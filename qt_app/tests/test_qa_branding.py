"""The QA exe, shortcut, installer and Qt window use the original Panacea icon."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class QABrandIconTests(unittest.TestCase):
    def test_executable_branding_is_embedded_not_just_window_image(self):
        workflow = (ROOT / ".github/workflows/qt-migration.yml").read_text(encoding="utf-8")
        app = (ROOT / "qt_app/main.py").read_text(encoding="utf-8")
        setup = (ROOT / "qt_app/packaging/PanaceaQtQA.iss").read_text(encoding="utf-8")
        self.assertTrue((ROOT / "assets/panacea_icon.ico").is_file())
        self.assertIn('--icon "assets/panacea_icon.ico"', workflow)
        spec = (ROOT / "Panacea.spec").read_text(encoding="utf-8")
        self.assertIn("panacea_icon.ico", spec)
        self.assertIn("--clean Panacea.spec", workflow)
        self.assertIn('--add-data "assets/panacea_icon.ico;assets"', workflow)
        self.assertIn('("assets/panacea_icon.ico", "assets")', spec)
        self.assertIn('app.setWindowIcon(QIcon(str(icon)))', app)
        self.assertIn('SetupIconFile={#QtBrandIcon}', setup)
        self.assertIn('"/DQtBrandIcon=$brandIcon"', workflow)


if __name__ == "__main__":
    unittest.main()
