"""Require equal dimensions when comparing current V2 and Qt captures."""
from pathlib import Path
import unittest


class CurrentV2ComparisonContracts(unittest.TestCase):
    def test_workflow_uses_actual_native_stable_dimensions(self):
        root = Path(__file__).resolve().parents[2]
        flow = (root / ".github/workflows/qt-migration.yml").read_text(encoding="utf-8")
        self.assertIn('$actualWidth = [int]$view.pixels[0]', flow)
        self.assertIn('$actualHeight = [int]$view.pixels[1]', flow)
        self.assertIn("--smoke-width $actualWidth --smoke-height $actualHeight", flow)
        self.assertIn("qt_app/current_v2_compare.py", flow)

    def test_comparison_refuses_resize_masquerading_as_parity(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "current_v2_compare.py").read_text(encoding="utf-8")
        self.assertIn("reference.size != current.size", source)
        self.assertIn("current_reference_is_fresh(", source)
        self.assertIn("diagnostic_only_not_approved", source)
        self.assertNotIn("Image.Resampling", source)


if __name__ == "__main__":
    unittest.main()
