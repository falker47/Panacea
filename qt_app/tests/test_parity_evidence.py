"""A/B evidence must preserve image dimensions and never imply visual approval."""
from pathlib import Path
import tempfile
import unittest

from PIL import Image


class EvidenceComparison(unittest.TestCase):
    def test_mismatched_images_are_reported_without_resizing(self):
        from qt_app.parity_matrix import compare_images
        with tempfile.TemporaryDirectory() as location:
            root = Path(location)
            a, b = root / "legacy.png", root / "qt.png"
            Image.new("RGB", (100, 80), "black").save(a)
            Image.new("RGB", (120, 80), "white").save(b)
            result = compare_images(a, b, root / "pair")
            self.assertFalse(result["same_dimensions"])
            self.assertIsNone(result["mean_rgb_difference"])
            self.assertEqual(result["status"], "diagnostic_only_not_approved")
            self.assertFalse((root / "pair-diff.png").exists())
