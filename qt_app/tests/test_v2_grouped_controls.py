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
        for key in ("apps_settings", "appwiz", "startup_settings", "battery_report"):
            self.assertIn('onTriggered: view.request("' + key + '")', page)
        self.assertIn('onPressed: view.request("restore_point")', page)
        self.assertIn("property bool showIndividualCleaning: false", page)
        self.assertIn("component PSectionLog: Rectangle", page)
        self.assertIn("sectionLog.expanded = !sectionLog.expanded", page)

    def test_battery_report_is_in_disk_panel_with_its_log_and_restore_is_not_duplicated(self):
        page = (ROOT / "qt_app/ParityPage.qml").read_text(encoding="utf-8")
        app = (ROOT / "qt_app/main.py").read_text(encoding="utf-8")
        tools = page.split('viewName: "tools"', 1)[1].split('viewName: "disk"', 1)[0]
        disk = page.split('viewName: "disk"', 1)[1].split('id: turboAndStartupSection', 1)[0]
        self.assertNotIn('view.request("restore_point")', tools)
        self.assertNotIn('view.request("battery_report")', tools)
        self.assertIn('onTriggered: view.request("battery_report")', disk)
        self.assertIn('PSectionLog { scope: "disk"', disk)
        self.assertIn('onPressed: view.request("restore_point")', page)
        self.assertIn('"drive_optimize", "chkdsk", "open_defrag", "battery_report"', app)

    def test_windows_update_is_only_in_overview_not_disk_diagnostics(self):
        page = (ROOT / "qt_app/ParityPage.qml").read_text(encoding="utf-8")
        disk = page.split('viewName: "disk"', 1)[1].split('id: turboAndStartupSection', 1)[0]
        self.assertNotIn('action:"windows_update"', disk)
        self.assertNotIn('action:"windows_optional"', disk)
        self.assertIn('onPressed: view.request("windows_update")', page)
        self.assertIn('action:"chkdsk"', disk)

    def test_master_switch_explains_global_activation_and_original_restore(self):
        page = (ROOT / "qt_app/ParityPage.qml").read_text(encoding="utf-8")
        turbo = page.split('id: turboAndStartupSection', 1)[1].split('id: resurrectionSection', 1)[0]
        self.assertIn('objectName: "turboMasterCard"', turbo)
        self.assertIn('view.t("Ottimizzazione completa", "Apply all optimizations")', turbo)
        self.assertIn("cinque ottimizzazioni", turbo)
        self.assertIn("ripristina le impostazioni originali", turbo)
        self.assertIn('view.request(nextValue ? "turbo_on" : "turbo_off")', turbo)
        self.assertIn('interactive: !view.occupied && typeof view.turbo.master === "boolean"', turbo)

    def test_turbo_and_disk_keep_original_compact_focus(self):
        page = (ROOT / "qt_app/ParityPage.qml").read_text(encoding="utf-8")
        self.assertIn("id: turboMasterContent", page)
        self.assertIn("height:turboMasterContent.implicitHeight + 24", page)
        self.assertIn('caption: view.t("Ripristina impostazioni salvate", "Restore saved settings")', page)
        self.assertIn("height: Math.max(width < 390 ? 110 : 52, turboRow.implicitHeight + 16)", page)
        self.assertIn("property bool showDriveChoices: false", page)
        self.assertIn("property bool showExtraDriveTools: false", page)
        self.assertIn("view.selectedDrive = letters[0]", page)
        self.assertIn("row.letter === view.selectedDrive", page)
        self.assertIn('view.request("drive_optimize",view.selectedDrive)', page)
        self.assertIn('action:"chkdsk"', page)
        self.assertIn("visible: view.showExtraDriveTools", page)


if __name__ == "__main__":
    unittest.main()
