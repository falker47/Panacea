"""Inspect real Qt items and record reproducible visual evidence in smoke mode."""
from __future__ import annotations

import hashlib
from itertools import combinations
from pathlib import Path

from PySide6.QtCore import QPointF
from PySide6.QtGui import QAccessible, QFontInfo


def items(root):
    yield root
    for child in root.childItems():
        yield from items(child)


def source_digest(root: Path) -> str:
    digest = hashlib.sha256()
    sources = [root / "Main.qml", *sorted((root / "qml").rglob("*.qml")),
               *sorted((root / "qml").rglob("qmldir")), *sorted((root / "i18n").glob("*.json"))]
    for path in sources:
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def inspect_window(window, section):
    visible = [item for item in items(window.contentItem()) if item.isVisible()]
    named = {item.objectName(): item for item in visible if item.objectName()}
    for name in ("sidebar", "workspace", "pageTitle", "page_" + section, "pageViewport"):
        if name not in named:
            raise ValueError(f"Missing item {name} on {section}")
    failures, interactive, labels, boxes = [], [], [], []
    width = window.width()
    for item in visible:
        if item.width() <= 0 or item.height() <= 0:
            continue
        name = item.objectName()
        pos = item.mapToScene(QPointF(0, 0))
        left, top = pos.x(), pos.y()
        right, bottom = left + item.width(), top + item.height()
        if item.inherits("QQuickText") or item.inherits("QQuickTextInput") or item.inherits("QQuickTextEdit"):
            label = item.property("text") or ""
            if label:
                labels.append(label)
                font = item.property("font")
                if QFontInfo(font).pixelSize() < 12:
                    failures.append(f"Text smaller than 12 px: {label[:70]}")
                if left < -1 or right > width + 1:
                    failures.append(f"Text extends outside the window: {label[:70]}")
        actionable = (item.inherits("QQuickAbstractButton") or item.inherits("QQuickComboBox")
                      or item.inherits("QQuickTextInput") or item.inherits("QQuickTextEdit")
                      or (item.inherits("QQuickScrollBar") and item.property("interactive")))
        if actionable or (item.inherits("QQuickControl") and item.activeFocusOnTab()):
            interface = QAccessible.queryAccessibleInterface(item)
            role = interface.role() if interface is not None else QAccessible.Role.NoRole
            label = interface.text(QAccessible.Text.Name) if interface is not None else ""
            if role == QAccessible.Role.NoRole or not label.strip():
                failures.append(f"Unnamed control or missing role: {name} {item.metaObject().className()}")
            interactive.append({"id": name, "name": label, "role": role.name})
        if name.startswith(("nav_", "action_")):
            for child in items(item):
                if child.isVisible() and child.inherits("QQuickText") and child.property("truncated"):
                    failures.append(f"Clipped label in {name}: {child.property('text')}")
        if name.startswith(("nav_", "action_")) or name in ("pageTitle", "openPalette", "brandLogo"):
            if left < -1 or right > width + 1:
                failures.append(f"{name} extends outside the window")
            ancestor = item.parentItem()
            while ancestor is not None:
                if ancestor.clip():
                    corner = ancestor.mapToScene(QPointF(0, 0))
                    left, right = max(left, corner.x()), min(right, corner.x()+ancestor.width())
                    top, bottom = max(top, corner.y()), min(bottom, corner.y()+ancestor.height())
                ancestor = ancestor.parentItem()
            if left < right and top < bottom:
                boxes.append((name, left, top, right, bottom))
    for a, b in combinations(boxes, 2):
        if min(a[3], b[3]) - max(a[1], b[1]) > 1 and min(a[4], b[4]) - max(a[2], b[2]) > 1:
            failures.append(f"Overlapping key items: {a[0]}, {b[0]}")
    viewport = named["pageViewport"]
    if (viewport.property("contentWidth") or 0) > viewport.width() + 1:
        failures.append("Horizontal scrolling is required")
    return {"errors": failures, "controls": interactive, "text": labels,
            "keyItems": boxes, "sidebarWidth": named["sidebar"].width()}
