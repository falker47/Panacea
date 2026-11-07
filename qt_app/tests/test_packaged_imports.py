"""The package import probe must not create a window or alter Windows."""
from pathlib import Path
import unittest
from unittest.mock import patch

from qt_app.main import main


class PackagedBackendTests(unittest.TestCase):
    def test_probing_imports_never_creates_a_window_or_maintenance_controller(self):
        with patch("qt_app.main.QGuiApplication",
                   side_effect=AssertionError("Cannot start UI for a backend import probe")):
            with patch("qt_app.main.MaintenanceBridge",
                       side_effect=AssertionError("Cannot invoke a maintenance controller")):
                self.assertEqual(main(["--smoke-backend-imports"]), 0)

    def test_windows_workflow_checks_imports_from_frozen_exe(self):
        yml = (Path(__file__).resolve().parents[2] /
               ".github" / "workflows" / "qt-migration.yml").read_text(encoding="utf-8")
        self.assertIn("PanaceaQtCandidate.exe', '--smoke-backend-imports'", yml)


if __name__ == "__main__":
    unittest.main()
