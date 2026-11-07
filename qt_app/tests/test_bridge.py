"""Qt maintenance bridge tests: no Windows mutation, only a fake gateway."""
import unittest

from PySide6.QtCore import QCoreApplication
from qt_app.main import MaintenanceBridge, ReadBridge


class FakeMaintenance:
    def __init__(self):
        self.prepared = []
        self.executed = []
        self.rejected = 0
        self.closed = False

    def prepare(self, action, drive):
        self.prepared.append((action, drive))
        if action != "temp_clean" or drive:
            raise ValueError("not approved")
        return {"nonce": "fixture-nonce", "title": "Temp clean", "details": "Permanent deletion"}

    def reject(self):
        self.rejected += 1

    def execute(self, nonce, *, log=None, progress=None):
        self.executed.append(nonce)
        log("fixture finished")
        return {"status": "completed", "message": "fixture success"}

    def cancel(self):
        pass

    def close(self):
        self.closed = True


class BridgeContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.fake = FakeMaintenance()
        self.bridge = MaintenanceBridge(service=self.fake)

    def tearDown(self):
        self.bridge.stop()

    def test_prepare_must_be_confirmed_and_is_one_use(self):
        self.bridge.prepare("temp_clean", "")
        self.assertTrue(self.bridge.awaitingConfirmation)
        self.assertIn("Permanent deletion", self.bridge.details)
        self.assertEqual(self.fake.executed, [])
        self.bridge.reject()
        self.assertFalse(self.bridge.awaitingConfirmation)
        self.bridge.confirm()
        self.assertEqual(self.fake.executed, [])

    def test_disallowed_arguments_fail_closed(self):
        self.bridge.prepare("temp_clean", "C:")
        self.assertFalse(self.bridge.awaitingConfirmation)
        self.assertIn("rifiutata", self.bridge.output)
        self.assertEqual(self.fake.executed, [])

    def test_confirm_dispatches_once_and_keeps_result(self):
        import time
        self.bridge.prepare("temp_clean", "")
        self.bridge.confirm()
        deadline = time.monotonic() + 3
        while self.bridge.busy and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.01)
        self.assertFalse(self.bridge.busy)
        self.assertEqual(self.fake.executed, ["fixture-nonce"])
        self.assertIn("fixture success", self.bridge.output)
        self.bridge.confirm()
        self.assertEqual(self.fake.executed, ["fixture-nonce"])

    def test_turbo_completion_refreshes_the_state_visible_to_qml(self):
        import time
        state = {"power": False}
        class Toggle(FakeMaintenance):
            def prepare(self, action, drive):
                return {"nonce": "toggle", "title": "Power", "details": "Fixture settings"}

            def execute(self, nonce, **callbacks):
                state["power"] = True
                return {"status": "completed", "message": "Fixture only"}

        class Reader:
            def collect(self, action):
                if action != "turbo_status":
                    raise AssertionError(action)
                return {"states": dict(state), "master": True}

            def close(self):
                pass

        reader = ReadBridge()
        reader._service = Reader()
        self.bridge._service = Toggle()
        self.bridge._reader = reader
        try:
            self.bridge.prepare("power_on", "")
            self.bridge.confirm()
            deadline = time.monotonic() + 2
            while "turbo_status" not in reader.results and time.monotonic() < deadline:
                self.app.processEvents()
                time.sleep(.01)
            self.assertEqual(reader.results.get("turbo_status", {}).get("states"), {"power": True})
        finally:
            reader.stop()

    def test_results_and_logs_remain_with_their_original_section(self):
        import time
        class Actions(FakeMaintenance):
            def prepare(self, action, drive):
                self.action = action
                return {"nonce": action, "title": action, "details": "Fixture"}

            def execute(self, nonce, *, log, progress):
                log("fixture " + nonce)
                return {"status": "completed", "message": nonce,
                        "steps": [{"success": True, "message": nonce}], "total": 1}

        self.bridge._service = Actions()
        for action in ("resurrection", "temp_clean"):
            self.bridge.prepare(action, "")
            self.bridge.confirm()
            deadline = time.monotonic() + 2
            while self.bridge.busy and time.monotonic() < deadline:
                self.app.processEvents()
                time.sleep(.01)
        self.assertEqual(getattr(self.bridge, "results", {}).get("resurrection", {}).get("status"), "completed")
        self.assertIn("fixture resurrection", getattr(self.bridge, "sectionLogs", {}).get("resurrect", ""))
        self.assertNotIn("fixture temp_clean", getattr(self.bridge, "sectionLogs", {}).get("resurrect", ""))

    def test_phase_outcome_is_visible_before_the_sequence_finishes(self):
        import threading
        import time
        release = threading.Event()
        class Running(FakeMaintenance):
            def prepare(self, action, drive):
                return {"nonce": "running", "title": action, "details": "Fixture"}

            def execute(self, nonce, *, log, progress):
                progress(1, 10, {"name": "Restore point", "success": False, "message": "Fixture failure"})
                release.wait(2)
                return {"status": "failed", "message": "Fixture failure"}

        self.bridge._service = Running()
        try:
            self.bridge.prepare("resurrection", "")
            self.bridge.confirm()
            deadline = time.monotonic() + 1
            while not self.bridge.progressDone and time.monotonic() < deadline:
                self.app.processEvents()
                time.sleep(.01)
            self.assertTrue(self.bridge.busy)
            self.assertEqual(self.bridge.steps, [{"name": "Restore point", "success": False, "message": "Fixture failure"}])
        finally:
            release.set()
            self.bridge._workers.join(2)

    def test_read_failure_is_a_structured_unavailable_snapshot(self):
        import time
        class FailingRead:
            def collect(self, action):
                raise PermissionError("Fixture read unavailable")

            def close(self):
                pass
        reader = ReadBridge()
        reader._service = FailingRead()
        try:
            reader.request("hardware")
            deadline = time.monotonic() + 1
            while reader.busy and time.monotonic() < deadline:
                self.app.processEvents()
                time.sleep(.01)
            self.assertEqual(reader.results.get("hardware", {}).get("available"), False)
            self.assertEqual(reader.results["hardware"]["error"], "Fixture read unavailable")
        finally:
            reader.stop()


if __name__ == "__main__":
    unittest.main()
