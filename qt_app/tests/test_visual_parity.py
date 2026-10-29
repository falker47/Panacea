"""Static regression contracts for the staged Qt visual parity surfaces.

These tests prove wiring/availability, not native pixel equality; true GUI
and Windows-specific behavior is gated separately by the QA workflow.
"""
from pathlib import Path
import re
import unittest

from qt_app.maintenance import ACTIONS, DRIVE_ACTIONS


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "Main.qml"
PARITY = ROOT / "ParityPage.qml"
WORKFLOW = ROOT.parent / ".github" / "workflows" / "qt-migration.yml"


class QtVisualParityContracts(unittest.TestCase):
    def test_group_navigation_keeps_all_original_v2_screens(self):
        shell = APP.read_text(encoding="utf-8")
        page = PARITY.read_text(encoding="utf-8")
        original = (ROOT.parent / "panacea_ui.py").read_text(encoding="utf-8")

        for name in ("Dashboard", "Cleaning", "Tools", "Turbo", "Resurrect"):
            self.assertIn(f'name: "{name}"', shell)
            self.assertIn(f"('{name}', ", original)
        for section in ("dashboardSection", "cleaningAndAppsSection",
                        "toolsAndDiskSection", "turboAndStartupSection",
                        "resurrectionSection"):
            self.assertIn("id: " + section, page)
        self.assertIn('view.t("Applicazioni installate","Installed apps")', page)
        self.assertIn('view.t("Ottimizzazione dischi","Drive optimization")', page)
        self.assertIn('view.t("Applicazioni all\'avvio","Startup apps")', page)
        self.assertNotIn("pageData.cards", shell)
        self.assertNotIn("actionCards[pageLoader.pageIndex]", shell)

    def test_original_brand_system_and_functional_shapes_are_present(self):
        shell = APP.read_text(encoding="utf-8")
        page = PARITY.read_text(encoding="utf-8")
        workflow = WORKFLOW.read_text(encoding="utf-8")
        for color in ("#0b1525", "#0e192b", "#f1f3f8",
                      "#e4c579", "#2e415c"):
            self.assertIn(color, shell + page)
        self.assertIn("panacea_icon.png", shell)
        self.assertIn("lucide/png", shell)
        self.assertIn("Layout.preferredWidth: 302", shell)
        self.assertIn('ParityPage {', shell)
        self.assertIn("PMiniGraph {", page)
        self.assertIn("PProgress {", page)
        self.assertIn("PToggle {", page)
        self.assertIn("id: stepGrid", page)
        self.assertIn("showIndividualCleaning", page)
        self.assertIn("logExpanded", page)
        self.assertIn('Shortcut { sequence: "Ctrl+5"', shell)
        self.assertIn('activeFocusOnTab: interactive', page)
        self.assertIn('qt_app/ParityPage.qml;qt_app', workflow)
        self.assertIn('assets/panacea_icon.png;assets', workflow)
        self.assertIn('assets/icons/lucide/png;assets/icons/lucide/png', workflow)

    def test_all_qml_actions_use_the_confirmed_allowlist(self):
        page = PARITY.read_text(encoding="utf-8")
        literal_calls = set(re.findall(r'view\.request\("([^"]+)"', page))
        row_actions = set(re.findall(r'\baction:"([^"]+)"', page))
        self.assertTrue(literal_calls)
        self.assertTrue(row_actions)
        self.assertFalse((literal_calls | row_actions) - ACTIONS)
        for action in DRIVE_ACTIONS:
            self.assertIn('action:"' + action + '"', page)
        self.assertIn('maintenanceService.prepare(action, drive || "")', page)
        self.assertNotIn("subprocess", page)
        self.assertNotIn("os.system", page)

    def test_qml_uses_structured_live_data_and_progress(self):
        page = PARITY.read_text(encoding="utf-8")
        bridge = (ROOT / "main.py").read_text(encoding="utf-8")
        metrics = (ROOT.parent / "qt_lab" / "main.py").read_text(encoding="utf-8")
        self.assertIn("readService.results", page)
        self.assertIn("maintenanceService.steps", page)
        self.assertIn("maintenanceService.progressDone", page)
        self.assertIn("maintenanceService.cancel()", page)
        for prop in ("results", "progressDone", "progressTotal",
                     "lastAction", "resultStatus", "steps"):
            self.assertIn("def " + prop + "(self):", bridge)
        for metric in ("cpuHistory", "ramHistory", "diskHistory"):
            self.assertIn("def " + metric + "(self):", metrics)

    def test_confirmation_and_package_identity_remain_separate(self):
        shell = APP.read_text(encoding="utf-8")
        bridge = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("maintenanceService.awaitingConfirmation", shell)
        self.assertIn("maintenanceService.confirm()", shell)
        self.assertIn("maintenanceService.reject()", shell)
        self.assertIn("updateService.confirmInstall()", shell)
        self.assertIn("updateService.reject()", shell)
        self.assertIn("onClosing: function(event)", shell)
        self.assertIn('Path(sys.executable).name != "Panacea.exe"', bridge)
        self.assertIn("ShellExecuteW(", bridge)

if __name__ == "__main__":
    unittest.main()
