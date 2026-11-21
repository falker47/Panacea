"""Production entry point, import closure and QML action boundary."""
from pathlib import Path
import os
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]


class UiContractTests(unittest.TestCase):
    def test_runtime_imports_through_real_smoke_and_backend_probe(self):
        script = """
import importlib.abc
import sys
class ImportAudit(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname.split('.')[0] in ('PIL', 'qt_lab'):
            raise AssertionError(f'Unexpected desktop runtime import: {fullname}')
sys.meta_path.insert(0, ImportAudit())
from qt_app.main import main
assert main(['--smoke-backend-imports']) == 0
assert main(['--smoke-test']) == 0
assert not {'PIL', 'qt_lab'}.intersection(sys.modules)
"""
        result = subprocess.run([sys.executable, "-c", script], cwd=ROOT, capture_output=True, timeout=30,
                                env=dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_shell_uses_confirmed_bridges_and_preserves_frozen_entrypoint(self):
        app = (ROOT / "qt_app/main.py").read_text(encoding="utf-8")
        shell = (ROOT / "qt_app/Main.qml").read_text(encoding="utf-8")
        self.assertIn("run_update_helper(args.panacea_update_helper)", app)
        self.assertIn('Path(sys.executable).name != "Panacea.exe"', app)
        self.assertIn("ShellExecuteW(", app)
        self.assertIn("onClosing: function(event)", shell)
        self.assertIn("maintenanceService.confirm()", shell)
        self.assertIn("updateService.confirmInstall()", shell)
        sources = [shell, *(p.read_text(encoding="utf-8") for p in (ROOT/"qt_app/qml").rglob("*.qml"))]
        for code in sources:
            self.assertNotIn("Service.execute(", code)
            self.assertNotIn("subprocess", code)
