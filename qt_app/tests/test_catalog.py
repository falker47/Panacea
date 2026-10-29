"""Contract: Qt cards list every allowed operation and never invent a command."""
import unittest

from qt_app.catalog import ENTRIES, GROUPS, cards
from qt_app.maintenance import ACTIONS


class CatalogTests(unittest.TestCase):
    def test_all_supported_operations_have_a_visible_card(self):
        keys = {key for group in GROUPS for key in group}
        self.assertEqual(keys, set(ENTRIES))
        self.assertEqual(keys - {"cpu", "ram", "disk"}, ACTIONS)

    def test_pages_localize_without_changing_action_identifiers(self):
        italian, english = cards("it"), cards("en")
        self.assertEqual(len(italian), 5)
        self.assertEqual(len(english), 5)
        self.assertNotEqual(italian[1][0]["title"], english[1][0]["title"])
        self.assertEqual(italian[0][0]["metric"], "cpu")
        self.assertEqual(italian[0][0]["action"], "")
        self.assertEqual(english[2][0]["action"], "sfc")
        self.assertEqual(english[4][0]["action"], "resurrection")

    def test_all_other_buttons_are_explicitly_confirmation_only(self):
        for page in cards():
            for card in page:
                self.assertEqual(card["action"] in ACTIONS, card["badge"] == "ACTION")
                self.assertFalse("shell" in card["action"] or "&" in card["action"])


if __name__ == "__main__":
    unittest.main()
