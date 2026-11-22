"""Visual fixture CLI must exit, preserve warnings and remain smoke-only."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

MAIN = Path(__file__).resolve().parents[1] / "main.py"
ROOT = MAIN.parents[1]
# Run the real smoke capture in a window that is never exposed (hidden, minimized or a locked
# session on a developer PC). No frame ever runs the polish pass that positions Qt Quick Layouts.
UNEXPOSED = """
import sys
sys.path.insert(0, sys.argv[1])
import qt_app.main as entry
import qt_app.qa_fixtures as fixtures
run_smoke = fixtures.run_smoke
def hidden(app, window, *args):
    window.hide()
    return run_smoke(app, window, *args)
fixtures.run_smoke = hidden
raise SystemExit(entry.main(sys.argv[2:]))
"""


class SmokeStates(unittest.TestCase):
    def test_unexposed_window_is_measured_after_layout_and_features_settle(self):
        with tempfile.TemporaryDirectory() as directory:
            capture = Path(directory) / "section.png"
            result = subprocess.run([sys.executable, "-c", UNEXPOSED, str(ROOT), "--smoke-test", "--smoke-all-sections",
                                     "--smoke-language", "en", "--capture", str(capture)],
                                    env=dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software"),
                                    capture_output=True, text=True, timeout=90)
            self.assertEqual(result.returncode, 0, result.stdout[-3000:] + result.stderr[-3000:])
            reports = {path.stem: json.loads(path.read_text(encoding="utf-8"))["geometry"]
                       for path in Path(directory).glob("*.json")}
            self.assertEqual(set(reports), {"home", "cleanup", "startup", "repair", "performance", "guided",
                                            "history", "updates", "settings"})
            for section, report in reports.items():
                self.assertEqual(report["errors"], [], section)
            # Optional features compile asynchronously; the evidence must include them, not a half-built page.
            self.assertIn("Deep cleanup", reports["cleanup"]["text"])
            self.assertIn("Storage analysis", reports["cleanup"]["text"])
            rows = sorted(box for box in reports["cleanup"]["keyItems"] if box[0].startswith("action_")
                          and box[0] != "action_quick_cleanup")
            self.assertEqual(len({box[2] for box in rows}), len(rows), rows)


    def test_profile_measures_every_actual_qml_section_cold_and_warm(self):
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory) / "profile.json"
            result = subprocess.run([sys.executable, str(MAIN), "--smoke-test", "--smoke-profile", str(profile)],
                                    env=dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software"),
                                    capture_output=True, text=True, timeout=45)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(profile.read_text(encoding="utf-8"))
            self.assertEqual([r["tab"] for r in data["navigation"]], list(range(9)) * 2)
            self.assertTrue(data["fixture_only"])

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
