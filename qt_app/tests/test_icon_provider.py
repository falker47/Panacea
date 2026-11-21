"""Packaged Qt artwork, scaling, system-color tinting and strict URL resolution."""
from pathlib import Path
import unittest

from PySide6.QtCore import QSize
from PySide6.QtGui import QImage

from qt_app.icon_provider import NavigationIconProvider


ROOT = Path(__file__).resolve().parents[2]


class NavigationIconTests(unittest.TestCase):
    def setUp(self):
        self.provider = NavigationIconProvider()

    def test_each_bundled_lucide_mask_keeps_all_source_pixels(self):
        source = ROOT / "assets" / "icons" / "lucide" / "png"
        masks = sorted(source.glob("*.png"))
        self.assertGreaterEqual(len(masks), 11)
        for mask in masks:
            with self.subTest(mask=mask.name):
                expected = QImage(str(mask)).convertToFormat(QImage.Format_Alpha8)
                self.assertFalse(expected.isNull())
                for state in ("active", "idle"):
                    actual = self.provider.requestImage(f"{mask.name}/{state}", QSize(), expected.size())
                    self.assertEqual(actual.convertToFormat(QImage.Format_Alpha8), expected)

    def test_navigation_destinations_have_distinct_visible_artwork_and_accept_system_tints(self):
        names = ("home", "cleanup", "startup", "repair", "performance",
                 "guided", "history", "updates", "settings")
        for size in (24, 30, 36):
            masks = set()
            for name in names:
                with self.subTest(name=name, size=size):
                    reported_size = QSize()
                    image = self.provider.requestImage(f"{name}/ff20c0", reported_size, QSize(size * 2, size))
                    self.assertEqual(reported_size, QSize(size, size))
                    ink = {image.pixelColor(x, y).name() for y in range(size) for x in range(size)
                           if image.pixelColor(x, y).alpha() == 255}
                    self.assertEqual(ink, {"#ff20c0"})
                    masks.add(bytes(image.constBits()))
            self.assertEqual(len(masks), len(names))

    def test_active_and_idle_tints_are_independent_and_keep_their_shape(self):
        size = QSize(48, 48)
        active = self.provider.requestImage("wrench.png/active", QSize(), size)
        idle = self.provider.requestImage("wrench.png/idle", QSize(), size)
        self.assertNotEqual(active, idle)
        self.assertEqual(active.convertToFormat(QImage.Format_Alpha8), idle.convertToFormat(QImage.Format_Alpha8))
        self.assertEqual(active, self.provider.requestImage("repair/active", QSize(), size))

    def test_literal_paths_unknown_symbols_and_invalid_tints_are_rejected(self):
        for name in ("../secrets/active", "wrench.png/../../active", "file:///C:/Windows/open",
                     "wrench.png/unrecognized", "missing.png/active", "home.png/active",
                     "home/ff00", "home/ff00zz", "home/0a0b0c/extra"):
            with self.subTest(name=name):
                self.assertTrue(self.provider.requestImage(name, QSize(), QSize()).isNull())


if __name__ == "__main__":
    unittest.main()
