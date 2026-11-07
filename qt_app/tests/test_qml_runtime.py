"""Behavioral geometry checks against actual QML, independent of source spelling."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

PROBE = Path(__file__).with_name("qml_probe.py")


class DashboardRuntimeGeometry(unittest.TestCase):
    def probe(self, width, height, tab=0):
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software")
        result = subprocess.run([sys.executable, str(PROBE), str(width), str(height), str(tab)],
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

    def test_guided_steps_follow_the_legacy_responsive_columns(self):
        for width, columns in ((976, 3), (1366, 3), (1920, 5), (760, 1)):
            with self.subTest(width=width):
                steps = self.probe(width, 768, 4)["steps"]
                self.assertEqual(len(steps), 10)
                self.assertEqual(len({r[0] for r in steps}), columns)
                self.assertLess(steps[0][0], steps[1][0]) if columns > 1 else None


if __name__ == "__main__":
    unittest.main()
