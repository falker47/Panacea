"""No destructive action gets an English-only confirmation in Italian UI."""
import unittest

from qt_app.confirmation_copy import confirmation_text
from qt_app.maintenance import DANGEROUS, MaintenanceService, WARNINGS


class ConfirmationCopyContracts(unittest.TestCase):
    def setUp(self):
        self.gateway = MaintenanceService(platform="not-windows")

    def tearDown(self):
        self.gateway.close()

    def prepared(self, action, drive=""):
        return self.gateway.prepare(action, drive)

    def test_every_dangerous_action_has_an_explicit_italian_warning(self):
        for action in DANGEROUS:
            with self.subTest(action=action):
                warning = self.prepared(action)
                title, details = confirmation_text(action, warning, "it")
                self.assertTrue(title)
                self.assertTrue(details)
                self.assertNotIn("Permanently", details)
                self.assertNotIn("This changes Windows settings", details)
                self.assertNotEqual(details, warning["details"])
                if action in ("temp_clean", "browser_clean", "recycle_empty",
                              "quick_cleanup", "resurrection"):
                    self.assertIn("irreversib", details)

    def test_drive_confirmation_names_the_verified_drive(self):
        data = self.prepared("chkdsk", "C:")
        title, text = confirmation_text("chkdsk", data, "it")
        self.assertTrue(title)
        self.assertIn("Unità selezionata: C:", text)
        self.assertNotIn("Selected drive", text)

    def test_english_and_unknown_changed_warnings_are_never_rewritten(self):
        data = self.prepared("resurrection")
        self.assertEqual(confirmation_text("resurrection", data, "en"),
                         (data["title"], data["details"]))
        changed = dict(data, details=WARNINGS["resurrection"] + " External extra caution.")
        self.assertEqual(confirmation_text("resurrection", changed, "it"),
                         (changed["title"], changed["details"]))

    def test_native_utilities_and_turbo_are_translated(self):
        for action in ("open_defrag", "turbo_on", "power_off"):
            data = self.prepared(action)
            self.assertNotEqual(confirmation_text(action, data, "it")[1], data["details"])


if __name__ == "__main__":
    unittest.main()
