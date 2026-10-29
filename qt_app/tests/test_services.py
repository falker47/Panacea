"""Qt migration read-only service contract tests: no Qt or Windows host needed."""

import unittest
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
                                    "turbo_status", "guard_status"}))
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

    def test_turbo_state_never_toggles_settings(self):
        result = self.service.collect("turbo_status")
        self.assertEqual(result["states"]["power"], False)
        self.assertEqual(result["states"]["visual"], False)
        self.assertEqual(result["master"], False)

    def test_guard_reports_the_actual_blocking_reason(self):
        result = self.service.collect("guard_status")
        self.assertTrue(result["blocked"])
        self.assertEqual(result["message"], "Guard active")

    def test_owned_monitor_is_closed(self):
        self.service.collect("hardware")
        self.service.close()
        self.assertIn("close_monitor", self.calls)


if __name__ == "__main__":
    unittest.main()
