"""The QA installer must never share the production install identity or path."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]


class QaInstallerContracts(unittest.TestCase):
    def test_installation_is_strictly_side_by_side(self):
        stable = (ROOT / "packaging/Panacea.iss").read_text(encoding="utf-8")
        candidate = (ROOT / "qt_app/packaging/PanaceaQtQA.iss").read_text(encoding="utf-8")
        app_id = re.compile(r"(?im)^AppId\s*=\s*(\S+)")
        self.assertNotEqual(app_id.search(stable).group(1), app_id.search(candidate).group(1))
        self.assertIn(r"DefaultDirName={autopf}\PanaceaQtQA", candidate)
        self.assertIn("UsePreviousAppDir=no", candidate)
        self.assertIn("CloseApplications=no", candidate)
        self.assertIn("PrivilegesRequired=admin", candidate)
        self.assertIn(r'Source: "{#QtCandidateDir}\*"', candidate)
        self.assertIn("recursesubdirs createallsubdirs", candidate)
        self.assertNotIn('DestName: "Panacea.exe"', candidate)
        self.assertIn("PanaceaQtCandidate.exe", candidate)

    def test_silent_installer_waits_and_has_diagnostic_log(self):
        workflow = (ROOT / ".github/workflows/qt-migration.yml").read_text(encoding="utf-8")
        self.assertIn('"/SP-"', workflow)
        self.assertIn('Start-Process -FilePath $setup', workflow)
        self.assertIn(' -Wait -PassThru', workflow)
        self.assertIn("qa-install.log", workflow)
        self.assertIn("qa-uninstall.log", workflow)
        self.assertIn("Inno exit code", workflow)

    def test_qa_installer_not_in_stable_build_pipeline(self):
        ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertNotIn("PanaceaQtQA.iss", ci)
        self.assertNotIn("PanaceaQtQASetup", ci)


if __name__ == "__main__":
    unittest.main()
