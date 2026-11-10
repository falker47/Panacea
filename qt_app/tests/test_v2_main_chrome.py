"""Qt chrome follows the current V2 stable capture, without losing QA controls."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class V2MainChromeTests(unittest.TestCase):
    def test_main_content_starts_at_v2_position(self):
        ui = (ROOT / "qt_app/Main.qml").read_text(encoding="utf-8")
        page = (ROOT / "qt_app/ParityPage.qml").read_text(encoding="utf-8")
        stable = (ROOT / "panacea_ui.py").read_text(encoding="utf-8")
        self.assertIn("self.geometry('1020x680')", stable)
        self.assertIn("    width: 1020\n    height: 680", ui)
        self.assertNotIn("Layout.preferredHeight: 38", ui)
        self.assertIn("y: view.groupIndex === 0 ? 16 : view.groupIndex === 4 ? 12 : 10", page)
        self.assertIn("Layout.preferredHeight: 30", ui)
        self.assertIn("Layout.preferredWidth: 302", ui)

    def test_brand_uses_available_sidebar_width_without_changing_navigation(self):
        shell = (ROOT / "qt_app/Main.qml").read_text(encoding="utf-8")
        self.assertIn('Layout.preferredWidth: shell.height < 620 ? 74 : 82', shell)
        self.assertIn('font.pixelSize: shell.height < 620 ? 32 : 38', shell)
        self.assertIn('font.pixelSize: shell.height < 620 ? 11 : 12', shell)
        self.assertIn('Layout.preferredWidth: 302', shell)
        self.assertEqual(shell.count('icon: "dashboard"'), 1)
        self.assertEqual(shell.count('icon: "resurrect"'), 1)

    def test_sidebar_brand_is_centered_without_overflow_at_compact_and_regular_sizes(self):
        shell = (ROOT / "qt_app/Main.qml").read_text(encoding="utf-8")
        for name in ("brandLogo", "brandWordmark", "brandTagline"):
            self.assertIn('objectName: "' + name + '"', shell)
        self.assertIn("Layout.alignment: Qt.AlignVCenter", shell)

    def test_update_and_language_controls_remain_keyboard_operable(self):
        shell = (ROOT / "qt_app/Main.qml").read_text(encoding="utf-8")
        self.assertIn("updateService.check()", shell)
        self.assertIn('shell.language = shell.language === "it" ? "en" : "it"', shell)
        self.assertIn("Accessible.role: Accessible.Button", shell)
        self.assertIn("Keys.onSpacePressed: activate()", shell)


if __name__ == "__main__":
    unittest.main()
