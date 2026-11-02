"""The V2 graph has an honest sixty-point plot, guides and original fills."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class V2GraphRenderingContracts(unittest.TestCase):
    def test_qt_graph_style_and_history_density_match_the_stable(self):
        stable = (ROOT / "panacea_ui.py").read_text(encoding="utf-8")
        page = (ROOT / "qt_app/ParityPage.qml").read_text(encoding="utf-8")
        self.assertIn("self.points = [0.0] * 60", stable)
        self.assertIn("for percent in (25, 50, 75):", stable)
        self.assertIn('fill=\'#3b342b\' if line_color == COL_GOLD else \'#24364c\'', stable)
        self.assertIn("i < 60 - length ? 0", page)
        self.assertIn("level <= 75; level += 25", page)
        self.assertIn('goldFill ? "#3b342b" : "#24364c"', page)
        self.assertIn('goldFill: modelData.id === "ram"', page)


if __name__ == "__main__":
    unittest.main()
