"""Cleaning and app-shortcut visual structure matches the current CTk V2."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class V2CleanupCardsTests(unittest.TestCase):
    def test_quick_cleanup_is_the_primary_compact_action(self):
        qml = (ROOT / "qt_app/ParityPage.qml").read_text(encoding="utf-8")
        stable = (ROOT / "panacea_ui.py").read_text(encoding="utf-8")
        self.assertIn("self.quick_cleanup_button", stable)
        self.assertIn("id: quickContent", qml)
        self.assertIn("primary: true", qml)
        self.assertIn('iconName: "clean"', qml)
        self.assertIn('onTriggered: view.request("quick_cleanup")', qml)
        self.assertIn("property bool showIndividualCleaning: false", qml)
        self.assertIn("visible: view.showIndividualCleaning", qml)
        self.assertIn("id: appLinks", qml)
        self.assertIn("id: startupLinks", qml)


if __name__ == "__main__":
    unittest.main()
