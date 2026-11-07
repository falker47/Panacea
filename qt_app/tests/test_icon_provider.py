"""The five original Lucide navigation masks must remain visible on navy."""
from pathlib import Path
import unittest

from PySide6.QtCore import QSize
from qt_app.icon_provider import NavigationIconProvider


ROOT = Path(__file__).resolve().parents[2]


class NavigationIconTests(unittest.TestCase):
    def test_shipped_source_assets_exist(self):
        source = ROOT / "assets" / "icons" / "lucide" / "png"
        for name in ("layout-dashboard.png", "brush-cleaning.png",
                     "wrench.png", "zap.png", "shield-plus.png"):
            self.assertTrue((source / name).is_file(), name)

    def test_active_and_idle_navigation_masks_preserve_shape(self):
        provider = NavigationIconProvider()
        for name in ("layout-dashboard.png", "brush-cleaning.png",
                     "wrench.png", "zap.png", "shield-plus.png"):
            result = []
            for state in ("active", "idle"):
                image = provider.requestImage(name + "/" + state, QSize(), QSize(48, 48))
                self.assertFalse(image.isNull(), (name, state))
                self.assertEqual(image.width(), 48)
                self.assertEqual(image.height(), 48)
                colored_pixels = [
                    image.pixelColor(x, y).name()
                    for y in range(48) for x in range(48)
                    if image.pixelColor(x, y).alpha() > 180
                ]
                self.assertTrue(colored_pixels, (name, state))
                result.append(colored_pixels)
            self.assertNotEqual(result[0][0], result[1][0])

    def test_paths_are_allowlisted(self):
        provider = NavigationIconProvider()
        for dangerous in ("../secrets/active", "wrench.png/../../active",
                          "wrench.png/unrecognized", "missing.png/active"):
            self.assertTrue(provider.requestImage(dangerous, QSize(), QSize()).isNull())


if __name__ == "__main__":
    unittest.main()
