"""Default Qt window follows the actual current stable V2 desktop dimensions."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class V2ShellGeometryContracts(unittest.TestCase):
    def test_default_window_and_main_header_follow_stable_density(self):
        old = (ROOT / "panacea_ui.py").read_text(encoding="utf-8")
        shell = (ROOT / "qt_app/Main.qml").read_text(encoding="utf-8")
        self.assertIn("self.geometry('1020x680')", old)
        self.assertIn("    width: 1020\n    height: 680", shell)
        self.assertIn("Layout.preferredHeight: 38", shell)
        self.assertIn("Layout.preferredWidth: 302", shell)  # approved sidebar


if __name__ == "__main__":
    unittest.main()
