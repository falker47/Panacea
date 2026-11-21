"""Exercise the real extension and all four controls in an isolated offscreen Qt application."""
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]


def probe(language):
    from PySide6.QtCore import QUrl, Qt, QEvent, QCoreApplication
    from PySide6.QtGui import QAccessible, QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from PySide6.QtQuick import QQuickWindow
    from PySide6.QtTest import QTest
    from modules.health_check import evaluate
    from qt_app.bridges.features_bridge import create
    from qt_app.tests.test_features_bridge import fixture_context

    app = QGuiApplication([])
    ctx = fixture_context()
    identifier = "a" * 64
    ctx.reader.results = {
        "health_check": evaluate({"uptime_days": 9}),
        "startup_apps": {"apps": [{"id": identifier, "display_name": "Fixture", "scope": "user", "location": "Run",
                                   "publisher": "Publisher", "description": "App", "command": "example.exe",
                                   "enabled": True, "last_changed": None}]},
        "deep_cleanup_preview": {"categories": [
            {"id": key, "available": True, "default_selected": key != "crash_dumps", "count": 3, "bytes": 700,
             "samples": ["test/one"], "skipped": 0} for key in ("shader_cache", "crash_dumps")]},
        "drives": {"drives": [{"letter": "R:", "available": True}]},
    }
    objects = create(ctx)
    objects["storageService"]._data = {"selection": "profile", "status": "completed", "entries": 2,
                                       "folders": [{"path": "fixture/folder", "bytes": 300}], "files": []}
    ctx.maintenance.results = {"deep_cleanup": {"steps": [{"id": "shader_cache", "status": "partial", "count": 2,
                                                           "bytes": 30, "skipped": 1}]}}
    engine = QQmlEngine()
    warnings = []
    engine.warnings.connect(lambda errors: warnings.extend(e.toString() for e in errors))
    for key, value in objects.items():
        engine.rootContext().setContextProperty(key, value)
    window = QQuickWindow()
    window.resize(680, 720)
    window.show()

    def controls(item):
        for child in item.childItems():
            yield child
            yield from controls(child)

    def press(button):
        button.forceActiveFocus(Qt.FocusReason.TabFocusReason)
        app.processEvents()
        assert button.hasActiveFocus(), button.property("text")
        QTest.keyClick(window, Qt.Key.Key_Space)
        app.processEvents()

    for name in ("HealthCheck", "StartupApps", "DeepCleanup", "StorageAnalysis"):
        print(f"Loading {name} ({language})", flush=True)
        path = ROOT / "qt_app/qml/features" / (name + ".qml")
        component = QQmlComponent(engine, QUrl.fromLocalFile(str(path)))
        assert component.isReady(), component.errorString()
        root = component.createWithInitialProperties({"language": language, "width": 650})
        assert root is not None, component.errorString()
        root.setParentItem(window.contentItem())
        root.setHeight(root.implicitHeight())
        app.processEvents()
        buttons = []
        for item in controls(root):
            if not item.isVisible():
                continue
            if item.metaObject().indexOfProperty("font") >= 0:
                font = item.property("font")
                assert font.pixelSize() >= 12, (name, item, font.pixelSize())
            if not item.activeFocusOnTab():
                continue
            interface = QAccessible.queryAccessibleInterface(item)
            assert interface and interface.text(QAccessible.Text.Name), (name, item)
            if interface.role() in (QAccessible.Role.Button, QAccessible.Role.CheckBox, QAccessible.Role.ComboBox):
                buttons.append(item)
        assert buttons, name
        if name == "HealthCheck":
            press(next(b for b in buttons if b.property("text") in ("Esegui controllo", "Run check")))
            assert ctx.reader.calls[-1] == "health_check"
            press(next(b for b in buttons if b.property("text") in ("Apri Windows Update", "Open Windows Update")))
            assert ctx.maintenance.calls[-1] == ("windows_update", "")
        elif name == "StartupApps":
            press(next(b for b in buttons if b.property("text") in ("Disabilita", "Disable")))
            assert ctx.maintenance.calls[-1] == ("startup_disable", identifier)
        elif name == "DeepCleanup":
            check = next(b for b in buttons if "dump" in (b.property("text") or "").lower())
            assert not check.property("checked")
            press(check)
            assert check.property("checked")
            press(next(b for b in buttons if (b.property("text") or "").endswith("(2)")))
            assert ctx.maintenance.calls[-1] == ("deep_cleanup", "shader_cache,crash_dumps")
        else:
            assert any(b.property("text") in ("Mostra in Esplora file", "Show in Explorer") for b in buttons)
        assert not warnings, warnings
        root.setParentItem(None)
        root.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert not warnings, warnings
    window.close()


class FeatureQmlTests(unittest.TestCase):
    def test_localized_components_and_keyboard_actions(self):
        for language in ("it", "en"):
            with self.subTest(language=language):
                env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QUICK_CONTROLS_STYLE="Basic")
                completed = subprocess.run([sys.executable, "-m", "qt_app.tests.test_features_qml", language],
                                           cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
                self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
                self.assertNotIn("qml:", completed.stderr.lower())
                self.assertNotIn(".qml:", completed.stderr.lower())


if __name__ == "__main__":
    probe(sys.argv[1])
