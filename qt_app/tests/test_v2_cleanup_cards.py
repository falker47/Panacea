"""Quick cleanup, its independent actions and its read-only preview remain directly reachable."""
import unittest

from qt_app.catalog import SECTION_ACTIONS
from qt_app.tests.test_v2_graph import find, page_test, value


class CleanupActionTests(unittest.TestCase):
    @page_test("cleanup")
    def test_every_cleanup_row_prepares_only_its_own_confirmation(self, f):
        for action in SECTION_ACTIONS["cleanup"]:
            with self.subTest(action=action):
                row = find(f.page, "action_" + action)
                self.assertTrue(row.isEnabled())
                row.click()
                self.assertEqual(f.maintenance.preparedAction, action)
                self.assertTrue(f.maintenance.awaitingConfirmation)
                self.assertFalse(f.backend.executed)
                f.maintenance.reject()
        self.assertEqual(value(find(f.page, "action_quick_cleanup"), "variant"), "primary")

    @page_test("cleanup", "it", "partial")
    def test_preview_is_read_only_and_partial_result_keeps_the_failing_step(self, f):
        from PySide6.QtTest import QTest

        steps = value(find(f.page, "steps_quick_cleanup"), "steps")
        self.assertEqual([row["state"] for row in steps], ["success", "success", "failed"])
        banner = find(f.page, "read_temp_preview")
        self.assertIn("128", value(banner, "description"))
        banner.click()
        for _ in range(100):
            if not f.reader.busy:
                break
            QTest.qWait(10)
        self.assertEqual(f.reader.lastAction, "temp_preview")
        self.assertTrue(f.reader.results["temp_preview"]["no_files_deleted"])
        self.assertFalse(f.maintenance.awaitingConfirmation)
        self.assertFalse(f.backend.executed)


if __name__ == "__main__":
    unittest.main()
