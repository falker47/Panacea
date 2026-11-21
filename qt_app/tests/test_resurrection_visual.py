"""All ten guided operations retain their help, real outcomes and pending diagnostics."""
import unittest

from qt_app.tests.test_v2_graph import descendants, find, page_test, value


class GuidedMaintenanceTests(unittest.TestCase):
    @page_test("guided")
    def test_phase_order_and_descriptions_match_the_backend_sequence(self, f):
        keys = ["restore_point", "browser_clean", "temp_clean", "recycle_empty", "dns_flush",
                "winsock_reset", "drive_optimize", "chkdsk", "dism_check", "sfc"]
        steps = value(find(f.page, "steps_resurrection"), "steps")
        self.assertEqual([row["title"] for row in steps], [f.strings.t(f"action.{key}.title") for key in keys])
        self.assertEqual([row["description"] for row in steps], [f.strings.t(f"pages.step.{key}") for key in keys])
        self.assertEqual([row["state"] for row in steps], ["pending"] * 10)
        self.assertFalse(f.maintenance.awaitingConfirmation)
        find(f.page, "action_resurrection").click()
        self.assertTrue(f.maintenance.awaitingConfirmation)
        self.assertEqual(f.maintenance.preparedAction, "resurrection")
        self.assertFalse(f.backend.executed)

    @page_test("guided", "it", "running")
    def test_running_cancelled_failed_and_unverified_states_use_reported_results(self, f):
        sequence = find(f.page, "steps_resurrection")

        def states():
            return [row["state"] for row in value(sequence, "steps")]

        self.assertEqual(states(), ["success", "success", "running"] + ["pending"] * 7)
        f.maintenance._busy = False
        for status in ("cancelled", "failed", "partial", "unknown"):
            f.maintenance._result_status = status
            f.maintenance._steps = [{"success": False, "message": "fixture 42"}]
            f.maintenance._progress_done = 7  # A count alone can never verify individual outcomes.
            f.maintenance._remember_result()
            f.maintenance.changed.emit()
            remaining = "unknown" if status == "unknown" else "skipped"
            self.assertEqual(states(), ["failed"] + [remaining] * 9)
        details = [value(node, "details") for node in descendants(f.page)
                   if node.isVisible() and node.metaObject().indexOfProperty("details") >= 0]
        self.assertTrue(any("fixture 42" in raw for raw in details))


if __name__ == "__main__":
    unittest.main()
