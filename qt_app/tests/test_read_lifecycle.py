"""Read/mutation handoff regression tests; every backend is inert."""
import threading
import time
import unittest
from types import SimpleNamespace

from PySide6.QtCore import QCoreApplication

from qt_app.main import MaintenanceBridge, ReadBridge


class ReadLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def wait_for(self, condition):
        deadline = time.monotonic() + 3
        while not condition() and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(.005)
        self.assertTrue(condition(), "fixture callback did not arrive")

    def test_turbo_attempt_invalidates_and_rereads_every_terminal_outcome(self):
        for outcome in ("completed", "partial", "failed", "unknown", "cancelled", "exception"):
            with self.subTest(outcome=outcome):
                release = threading.Event()
                state = {"power": False, "saved_count": 0}
                calls = []

                class Reader:
                    def collect(self, action):
                        calls.append(action)
                        return {"states": {"power": state["power"]},
                                "saved_count": state["saved_count"],
                                "restore_available": bool(state["saved_count"])}

                    def close(self):
                        pass

                class Mutation:
                    def prepare(self, action, drive):
                        return {"nonce": "fixture", "title": "Fixture", "details": "Inert"}

                    def reject(self):
                        pass

                    def execute(self, nonce, **callbacks):
                        release.wait(3)
                        # One setter succeeded, then another failed. Originals survive.
                        state.update(power=True, saved_count=5)
                        if outcome == "exception":
                            raise RuntimeError("second fixture setter failed")
                        return {"status": outcome, "message": "fixture terminal result"}

                    def close(self):
                        release.set()

                reader = ReadBridge()
                reader._service = Reader()
                bridge = MaintenanceBridge(service=Mutation())
                reader._maintenance = bridge
                bridge._reader = reader
                reader._results["turbo_status"] = {
                    "states": {"power": False}, "saved_count": 0, "restore_available": False}
                try:
                    bridge.prepare("turbo_on", "")
                    bridge.confirm()
                    self.assertFalse(reader.results["turbo_status"].get("available", True))
                    self.assertNotIn("states", reader.results["turbo_status"])
                    self.assertEqual(calls, [], "no read may overlap the mutation")
                    release.set()
                    self.wait_for(lambda: not bridge.busy and not reader.busy and bool(calls))
                    self.assertEqual(calls, ["turbo_status"])
                    self.assertEqual(reader.results["turbo_status"]["states"], {"power": True})
                    self.assertTrue(reader.results["turbo_status"]["restore_available"])
                    self.assertEqual(bridge.resultStatus, "failed" if outcome == "exception" else outcome)
                finally:
                    release.set()
                    bridge._workers.join(3)
                    reader._workers.join(3)
                    bridge.stop()
                    reader.stop()

    def test_refresh_failure_keeps_unknown_instead_of_previous_turbo_values(self):
        class Reader:
            def collect(self, action):
                raise PermissionError("fixture read denied")

            def close(self):
                pass

        reader = ReadBridge()
        reader._service = Reader()
        reader._results["turbo_status"] = {"states": {"power": True}, "restore_available": True}
        try:
            reader.request("turbo_status")
            self.assertNotIn("states", reader.results["turbo_status"])
            self.wait_for(lambda: not reader.busy)
            self.assertEqual(reader.results["turbo_status"],
                             {"available": False, "error": "fixture read denied"})
        finally:
            reader.stop()

    def test_busy_requests_are_coalesced_and_processed_after_a_failed_read(self):
        release = threading.Event()
        calls = []

        class Reader:
            def collect(self, action):
                calls.append(action)
                if action == "hardware":
                    release.wait(3)
                    raise RuntimeError("fixture metadata failure")
                return {"drives": []} if action == "drives" else {"states": {"power": True}}

            def close(self):
                release.set()

        reader = ReadBridge()
        reader._service = Reader()
        try:
            reader.request("hardware")
            for _ in range(20):
                reader.request("drives")
                reader.request("turbo_status")
            reader.request("unsafe")
            release.set()
            self.wait_for(lambda: len(calls) == 3 and not reader.busy)
            self.assertEqual(calls, ["hardware", "drives", "turbo_status"])
            self.assertFalse(reader.results["hardware"]["available"])
        finally:
            release.set()
            reader._workers.join(3)
            reader.stop()

    def test_queued_reads_wait_for_mutation_and_updater_and_stop_discards_them(self):
        for blocker_name in ("_maintenance", "_updater"):
            with self.subTest(blocker=blocker_name):
                calls = []
                reader = ReadBridge()
                reader._service = SimpleNamespace(collect=lambda action: calls.append(action) or {}, close=lambda: None)
                blocker = SimpleNamespace(busy=True)
                setattr(reader, blocker_name, blocker)
                try:
                    reader.request("turbo_status")
                    self.app.processEvents()
                    self.assertEqual(calls, [])
                    blocker.busy = False
                    self.wait_for(lambda: calls == ["turbo_status"] and not reader.busy)
                    blocker.busy = True
                    reader.request("drives")
                    reader.stop()
                    blocker.busy = False
                    for _ in range(10):
                        self.app.processEvents()
                        time.sleep(.01)
                    self.assertEqual(calls, ["turbo_status"])
                finally:
                    reader.stop()

    def test_pending_confirmations_keep_queued_reads_from_consuming_the_accept(self):
        for blocker_name, pending_name in (("_maintenance", "awaitingConfirmation"),
                                           ("_updater", "pending")):
            with self.subTest(blocker=blocker_name):
                calls = []
                reader = ReadBridge()
                reader._service = SimpleNamespace(collect=lambda action: calls.append(action) or {}, close=lambda: None)
                blocker = SimpleNamespace(busy=True, **{pending_name: False})
                setattr(reader, blocker_name, blocker)
                try:
                    reader.request("drives")
                    blocker.busy = False
                    setattr(blocker, pending_name, True)
                    # Native modal dialogs run the Qt event loop, including the
                    # queue timer, while awaiting the user's confirmation.
                    for _ in range(20):
                        self.app.processEvents()
                        time.sleep(.005)
                    self.assertEqual(calls, [])
                    self.assertFalse(reader.busy, "a native confirmation must remain actionable")
                    setattr(blocker, pending_name, False)
                    self.wait_for(lambda: calls == ["drives"] and not reader.busy)
                finally:
                    reader.stop()


if __name__ == "__main__":
    unittest.main()
