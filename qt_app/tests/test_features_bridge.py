import threading
import time
from types import SimpleNamespace
import unittest

from PySide6.QtCore import QCoreApplication, QObject, Signal

from qt_app.bridges.features_bridge import StorageService, create
from qt_app.maintenance import MaintenanceService


class Signals(QObject):
    changed = Signal()

    def __init__(self):
        super().__init__()
        self.busy, self.lastAction = False, ""
        self.results, self.calls = {}, []

    def request(self, action):
        self.calls.append(action)

    def prepareTarget(self, *args):
        self.calls.append(args)

    def prepare(self, *args):
        self.calls.append(args)


def fixture_context(smoke=False):
    return SimpleNamespace(reader=Signals(), maintenance=Signals(), updater=Signals(), metrics=Signals(),
                           language=lambda: "it", qa_smoke=smoke)


class FeaturesBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def test_extension_routes_only_preparation_and_read_requests(self):
        ctx = fixture_context()
        services = create(ctx)
        self.assertEqual(set(services), {"startupService", "healthService", "deepCleanupService", "storageService"})
        self.assertTrue(all(isinstance(s, QObject) for s in services.values()))
        services["startupService"].refresh()
        services["startupService"].setEnabled("fixture", False)
        services["startupService"].setEnabled("fixture", True)
        services["deepCleanupService"].prepare("wer_reports")
        services["healthService"].windowsUpdate()
        self.assertEqual(ctx.reader.calls, ["startup_apps"])
        self.assertEqual(ctx.maintenance.calls, [("startup_disable", "fixture"), ("startup_enable", "fixture"),
                                               ("deep_cleanup", "wer_reports"), ("windows_update", "")])
        ctx.maintenance.lastAction = "startup_disable"
        ctx.maintenance.busy = True
        ctx.maintenance.changed.emit()
        ctx.maintenance.busy = False
        ctx.maintenance.changed.emit()
        self.assertEqual(ctx.reader.calls[-1], "startup_apps")

    def test_smoke_mode_is_inert(self):
        ctx = fixture_context(smoke=True)
        objects = create(ctx)
        objects["startupService"].refresh()
        objects["startupService"].setEnabled("fixture", True)
        objects["deepCleanupService"].prepare("crash_dumps")
        objects["storageService"].loadDrives()
        objects["storageService"].scan("profile", True)
        objects["healthService"].windowsUpdate()
        self.assertFalse(ctx.reader.calls or ctx.maintenance.calls or objects["storageService"].busy)

    def test_legacy_actions_reject_unexpected_target_and_new_actions_require_one(self):
        service = MaintenanceService(platform="test")
        for action in ("startup_disable", "startup_enable", "deep_cleanup"):
            with self.subTest(action=action), self.assertRaises(ValueError):
                service.prepare(action)
        with self.assertRaises(ValueError):
            service.prepare("temp_clean", target="value")
        with self.assertRaises(ValueError):
            service.prepare("chkdsk", "C:", target="value")
        self.assertIn("nonce", service.prepare("chkdsk", "C:"))

    def test_storage_worker_can_cancel_and_closes_without_explorer(self):
        entered = threading.Event()
        def scan(selection, *, cancel, progress, refresh):
            progress(137)
            entered.set()
            if not cancel.wait(4):
                raise AssertionError("cancel did not reach scan")
            return {"selection": selection, "status": "cancelled", "entries": 137}
        ctx = fixture_context()
        worker = StorageService(ctx, scanner=SimpleNamespace(scan=scan))
        worker.scan("P:", False)
        self.assertFalse(worker.busy)
        worker.scan("profile", True)
        self.assertTrue(entered.wait(2))
        worker.cancel()
        deadline = time.monotonic() + 3
        while worker.busy and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.005)
        self.assertEqual(worker.data["status"], "cancelled")
        self.assertEqual(worker.visited, 137)
        worker.openItem("anything")
        self.assertFalse(worker.openError)
