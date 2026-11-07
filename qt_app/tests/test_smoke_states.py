"""Visual fixture CLI must exit, preserve warnings and remain smoke-only."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

MAIN = Path(__file__).resolve().parents[1] / "main.py"


class SmokeStates(unittest.TestCase):
    def test_fixture_arguments_are_rejected_before_interactive_startup(self):
        result = subprocess.run([sys.executable, str(MAIN), "--smoke-scenario", "running"],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 2)
        self.assertIn("require --smoke-test", result.stderr)

    def test_running_fixture_captures_and_exits_without_starting_maintenance(self):
        with tempfile.TemporaryDirectory() as directory:
            capture = Path(directory) / "running.png"
            result = subprocess.run([sys.executable, str(MAIN), "--smoke-test", "--smoke-tab", "4",
                                     "--smoke-scenario", "running", "--capture", str(capture)],
                                    env=dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software"),
                                    capture_output=True, text=True, timeout=45)
            trace = capture.with_suffix(".lifecycle.log").read_text(encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stderr + trace)
            data = json.loads(capture.with_suffix(".json").read_text(encoding="utf-8"))
            self.assertEqual(data["scenario"], "running")
            self.assertTrue(data["visual_fixture"])
            self.assertEqual(data["qml_warnings"], [])
            trace = capture.with_suffix(".lifecycle.log").read_text(encoding="utf-8")
            self.assertIn("capture saved", trace)
            self.assertIn("fixture page configured", trace)
            self.assertIn("event loop exited", trace)
