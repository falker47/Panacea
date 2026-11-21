"""Section reads queue across visits, and uncertain machine state disables mutations."""
import unittest

from qt_app.tests.qml_probe import probe


class ReadLifecycleQmlTests(unittest.TestCase):
    def test_busy_page_visits_forward_reads_once_after_the_active_read(self):
        for language in ("it", "en"):
            data = probe("lifecycle", language)
            self.assertEqual(data["queued"], ["drives", "turbo_status"])
            self.assertEqual(data["processed"], data["queued"])
            self.assertTrue(data["blocked"])

    def test_active_read_is_visible_in_both_languages(self):
        self.assertIn("Lettura", probe("lifecycle", "it")["active_text"])
        self.assertIn("Reading", probe("lifecycle")["active_text"])

    def test_restore_and_drive_actions_require_measured_state(self):
        for language in ("it", "en"):
            data = probe("lifecycle", language)
            self.assertEqual(data["restore"], [False, False, True])
            self.assertTrue(data["drive_disabled"])
