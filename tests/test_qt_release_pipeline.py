"""Production-cutover regression contracts. No Windows mutations."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class QtProductionReleaseContracts(unittest.TestCase):
    def test_release_version_and_native_build_use_qt_not_legacy_tk(self):
        version = (ROOT / "version.py").read_text(encoding="utf-8")
        spec = (ROOT / "Panacea.spec").read_text(encoding="utf-8")
        dependencies = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        self.assertIn('VERSION = "2.1.0"', version)
        self.assertIn("['qt_app/main.py']", spec)
        for path in ("qt_app/Main.qml", "qt_app/ParityPage.qml",
                     "assets/panacea_icon.ico", "assets/panacea_icon.png"):
            self.assertIn(path, spec)
        self.assertIn("modules.update_install", spec)
        self.assertIn("modules.maintenance_guard", spec)
        self.assertNotIn("collect_all('customtkinter')", spec)
        self.assertIn("PySide6==6.10.2", dependencies)
        self.assertIn("pyinstaller==6.22.3", dependencies)

    def test_production_ui_uses_current_version_and_not_static_qa_branding(self):
        ui = (ROOT / "qt_app/Main.qml").read_text(encoding="utf-8")
        bridge = (ROOT / "qt_app/update_bridge.py").read_text(encoding="utf-8")
        self.assertIn("updateService.currentVersion", ui)
        self.assertIn("updateService.eligible", ui)
        self.assertNotIn('title: "Panacea 2.0.2 · Qt QA"', ui)
        self.assertNotIn('text: "v2.0.2 QA"', ui)
        self.assertIn("self._flow.install_eligible", bridge)

    def test_stable_installer_keeps_identity_and_all_release_asset_names(self):
        installer = (ROOT / "packaging/Panacea.iss").read_text(encoding="utf-8")
        build = (ROOT / "scripts/build_installer.py").read_text(encoding="utf-8")
        workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("AppId={{B6C0FB10-27BC-4E6F-9078-40F9E8B49B2D}", installer)
        self.assertIn('DestName: "Panacea.exe"', installer)
        for name in ("Panacea.exe", "Panacea.exe.sha256",
                     "PanaceaSetup.exe", "PanaceaSetup.exe.sha256"):
            self.assertIn(name, workflow)
        self.assertIn("validate_portable(exe, checksum)", build)
        self.assertIn("python -m unittest discover -s qt_app/tests", workflow)
        self.assertIn("--smoke-backend-imports", workflow)

    def test_old_installed_v202_to_qt_and_rollback_are_run_on_disposable_windows(self):
        workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("v2.0.2", workflow)
        self.assertIn("hosted_windows_release_probe.py", workflow)
        self.assertIn("PANACEA_ALLOW_HOSTED_PROBE", workflow)
        self.assertIn("hosted_installer_probe.py", workflow)

    def test_native_qt_window_probe_must_not_force_hidden_startup(self):
        harness = (ROOT / "scripts/packaged_probe.py").read_text(encoding="utf-8")
        self.assertNotIn("STARTF_USESHOWWINDOW", harness)
        self.assertIn("subprocess.Popen([str(executable), '--smoke-test'])", harness)
        self.assertIn("usable_candidate_window(executable)", harness)

    def test_release_notes_and_manual_draft_workflow_exist(self):
        notes = ROOT / "docs/releases/2.1.0.md"
        self.assertTrue(notes.is_file())
        body = notes.read_text(encoding="utf-8")
        self.assertIn("Qt Quick", body)
        self.assertIn("2.0.2", body)
        self.assertIn("Panacea.exe", body)
        self.assertIn("rollback", body.lower())
        release = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", release)
        self.assertIn("--draft", release)
        self.assertIn("python -m unittest discover -s qt_app/tests", release)


if __name__ == "__main__":
    unittest.main()
