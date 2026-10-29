"""Qt migration QA contracts: five V2 groups, safe confirmations and screenshots."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class UiContractTests(unittest.TestCase):
    def test_qa_shell_exposes_full_v2_views_without_bypassing_confirmation(self):
        qml = (ROOT / "Main.qml").read_text(encoding="utf-8")
        page = (ROOT / "ParityPage.qml").read_text(encoding="utf-8")
        self.assertIn("ParityPage {", qml)
        self.assertIn('groupIndex: contentLoader.groupIndex', qml)
        self.assertIn("readService.results", page)
        self.assertIn("readService.driveLetters", page)
        for metric in ('liveMetrics.cpu', 'liveMetrics.ram', 'liveMetrics.disk'):
            self.assertIn(metric, page)
        self.assertIn("activeFocusOnTab: true", qml)
        self.assertIn("onClosing: function(event)", qml)
        self.assertIn("maintenanceService.prepare(action, drive || \"\")", page)
        self.assertIn("maintenanceService.confirm()", qml)
        self.assertIn("updateService.status", qml)
        self.assertIn("updateService.prepareInstall()", qml)
        self.assertIn("updateService.confirmInstall()", qml)
        self.assertIn("updateService.cancelDownload()", qml)
        self.assertIn("readService.request", page)
        self.assertIn("readService.busy", page)
        self.assertNotIn("maintenanceBridge.execute", qml + page)
        self.assertNotIn("pageData.cards", qml + page)

    def test_packaging_entrypoint_stays_distinct_from_stable_main(self):
        app = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("Panacea Qt UI migration QA", app)
        # The frozen production identity supports the verified legacy helper,
        # but a QA candidate cannot acknowledge or install a production update.
        self.assertIn("run_update_helper(", app)
        self.assertIn('Path(sys.executable).name != "Panacea.exe"', app)
        self.assertIn("ShellExecuteW(", app)
        self.assertIn("not args.smoke_test", app)
        self.assertIn('setContextProperty("updateService"', app)

    def test_smoke_capture_uses_supported_qscreen_api(self):
        app = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("screen.grabWindow(", app)
        self.assertNotIn("engine.rootObjects()[0].grabWindow()", app)

    def test_five_primary_destinations_survive(self):
        qml = (ROOT / "Main.qml").read_text(encoding="utf-8")
        for section in ("Dashboard", "Cleaning", "Tools", "Turbo", "Resurrect"):
            self.assertIn('name: "' + section + '"', qml)

if __name__ == "__main__":
    unittest.main()
