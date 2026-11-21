"""Render packaged Panacea and Lucide masks with Qt, including system palette tints."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import re

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPolygonF, qRgba
from PySide6.QtQuick import QQuickImageProvider
from PySide6.QtSvg import QSvgRenderer

from modules.utils import resource_path


_LUCIDE = {
    "layout-dashboard", "brush-cleaning", "wrench", "zap", "shield-plus",
    "layout-grid", "memory-stick", "cpu", "hard-drive", "file-search", "refresh-cw",
}
_SYMBOLS = {
    "menu", "panel", "settings", "history", "search", "close", "check", "chevron-right",
    "chevron-down", "chevron-up", "clock", "info", "warning", "error", "copy",
    "download", "activity", "windows",
}
_ALIASES = {
    "dashboard": "layout-dashboard", "home": "layout-dashboard",
    "clean": "brush-cleaning", "cleanup": "brush-cleaning",
    "apps": "layout-grid", "startup": "layout-grid",
    "tools": "wrench", "repair": "wrench",
    "turbo": "zap", "performance": "zap",
    "guided": "resurrect", "restore": "shield-plus",
    "memory": "memory-stick", "drive": "hard-drive", "disk": "hard-drive",
    "scan": "file-search", "updates": "refresh-cw",
}
_BATTERY = re.compile(r"battery-([0-9]{1,3})-(charging|plugged|unplugged)")
_RGB = re.compile(r"[0-9a-fA-F]{6}")
_SIZE = 96


def _canvas() -> QImage:
    image = QImage(_SIZE, _SIZE, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    return image


def _chalice() -> QImage:
    logo = QImage(resource_path("assets/panacea_icon.png"))
    if logo.isNull():
        return logo
    # Isolate the original mark inside the square brand frame.
    mark = logo.copy(140, 73, 254, 352).convertToFormat(QImage.Format_Grayscale8)
    mask = mark.convertToFormat(QImage.Format_Indexed8)
    mask.setColorTable([qRgba(255, 255, 255, min(255, max(0, (gray - 38) * 3))) for gray in range(256)])
    mask = mask.scaled(75, 84, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    image = _canvas()
    with QPainter(image) as painter:
        painter.drawImage((_SIZE - mask.width()) // 2, (_SIZE - mask.height()) // 2, mask)
    return image


def _battery(percent: int | None, state: str) -> QImage:
    image = _canvas()
    with QPainter(image) as painter:
        painter.setRenderHint(QPainter.Antialiasing)
        painter.scale(4, 4)
        painter.setPen(QPen(Qt.white, 1.5))
        painter.drawRoundedRect(QRectF(2.5, 6.5, 17.5, 11), 1.5, 1.5)
        painter.setPen(Qt.NoPen)
        painter.setBrush(Qt.white)
        painter.drawRoundedRect(QRectF(21, 10, 2, 4), 0.5, 0.5)
        if percent:
            painter.drawRoundedRect(QRectF(4.5, 8.5, 13.5 * percent / 100, 7), 0.5, 0.5)
        if state == "charging":
            bolt = QPolygonF([QPointF(x, y) for x, y in (
                (14, 2), (9, 12.5), (12.5, 12), (10, 22), (16.5, 10), (13, 10.5),
            )])
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.setPen(QPen(Qt.white, 1.8))
            painter.drawPolygon(bolt)
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            painter.setPen(Qt.NoPen)
            painter.drawPolygon(bolt)
        elif state == "plugged":
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.drawEllipse(QRectF(14.5, 2, 6.5, 6.5))
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            painter.drawEllipse(QRectF(15.5, 3, 4.5, 4.5))
    return image


@lru_cache(maxsize=96)
def _mask(name: str) -> QImage:
    if name in _LUCIDE:
        return QImage(resource_path(f"assets/icons/lucide/png/{name}.png"))
    if name in _SYMBOLS:
        renderer = QSvgRenderer(str(Path(__file__).parent / "qml" / "components" / "symbols.svg"))
        if not renderer.elementExists(name):
            return QImage()
        bounds = renderer.boundsOnElement(name)
        target = QRectF(bounds.x() * 4, bounds.y() * 4, bounds.width() * 4, bounds.height() * 4)
        image = _canvas()
        with QPainter(image) as painter:
            renderer.render(painter, name, target)
        return image
    if name == "resurrect":
        return _chalice()
    if name in ("battery", "battery-report"):
        return _battery(70 if name == "battery-report" else None, "unplugged")
    battery = _BATTERY.fullmatch(name)
    if battery and int(battery[1]) <= 100:
        return _battery(int(battery[1]), battery[2])
    return QImage()


class NavigationIconProvider(QQuickImageProvider):
    """Resolve allowlisted names and RGB values only; QML cannot supply a file path."""

    def __init__(self):
        super().__init__(QQuickImageProvider.Image)

    def requestImage(self, identifier: str, size: QSize, requestedSize: QSize) -> QImage:
        raw_name, _, tone = identifier.partition("/")
        name = raw_name.removesuffix(".png")
        if raw_name.endswith(".png") and name not in _LUCIDE:
            return QImage()
        if _RGB.fullmatch(tone):
            color = QColor("#" + tone)
        elif tone == "detail":
            color = QColor("#e4c579" if name in ("drive", "restore", "disk", "battery-report") else "#76b6e2")
        elif tone in ("active", "idle") and not _BATTERY.fullmatch(name):
            color = QColor("#e4c579" if tone == "active" else "#a9b6cc")
        else:
            return QImage()
        mask = _mask(_ALIASES.get(name, name))
        if mask.isNull():
            return QImage()
        image = mask.convertToFormat(QImage.Format_ARGB32_Premultiplied)
        with QPainter(image) as painter:
            painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
            painter.fillRect(image.rect(), color)
        if requestedSize is not None and not requestedSize.isEmpty():
            image = image.scaled(requestedSize, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        if size is not None:
            size.setWidth(image.width())
            size.setHeight(image.height())
        return image
