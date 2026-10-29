"""Parity contracts anchored on the current V2 CustomTkinter source."""
from pathlib import Path
import unittest

from PySide6.QtCore import QSize
from modules.ui_icons import make_icon, make_windows_icon
from qt_app.icon_provider import NavigationIconProvider


ROOT = Path(__file__).resolve().parents[2]


class V2VisualIdentityTests(unittest.TestCase):
    def test_sidebar_uses_original_glyphs_including_chalice(self):
        original = (ROOT / "panacea_ui.py").read_text(encoding="utf-8")
        shell = (ROOT / "qt_app" / "Main.qml").read_text(encoding="utf-8")
        provider_source = (ROOT / "qt_app" / "icon_provider.py").read_text(encoding="utf-8")
        self.assertIn("self.icons_active[icon]", original)
        self.assertIn("make_icon(name, color, 96)", provider_source)
        provider = NavigationIconProvider()
        for name in ("dashboard", "clean", "tools", "turbo", "resurrect"):
            self.assertIn('icon: "' + name + '"', shell)
            actual = provider.requestImage(name + "/active", QSize(), QSize(96, 96))
            expected = make_icon(name, "#e4c579", 96)
            self.assertEqual((actual.width(), actual.height()), expected.size)
            for y in (8, 24, 48, 72, 88):
                for x in (8, 24, 48, 72, 88):
                    color = actual.pixelColor(x, y)
                    self.assertEqual((color.red(), color.green(), color.blue(), color.alpha()),
                                     expected.getpixel((x, y)), (name, x, y))

    def test_dashboard_icons_and_disk_progress_match_v2(self):
        page = (ROOT / "qt_app" / "ParityPage.qml").read_text(encoding="utf-8")
        provider = NavigationIconProvider()
        for key in ("cpu", "memory", "scan", "updates", "drive", "restore"):
            tint = "#e4c579" if key in ("drive", "restore") else "#76b6e2"
            expected = make_icon(key, tint, 96)
            actual = provider.requestImage(key + "/detail", QSize(), QSize(96, 96))
            self.assertFalse(actual.isNull(), key)
            for x, y in ((10, 10), (24, 40), (48, 48), (70, 70), (88, 88)):
                c = actual.pixelColor(x, y)
                self.assertEqual((c.red(), c.green(), c.blue(), c.alpha()),
                                 expected.getpixel((x, y)), (key, x, y))
        win = provider.requestImage("windows/detail", QSize(), QSize(96, 96))
        self.assertFalse(win.isNull())
        self.assertEqual((win.pixelColor(15, 15).red(),
                          win.pixelColor(15, 15).green(),
                          win.pixelColor(15, 15).blue(),
                          win.pixelColor(15, 15).alpha()),
                         make_windows_icon(size=96).getpixel((15, 15)))
        self.assertIn('modelData.icon + "/detail"', page)
        self.assertIn('visible: modelData.id === "disk"', page)
        self.assertIn('source: "image://panacea-nav/scan/detail"', page)
        self.assertIn('source: "image://panacea-nav/restore/detail"', page)
        self.assertTrue(provider.requestImage("../secrets/detail", QSize(), QSize()).isNull())

    def test_all_original_paired_subviews_are_always_present(self):
        page = (ROOT / "qt_app" / "ParityPage.qml").read_text(encoding="utf-8")
        original = (ROOT / "panacea_ui.py").read_text(encoding="utf-8")
        self.assertIn("def _group_requires_stack", original)
        self.assertIn("function pairedPanelWidth(total, minimum)", page)
        self.assertIn("total >= 2 * minimum + 20", page)
        for threshold in (300, 305, 320):
            self.assertEqual(page.count(f"pairedPanelWidth(pair.width, {threshold})"), 2)
        self.assertEqual(page.count("PPanel {"), 6)
        self.assertNotIn("visible: view.subIndex ===", page)
        self.assertNotIn("onPressed: view.subIndex =", page)
        self.assertIn('iconName: "resurrect"', page)


if __name__ == "__main__":
    unittest.main()
