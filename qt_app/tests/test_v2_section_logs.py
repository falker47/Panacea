"""Section activity stays with its tools. Diagnostic detail preserves the original output."""
import unittest

from qt_app.tests.test_v2_graph import descendants, find, page_test, value


class ActivityLogTests(unittest.TestCase):
    @page_test("cleanup")
    def test_individual_logs_keep_distinct_raw_output_and_the_users_expansion_choice(self, f):
        raw = "Deleted 50 files...\nDeleted 100 files...\nAccess denied: fixture"
        f.maintenance._results = {
            "temp_clean": {"status": "partial", "output": raw},
            "browser_clean": {"status": "completed", "output": "Browser fixture"},
            "sfc": {"status": "completed", "output": "Unrelated repair result"},
        }
        f.maintenance._section_logs["cleanup"] = "Earlier run\n" + raw
        f.maintenance.changed.emit()
        temp = find(f.page, "actionLog_temp_clean")
        browser = find(f.page, "actionLog_browser_clean")
        self.assertEqual(value(temp, "summary"), "Partially completed")
        self.assertEqual(value(temp, "details"), raw)
        self.assertEqual(value(browser, "details"), "Browser fixture")
        self.assertTrue(any(node.isVisible() and "Earlier run" in (value(node, "details") or "")
                            for node in descendants(f.page)))
        self.assertFalse(value(temp, "expanded"))
        self.assertFalse(any(item.isVisible() and item.objectName() == "actionLog_sfc" for item in descendants(f.page)))
        find(temp, "toggleLogDetails").click()
        self.assertTrue(value(temp, "expanded"))
        editor = find(temp, "logDetails")
        self.assertTrue(value(editor, "readOnly"))
        self.assertTrue(value(editor, "selectByMouse"))
        self.assertTrue(find(temp, "copyLog").isEnabled())
        f.maintenance._results["temp_clean"]["output"] += "\nDiagnostic retained"
        f.maintenance.changed.emit()
        self.assertEqual(temp, find(f.page, "actionLog_temp_clean"))
        self.assertTrue(value(temp, "expanded"))
        self.assertIn("Diagnostic retained", value(editor, "text"))
        self.assertIn("Deleted 50 files...", value(editor, "text"))

    @page_test("performance")
    def test_read_reports_are_selectable_and_do_not_open_details_automatically(self, f):
        f.reader._section_logs = {"performance": "C: measured", "cleanup": "Unrelated read"}
        f.reader.changed.emit()
        panel = next(item for item in descendants(f.page) if item.isVisible()
                     and value(item, "details") == "C: measured")
        self.assertFalse(value(panel, "expanded"))
        find(panel, "toggleLogDetails").click()
        self.assertEqual(value(find(panel, "logDetails"), "text"), "C: measured")
        f.page.setProperty("section", "cleanup")
        self.assertFalse(any(item.isVisible() and value(item, "details") == "C: measured"
                             for item in descendants(f.page)))


if __name__ == "__main__":
    unittest.main()
