"""Qt maintenance bridge tests: no Windows mutation, only a fake gateway."""
import unittest

from PySide6.QtCore import QCoreApplication
from qt_app.main import MaintenanceBridge


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


if __name__ == "__main__":
    unittest.main()
