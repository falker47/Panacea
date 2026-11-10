"""No Windows or UAC prompts: command-line argument contract only."""
import subprocess
import unittest

from qt_app.elevation import elevation_arguments


class ElevationArgumentsTests(unittest.TestCase):
    def test_interpreter_relaunch_includes_source_file(self):
        argv = [r"C:\users\test user\Panacea\qt_app\main.py", "--some-arg", "value with spaces"]
        self.assertEqual(elevation_arguments(argv, frozen=False),
                         subprocess.list2cmdline(argv))
        self.assertIn("qt_app", elevation_arguments(argv, frozen=False))

    def test_frozen_relaunch_omits_executable_name(self):
        argv = [r"C:\Program Files\PanaceaQtQA\PanaceaQtCandidate.exe", "--some-arg", "value with spaces"]
        self.assertEqual(elevation_arguments(argv, frozen=True),
                         subprocess.list2cmdline(argv[1:]))
        self.assertNotIn("PanaceaQtCandidate.exe",
                         elevation_arguments(argv, frozen=True))

    def test_missing_program_is_rejected(self):
        with self.assertRaises(ValueError):
            elevation_arguments([], frozen=False)
        with self.assertRaises(ValueError):
            elevation_arguments([""], frozen=True)


if __name__ == "__main__":
    unittest.main()
