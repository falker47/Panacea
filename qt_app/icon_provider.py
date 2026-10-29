"""Tint the shipped Lucide PNG icons without duplicating files or writing assets.

Qt Quick Image cannot recolor a raster icon by itself. The image provider
retains the original alpha mask and applies V2's approved idle/gold colors.
Every requested name is checked against a fixed allowlist.
"""
from __future__ import annotations

from pathlib import Path
import sys

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtQuick import QQuickImageProvider


_ICON_NAMES = frozenset({
    "layout-dashboard.png", "brush-cleaning.png", "wrench.png",
    "zap.png", "shield-plus.png",
})
_BUNDLE_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
_ICON_ROOT = _BUNDLE_ROOT / "assets" / "icons" / "lucide" / "png"


class NavigationIconProvider(QQuickImageProvider):
    """Read-only image provider for the five V2 navigation destinations."""

    def __init__(self):
        super().__init__(QQuickImageProvider.Image)

    def requestImage(self, identifier: str, size: QSize, requestedSize: QSize) -> QImage:
        name, separator, tone = identifier.rpartition("/")
        if not separator or name not in _ICON_NAMES or tone not in ("active", "idle"):
            return QImage()
        result = QImage(str(_ICON_ROOT / name))
        if result.isNull():
            return result
        result = result.convertToFormat(QImage.Format_ARGB32_Premultiplied)
        if requestedSize is not None and requestedSize.isValid():
            result = result.scaled(
                requestedSize,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        painter = QPainter(result)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(result.rect(), QColor("#e4c579" if tone == "active" else "#a5b5cd"))
        painter.end()
        if size is not None:
            size.setWidth(result.width())
            size.setHeight(result.height())
        return result
