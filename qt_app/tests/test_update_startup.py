"""Initial release discovery only checks metadata after the runtime is idle."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from qt_app.main import _check_initial_release_when_idle


class InitialReleaseCheckTests(unittest.TestCase):
    def test_busy_startup_defers_check_without_repeating_download_or_install(self):
        calls = []
        reader = SimpleNamespace(busy=True)
        maintenance = SimpleNamespace(busy=False)
        updater = SimpleNamespace(_closed=False, busy=False, pending=False,
                                  check=lambda: calls.append("check"))
        with patch("qt_app.main.QTimer.singleShot") as schedule:
            self.assertFalse(_check_initial_release_when_idle(reader, maintenance, updater))
            self.assertEqual(calls, [])
            schedule.assert_called_once()
            reader.busy = False
            schedule.call_args.args[1]()
            self.assertEqual(calls, ["check"])

    def test_idle_checker_never_checks_after_app_shutdown(self):
        calls = []
        updater = SimpleNamespace(_closed=True, busy=False, pending=False,
                                  check=lambda: calls.append("check"))
        with patch("qt_app.main.QTimer.singleShot") as schedule:
            self.assertFalse(_check_initial_release_when_idle(
                SimpleNamespace(busy=False), SimpleNamespace(busy=False), updater))
            self.assertEqual(calls, [])
            schedule.assert_not_called()

    def test_release_check_is_one_shot_metadata_only_and_never_an_install(self):
        source = ( __import__("pathlib").Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8")
        self.assertIn("QTimer.singleShot(2000, lambda: _check_initial_release_when_idle", source)
        self.assertNotIn("updater.confirmInstall()", source)
