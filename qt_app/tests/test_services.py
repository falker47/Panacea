"""Qt migration read-only service contract tests: no Qt or Windows host needed."""

import unittest
import threading
from types import SimpleNamespace

from qt_app.services import ReadService, READ_ACTIONS


class ReadServiceTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        calls = self.calls

        class Monitor:
            def sample_metadata(self):
                calls.append("metadata")
                return {"os": "Windows 11", "cpu_name": "CPU test", "ram_info": "DDR5"}

            def get_windows_update_status(self):
                calls.append("windows_updates")
                return (1, 2, "3 Windows updates")

            def close(self):
                calls.append("close_monitor")

        class Cleanup:
            def __init__(self):
                self.last_result = SimpleNamespace(skipped=["locked"], errors=[])

            def preview_temp_files(self, progress_callback=None):
                calls.append("preview")
                return (12, 15 * 1024 * 1024)

            def clean_temp_files(self):
                raise AssertionError("A read-only adapter must never delete files")

        class Disk:
            def get_drive_info(self):
                calls.append("drives")
                return [{"letter": "C:", "available": True, "total_bytes": 1000,
                         "free_bytes": 450, "used_percent": 55.0, "error": ""}]

            def analyze_optimize_drive(self, drive):
                raise AssertionError("A read-only adapter must never optimize drives")

        class Perf:
            def get_power_plan(self):
                calls.append("power")
                return "balanced"

            def get_visual_effects(self):
                return True

            def get_sysmain_status(self):
                return True

            def get_wsearch_status(self):
                return True

            def get_spooler_status(self):
                return True

            def is_turbo_active(self):
                return False

            def set_turbo(self, value):
                raise AssertionError("A read-only adapter must never change services")

        class Guard:
            last_error = "Guard active"
            def is_blocked(self):
                calls.append("guard")
                return True

        self.service = ReadService(
            factories={"monitor": Monitor, "cleanup": Cleanup,
                       "disk": Disk, "performance": Perf, "guard": Guard}
        )

    def tearDown(self):
        self.service.close()

    def test_only_an_explicit_allowlist_is_exposed(self):
        self.assertEqual(READ_ACTIONS,
                         frozenset({"hardware", "temp_preview", "drives",
                                    "turbo_status", "guard_status", "windows_updates"}))
        for action in ("clean_temp", "resurrect", "run_cmd", "set_turbo", "install_update", ""):
            with self.subTest(action=action), self.assertRaises(ValueError):
                self.service.collect(action)
        self.assertEqual(self.calls, [])

    def test_preview_is_non_destructive_and_reports_proven_uncertainty(self):
        output = self.service.collect("temp_preview")
        self.assertEqual(output["count"], 12)
        self.assertEqual(output["bytes"], 15 * 1024 * 1024)
        self.assertEqual(output["skipped"], 1)
        self.assertEqual(output["errors"], 0)
        self.assertTrue(output["no_files_deleted"])
        self.assertEqual(self.calls, ["preview"])

    def test_disk_inventory_is_read_only(self):
        drives = self.service.collect("drives")
        self.assertEqual(drives["drives"][0]["letter"], "C:")
        self.assertEqual(drives["drives"][0]["used_percent"], 55.0)
        self.assertEqual(self.calls, ["drives"])

    def test_metadata_does_not_start_a_cleanup(self):
        result = self.service.collect("hardware")
        self.assertEqual(result["os"], "Windows 11")
        self.assertEqual(self.calls, ["metadata"])

    def test_windows_update_status_is_read_only(self):
        output = self.service.collect("windows_updates")
        self.assertEqual(output["recommended"], 1)
        self.assertEqual(output["optional"], 2)
        self.assertEqual(output["status"], "3 Windows updates")
        self.assertTrue(output["verified"])
        self.assertEqual(self.calls, ["windows_updates"])

    def test_turbo_state_never_toggles_settings(self):
        result = self.service.collect("turbo_status")
        self.assertEqual(result["states"]["power"], False)
        self.assertEqual(result["states"]["visual"], False)
        self.assertEqual(result["master"], False)
        self.assertFalse(result["restore_available"])
        self.assertIsNone(result["saved_count"])

    def test_guard_reports_the_actual_blocking_reason(self):
        result = self.service.collect("guard_status")
        self.assertTrue(result["blocked"])
        self.assertEqual(result["message"], "Guard active")

    def test_owned_monitor_is_closed(self):
        self.service.collect("hardware")
        self.service.close()
        self.assertIn("close_monitor", self.calls)

    def test_close_cancels_an_active_query_before_collect_returns(self):
        entered = threading.Event()
        release = threading.Event()
        cancelled = threading.Event()
        closed = threading.Event()
        errors = []

        class Monitor:
            def get_windows_update_status(self):
                entered.set()
                release.wait(5)
                return (0, 0, "done")

            def close(self):
                cancelled.set()
                release.set()

        service = ReadService(factories={"monitor": Monitor})

        def collect():
            try:
                service.collect("windows_updates")
            except Exception as exc:
                errors.append(exc)

        def close():
            service.close()
            closed.set()

        worker = threading.Thread(target=collect)
        closer = threading.Thread(target=close)
        worker.start()
        try:
            self.assertTrue(entered.wait(2))
            closer.start()
            self.assertTrue(cancelled.wait(1), "close waited behind its own active query")
            self.assertTrue(closed.wait(1))
        finally:
            release.set()
            worker.join(2)
            if closer.ident is not None:
                closer.join(2)
        self.assertFalse(worker.is_alive())
        self.assertFalse(closer.is_alive())
        self.assertEqual(errors, [])

    def test_close_during_monitor_creation_disposes_it_without_starting_a_query(self):
        creating = threading.Event()
        release_factory = threading.Event()
        closed = threading.Event()
        calls = []
        errors = []

        class Monitor:
            def sample_metadata(self):
                calls.append("query")
                return {}

            def close(self):
                calls.append("close")

        def factory():
            creating.set()
            release_factory.wait(5)
            return Monitor()

        service = ReadService(factories={"monitor": factory})

        def collect():
            try:
                service.collect("hardware")
            except Exception as exc:
                errors.append(exc)

        def close():
            service.close()
            closed.set()

        worker = threading.Thread(target=collect)
        closer = threading.Thread(target=close)
        worker.start()
        try:
            self.assertTrue(creating.wait(2))
            closer.start()
            self.assertTrue(closed.wait(1), "close waited for backend construction")
        finally:
            release_factory.set()
            worker.join(2)
            if closer.ident is not None:
                closer.join(2)
        self.assertFalse(worker.is_alive())
        self.assertFalse(closer.is_alive())
        self.assertEqual(calls, ["close"])
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], RuntimeError)
        service.close()
        self.assertEqual(calls, ["close"])

    def test_collections_remain_serialized(self):
        entered = threading.Event()
        release = threading.Event()
        second_attempt = threading.Event()
        second_entered = threading.Event()
        errors = []

        class Monitor:
            def get_windows_update_status(self):
                entered.set()
                release.wait(5)
                return (0, 0, "done")

            def sample_metadata(self):
                second_entered.set()
                return {}

            def close(self):
                release.set()

        service = ReadService(factories={"monitor": Monitor})

        def collect(action):
            try:
                if action == "hardware":
                    second_attempt.set()
                service.collect(action)
            except Exception as exc:
                errors.append(exc)

        first = threading.Thread(target=collect, args=("windows_updates",))
        second = threading.Thread(target=collect, args=("hardware",))
        first.start()
        try:
            self.assertTrue(entered.wait(2))
            second.start()
            self.assertTrue(second_attempt.wait(2))
            self.assertFalse(second_entered.wait(0.1))
            release.set()
            self.assertTrue(second_entered.wait(2))
        finally:
            release.set()
            first.join(2)
            if second.ident is not None:
                second.join(2)
            service.close()
        self.assertEqual(errors, [])

    def test_close_is_idempotent_and_rejects_new_reads(self):
        self.service.collect("hardware")
        self.service.close()
        self.service.close()
        with self.assertRaises(RuntimeError):
            self.service.collect("windows_updates")
        self.assertEqual(self.calls, ["metadata", "close_monitor"])


if __name__ == "__main__":
    unittest.main()
