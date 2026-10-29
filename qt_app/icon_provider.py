"""Generate Qt navigation glyphs from the authoritative Panacea V2 artwork."""
from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage
from PySide6.QtQuick import QQuickImageProvider

from modules.ui_icons import make_icon, make_windows_icon


# Old QA identifiers remain readable, while QML uses the original V2 names.
_ALIASES = {
    "layout-dashboard.png": "dashboard",
    "brush-cleaning.png": "clean",
    "wrench.png": "tools",
    "zap.png": "turbo",
    "shield-plus.png": "resurrect",
}
_ORIGINAL_NAMES = frozenset(("dashboard", "clean", "tools", "turbo", "resurrect"))
_DETAIL_NAMES = frozenset(("cpu", "memory", "drive", "scan", "restore", "updates", "windows"))


@lru_cache(maxsize=10)
def _source_image(name: str, tone: str) -> QImage:
    if tone == "detail":
        color = "#e4c579" if name in ("drive", "restore") else "#76b6e2"
    else:
        color = "#e4c579" if tone == "active" else "#a5b5cd"
    art = make_windows_icon(color=color, size=96) if name == "windows" else make_icon(name, color, 96)
    pixels = art.tobytes()
    # Own the pixel memory after the temporary Python bytes are released.
    return QImage(pixels, 96, 96, 96 * 4, QImage.Format_RGBA8888).copy()


class NavigationIconProvider(QQuickImageProvider):
    """Read-only allowlisted image provider for the five V2 destinations."""

    def __init__(self):
        super().__init__(QQuickImageProvider.Image)

    def requestImage(self, identifier: str, size: QSize, requestedSize: QSize) -> QImage:
        name, separator, tone = identifier.rpartition("/")
        name = _ALIASES.get(name, name)
        allowed = (_ORIGINAL_NAMES if tone in ("active", "idle")
                   else _DETAIL_NAMES if tone == "detail" else frozenset())
        if not separator or name not in allowed:
            return QImage()
        original = _source_image(name, tone)
        if requestedSize is not None and requestedSize.isValid():
            result = original.scaled(requestedSize, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        else:
            result = original.copy()
        if size is not None:
            size.setWidth(result.width())
            size.setHeight(result.height())
        return result
