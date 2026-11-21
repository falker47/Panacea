"""The real QML sheet supplies consent to the one-use fixture broker."""
import unittest

from qt_app.tests.qml_probe import probe


class ConfirmationSheetTests(unittest.TestCase):
    def test_safe_default_escape_and_stale_decision_never_execute(self):
        for language in ("it", "en"):
            result = probe("consent", language)
            self.assertEqual(result["after_reject"], 0)
            self.assertEqual(result["after_stale"], 0)
            self.assertEqual(result["executions"], 1)

    def test_focus_stays_in_modal_sheet_and_irreversibility_is_visible(self):
        for language, warning in (("en", "cannot be undone"), ("it", "irreversibile")):
            result = probe("consent", language)
            self.assertIn(warning, result["body"])
            self.assertEqual(result["cycle"], ["confirmConfirmation", "cancelConfirmation"] * 2)
