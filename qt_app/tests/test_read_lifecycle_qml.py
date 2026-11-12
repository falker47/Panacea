"""Exercise page reads and Turbo uncertainty in real QML with inert services."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]


def _probe(language):
    sys.path.insert(0, str(ROOT))
    from types import SimpleNamespace
    from PySide6.QtCore import QCoreApplication, QEvent, QUrl, Slot
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from qt_app.icon_provider import NavigationIconProvider
    from qt_app.main import MaintenanceBridge, MetricsBridge, ReadBridge
    from qt_app.update_bridge import UpdateBridge

    class Reader(ReadBridge):
        @Slot(str)
        def request(self, action):
            requests.append(action)

    app = QGuiApplication([])
    requests = []
    reader = Reader()
    reader._service = SimpleNamespace(close=lambda: None)
    reader._busy = True
    reader._last_action = "hardware"
    maintenance = MaintenanceBridge(service=SimpleNamespace(close=lambda: None))
    metrics = MetricsBridge()
    updater = UpdateBridge(reader, maintenance, flow=SimpleNamespace(install_eligible=False))
    engine = QQmlApplicationEngine()
    warnings = []
    engine.warnings.connect(lambda errors: warnings.extend(str(error) for error in errors))
    engine.addImageProvider("panacea-nav", NavigationIconProvider())
    for name, value in {"applicationLanguage": language, "qaSmokeMode": False,
                        "nativeConfirmationsEnabled": False, "liveMetrics": metrics,
                        "readService": reader, "maintenanceService": maintenance,
                        "updateService": updater}.items():
        engine.rootContext().setContextProperty(name, value)
    engine.load(QUrl.fromLocalFile(str(ROOT / "qt_app/Main.qml")))
    if not engine.rootObjects():
        raise AssertionError(warnings)
    window = engine.rootObjects()[0]

    def items(root):
        yield root
        for child in root.childItems():
            yield from items(child)

    def snapshot():
        app.processEvents()
        visible = [item for item in items(window.contentItem()) if item.isVisible()]
        return {
            "texts": [item.property("text") for item in visible if isinstance(item.property("text"), str)],
            "restore_enabled": [bool(item.property("interactive")) for item in visible
                                if item.property("caption") in ("Ripristina impostazioni salvate", "Restore saved settings")],
            "switches_enabled": [bool(item.property("interactive")) for item in visible
                                 if item.metaObject().indexOfProperty("checked") >= 0],
        }

    try:
        window.setProperty("currentTab", 2)
        app.processEvents()
        window.setProperty("currentTab", 3)
        busy = snapshot()
        reader._results = {"turbo_status": {"available": False, "refreshing": True}}
        reader.changed.emit()
        refreshing = snapshot()
        reader._busy = False
        reader._results = {"turbo_status": {"available": False, "error": "fixture read denied"}}
        reader.changed.emit()
        failed = snapshot()
        reader._results = {"turbo_status": {"states": {"power": True}, "master": True,
                                              "saved_count": 1, "restore_available": True}}
        reader.changed.emit()
        recovered = snapshot()
        return {"requests": requests, "busy": busy, "refreshing": refreshing,
                "failed": failed, "recovered": recovered, "warnings": list(warnings)}
    finally:
        reader.stop()
        maintenance.stop()
        metrics.stop()
        updater.stop()
        engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


class ReadLifecycleQmlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.probes = {}
        for language in ("it", "en"):
            env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software")
            result = subprocess.run([sys.executable, str(Path(__file__)), "--probe", language],
                                    cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
            if result.returncode:
                raise AssertionError(f"QML probe failed: {result.stdout[-2000:]} {result.stderr[-4000:]}")
            cls.probes[language] = json.loads(result.stdout.strip().splitlines()[-1])

    def test_busy_page_visits_forward_the_requested_reads(self):
        for language, data in self.probes.items():
            with self.subTest(language=language):
                self.assertEqual(data["requests"], ["drives", "turbo_status"])
                self.assertEqual(data["warnings"], [])

    def test_footer_reports_active_reading_in_both_languages(self):
        for language, expected in (("it", "Verifica in corso · nessuna manutenzione"),
                                   ("en", "Reading system state · no maintenance")):
            with self.subTest(language=language):
                self.assertIn(expected, self.probes[language]["busy"]["texts"])

    def test_turbo_refresh_and_failure_keep_recovery_disabled_until_measured(self):
        for language, refreshing, failed, unknown in (
            ("it", "Verifica dello stato in corso…", "Stato non disponibile · Aggiorna stato", "Sconosciuto"),
            ("en", "Checking current state…", "State unavailable · Refresh state", "Unknown"),
        ):
            with self.subTest(language=language):
                data = self.probes[language]
                self.assertIn(refreshing, data["refreshing"]["texts"])
                self.assertIn(failed, data["failed"]["texts"])
                self.assertIn(unknown, data["failed"]["texts"])
                self.assertEqual(data["refreshing"]["restore_enabled"], [False])
                self.assertEqual(data["failed"]["restore_enabled"], [False])
                self.assertEqual(data["refreshing"]["switches_enabled"], [False] * 6)
                self.assertEqual(data["failed"]["switches_enabled"], [False] * 6)
                self.assertEqual(data["recovered"]["restore_enabled"], [True])


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--probe":
        print(json.dumps(_probe(sys.argv[2]), ensure_ascii=True))
    else:
        unittest.main()
