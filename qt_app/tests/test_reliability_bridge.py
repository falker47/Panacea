import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PySide6.QtCore import QCoreApplication

from modules.maintenance_guard import _state
from qt_app.bridges import reliability_bridge as bridge


class ReliabilityBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def idle(self, service):
        deadline = time.monotonic() + 5
        while service.busy and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.005)
        self.assertFalse(service.busy)

    def test_factory_shares_guard_installs_hooks_and_exposes_previous_crash(self):
        guard = Mock()
        guard.status.return_value = _state("clear")
        maintenance = SimpleNamespace(_service=SimpleNamespace(_manager=lambda _: guard))
        context = SimpleNamespace(reader=object(), maintenance=maintenance, updater=None,
                                  metrics=None, language=lambda: "it", qa_smoke=False)
        capture = SimpleNamespace(previous_crash=True)
        with patch.object(bridge.crash_guard, "install", return_value=capture) as install:
            objects = bridge.create(context)
        self.assertEqual(set(objects), {"reliabilityService", "historyService"})
        recovery = objects["reliabilityService"]
        self.assertTrue(recovery.previousCrash)
        install.assert_called_once_with()
        self.app.processEvents()
        self.idle(recovery)
        self.assertEqual(recovery.guardState["code"], "clear")
        guard.status.assert_called_once_with()

    def test_consent_is_one_use_cancelled_superseded_and_consumed_on_failure(self):
        guard = Mock()
        state = _state("interrupted_journal")
        guard.status.return_value = state
        context = SimpleNamespace(maintenance=object(), qa_smoke=False, language=lambda: "en")
        service = bridge.ReliabilityService(context, guard, None)
        service.refresh()
        self.idle(service)
        self.assertFalse(service.confirmArchive("unprepared"))
        rejected = service.prepareArchive()
        service.cancelArchive()
        self.assertFalse(service.confirmArchive(rejected))
        first, newer = service.prepareArchive(), service.prepareArchive()
        self.assertNotEqual(first, newer)
        self.assertFalse(service.confirmArchive(first))
        guard.archive.assert_not_called()
        nonce = service.prepareArchive()
        guard.archive.side_effect = TimeoutError()
        self.assertTrue(service.confirmArchive(nonce))
        self.idle(service)
        self.assertEqual(service.guardState["code"], "busy_other_instance")
        self.assertFalse(service.confirmArchive(nonce))
        self.assertEqual(service.prepareArchive(), "")
        guard.archive.assert_called_once_with(state)
        guard.archive.side_effect = None
        guard.archive.return_value = _state("clear")
        service.refresh()
        self.idle(service)
        nonce = service.prepareArchive()
        self.assertTrue(service.confirmArchive(nonce))
        self.idle(service)
        self.assertEqual(service.guardState["code"], "clear")
        self.assertFalse(service.confirmArchive(nonce))

    def test_smoke_context_has_no_io(self):
        ctx = SimpleNamespace(reader=None, maintenance=object(), updater=None, metrics=None,
                              language=lambda: "en", qa_smoke=True)
        with patch.object(bridge.crash_guard, "install") as hooks, patch.object(bridge.history, "page") as read:
            services = bridge.create(ctx)
            recovery = services["reliabilityService"]
            recovery.verifyAgain()
            recovery.exportDiagnostics()
            services["historyService"].loadPage(0, "")
            self.assertEqual(recovery.prepareArchive(), "")
            hooks.assert_not_called()
            read.assert_not_called()


    def test_read_adapter_preserves_legacy_keys_and_all_structured_fields(self):
        from qt_app.services import ReadService
        snapshot = _state("unknown_completion_same_boot", "2026-11-01T12:00:00Z", "sfc")
        guard = SimpleNamespace(status=lambda: snapshot)
        self.assertEqual(ReadService(factories={"guard": lambda: guard}).collect("guard_status"), snapshot)
