"""Smoke coverage must include every QML group, both locales, six DPI cases."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class VisualMatrixContracts(unittest.TestCase):
    def test_smoke_pages_are_loaded_not_just_shell(self):
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        shell = (ROOT / "Main.qml").read_text(encoding="utf-8")
        page = (ROOT / "ParityPage.qml").read_text(encoding="utf-8")
        for name in ("--smoke-width", "--smoke-height",
                     "--smoke-language", "--smoke-tab"):
            self.assertIn(name, main)
        self.assertIn('window.property("loadedMask")', main)
        self.assertIn("onLoaded:", shell)
        self.assertIn("loadedMask", shell)
        self.assertIn('objectName: "parityPage_" + groupIndex', page)
        self.assertIn("window.grabWindow()", main)
        self.assertIn("screen.grabWindow(", main)
        self.assertIn('setContextProperty("qaSmokeMode"', main)
        self.assertIn("!qaSmokeMode", shell)
        self.assertIn("not args.smoke_test", main)

    def test_ci_captures_all_v2_viewport_scale_language_combinations(self):
        workflow = (ROOT.parent / ".github" / "workflows" / "qt-migration.yml").read_text(encoding="utf-8")
        self.assertIn("Capture V2 visual review matrix", workflow)
        self.assertIn('w=1366; h=768', workflow)
        self.assertIn('w=1920; h=1080', workflow)
        self.assertIn('"1", "1.25", "1.5"', workflow)
        self.assertIn('QT_QPA_PLATFORM = "offscreen"', workflow)
        self.assertIn("foreach ($tab in @(0,1,2,3,4))", workflow)
        self.assertIn("--smoke-language it", workflow)
        self.assertIn("--smoke-language en", workflow)
        self.assertIn("visual_review.py", workflow)
        self.assertIn("visual-parity-contact-sheet", (ROOT / "visual_review.py").read_text(encoding="utf-8"))
        self.assertIn("build/qt-app/*.jpg", workflow)

if __name__ == "__main__":
    unittest.main()
