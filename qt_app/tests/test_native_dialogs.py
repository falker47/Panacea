"""Native-dialog decisions use the same one-use bridge token; no host dialog."""
import time
import unittest

from PySide6.QtCore import QCoreApplication
from qt_app.main import MaintenanceBridge
from qt_app.tests.test_bridge import FakeMaintenance


class NativeDialogConsent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def test_rejected_or_stale_native_decision_never_executes(self):
        from qt_app.native_dialogs import NativeConfirmations
        for stale in (False, True):
            service = FakeMaintenance()
            bridge = MaintenanceBridge(service=service)
            def decide(owner, title, detail):
                if stale:
                    bridge.reject()
                    return True
                return False
            controller = NativeConfirmations(bridge, None, lambda: 123, show=decide)
            try:
                bridge.prepare("temp_clean", "")
                self.app.processEvents()
                self.assertFalse(bridge.awaitingConfirmation)
                self.assertEqual(service.executed, [])
            finally:
                bridge.stop()
                controller.deleteLater()

    def test_accepted_native_decision_consumes_the_confirmation_once(self):
        from qt_app.native_dialogs import NativeConfirmations
        service = FakeMaintenance()
        bridge = MaintenanceBridge(service=service)
        controller = NativeConfirmations(bridge, None, lambda: 123, show=lambda *args: True)
        try:
            bridge.prepare("temp_clean", "")
            deadline = time.monotonic() + 2
            while not service.executed and time.monotonic() < deadline:
                self.app.processEvents()
                time.sleep(.01)
            bridge.confirm()
            self.assertEqual(service.executed, ["fixture-nonce"])
        finally:
            bridge.stop()
            controller.deleteLater()
