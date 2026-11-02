"""V2 layout controls remain compact and require explicit action confirmations."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class V2GroupedControls(unittest.TestCase):
    def test_original_settings_shortcuts_and_collapsed_cleaning(self):
        page = (ROOT / "qt_app/ParityPage.qml").read_text(encoding="utf-8")
        stable = (ROOT / "panacea_ui.py").read_text(encoding="utf-8")
        self.assertIn("def _settings_shortcuts", stable)
        self.assertIn("component PShortcut: Rectangle", page)
        self.assertIn("Keys.onReturnPressed: activate()", page)
        self.assertIn("Keys.onSpacePressed: activate()", page)
        for key in ("apps_settings", "appwiz", "startup_settings",
                    "restore_point", "battery_report"):
            self.assertIn('onTriggered: view.request("' + key + '")', page)
        self.assertIn("property bool showIndividualCleaning: false", page)
        self.assertIn("component PSectionLog: Rectangle", page)
        self.assertIn("sectionLog.expanded = !sectionLog.expanded", page)

    def test_turbo_and_disk_keep_original_compact_focus(self):
        page = (ROOT / "qt_app/ParityPage.qml").read_text(encoding="utf-8")
        self.assertIn("id: turboMasterContent", page)
        self.assertIn("height:turboMasterContent.implicitHeight + 24", page)
        self.assertIn('caption: view.t("Ripristina impostazioni salvate", "Restore saved settings")', page)
        self.assertIn("height: width < 390 ? 92 : 62", page)
        self.assertIn("property bool showDriveChoices: false", page)
        self.assertIn("property bool showExtraDriveTools: false", page)
        self.assertIn("view.selectedDrive = letters[0]", page)
        self.assertIn("row.letter === view.selectedDrive", page)
        self.assertIn('action:"drive_optimize"', page)
        self.assertIn('action:"chkdsk"', page)
        self.assertIn("visible: view.showExtraDriveTools", page)


if __name__ == "__main__":
    unittest.main()
