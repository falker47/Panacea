"""Behavioral geometry checks against actual QML, independent of source spelling."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

PROBE = Path(__file__).with_name("qml_probe.py")


class DashboardRuntimeGeometry(unittest.TestCase):
    def probe(self, width, height, tab=0, scenario="default", language="en"):
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software")
        result = subprocess.run([sys.executable, str(PROBE), str(width), str(height), str(tab), scenario, language],
                                env=env, capture_output=True, text=True, timeout=45, check=True)
        data = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertEqual(data["warnings"], [])
        return data

    def test_legacy_columns_fit_the_observed_compact_window(self):
        data = self.probe(976, 672)
        self.assertEqual(data["windows"][1], data["updates"][1], "Windows Update wrapped below Windows")
        self.assertEqual(len({r[1] for r in data["metrics"]}), 1, "Disk wrapped below CPU/RAM")
        for rect in data["metrics"]:
            self.assertLessEqual(rect[0] + rect[2], 976)

    def test_legacy_dashboard_grid_survives_scaled_logical_viewports(self):
        for width in (760, 781, 911):
            with self.subTest(width=width):
                data = self.probe(width, 512)
                self.assertEqual(data["windows"][1], data["updates"][1])
                self.assertEqual(len({r[1] for r in data["metrics"]}), 1)
                self.assertEqual(data["horizontal_overflow"], [])

    def test_guided_steps_follow_the_legacy_responsive_columns(self):
        for width, columns in ((976, 3), (1366, 3), (1920, 5), (760, 1)):
            with self.subTest(width=width):
                steps = self.probe(width, 768, 4)["steps"]
                self.assertEqual(len(steps), 10)
                self.assertEqual(len({r[0] for r in steps}), columns)
                self.assertLess(steps[0][0], steps[1][0]) if columns > 1 else None

    def test_expanded_secondary_surfaces_remain_inside_compact_viewports(self):
        for width in (760, 976):
            for tab in (1, 2, 3, 4):
                with self.subTest(width=width, tab=tab):
                    data = self.probe(width, 672, tab, "expanded", "it")
                    self.assertEqual(data["horizontal_overflow"], [])

    def test_guided_warning_fits_its_panel_at_minimum_width(self):
        data = self.probe(760, 480, 4)
        self.assertLessEqual(data["warning_content_height"], data["warning_panel_height"])

    def test_group_reflow_uses_the_legacy_scroller_width(self):
        cleaning = self.probe(976, 672, 1)["panels"]
        tools = self.probe(976, 672, 2)["panels"]
        self.assertEqual(cleaning[0][1], cleaning[1][1], "Cleanup and Apps should fit together")
        self.assertLess(tools[0][1], tools[1][1], "Tools and Disk should stack at this viewport")

    def test_long_confirmation_remains_readable_in_a_compact_window(self):
        data = self.probe(760, 480, 0, "confirmation")
        self.assertTrue(data["confirmation_scrollable"] or data["confirmation_readable_height"])

    def test_narrow_turbo_toggle_sits_below_the_description(self):
        row = self.probe(760, 672, 3)["turbo_layout"]
        self.assertGreater(row["toggle"][1], row["title"][1] + row["title"][3])

    def test_group_heading_stays_visible_when_scrolling_to_disk(self):
        header = self.probe(976, 672, 2, "scrolled")["group_heading"]
        self.assertGreaterEqual(header[1], 0)

    def test_drive_menu_does_not_reflow_the_optimization_panel(self):
        closed = self.probe(976, 672, 2)["drive_card_height"]
        opened = self.probe(976, 672, 2, "drive-choices")["drive_card_height"]
        self.assertEqual(opened, closed)

    def test_master_switch_matches_legacy_order_and_compact_stacking(self):
        wide = self.probe(976, 672, 3)["master_layout"]
        self.assertLess(wide["toggle"][0], wide["state"][0])
        narrow = self.probe(760, 672, 3)["master_layout"]
        self.assertGreaterEqual(narrow["toggle"][1], narrow["title"][1] + narrow["title"][3])

    def test_stopped_sequence_marks_unattempted_phases_as_not_run(self):
        for state, count in (("cancelled", 8), ("failed", 9)):
            with self.subTest(state=state):
                labels = self.probe(976, 672, 4, state)["phase_states"]
                self.assertEqual(labels.count("Not run"), count)
                self.assertNotIn("Not started", labels)


if __name__ == "__main__":
    unittest.main()
