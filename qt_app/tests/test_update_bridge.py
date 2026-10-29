"""Qt updater UI must only invoke the protected, allowlisted flow."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class UpdateBridgeContractTests(unittest.TestCase):
    def test_bridge_never_accepts_untrusted_url_or_target(self):
        source = (ROOT / "update_bridge.py").read_text(encoding="utf-8")
        for identifier in ("def check(self)", "def prepareInstall(self)",
                           "def confirmInstall(self)", "def cancelDownload(self)",
                           "self._flow.download", "self._flow.start_verified_install",
                           "self._job.poll"):
            self.assertIn(identifier, source)
        self.assertNotIn("os.startfile(", source)
        self.assertNotIn("subprocess.Popen(", source)
        self.assertIn("self._maintenance.busy", source)
        self.assertIn("self._reader.busy", source)
        self.assertIn("self._flow.install_eligible", source)

    def test_qa_cannot_propose_production_install(self):
        source = (ROOT / "update_bridge.py").read_text(encoding="utf-8")
        self.assertIn("or not self.eligible:", source)
        self.assertIn("or not self._available", source)
        self.assertIn("self._pending = True", source)
        self.assertIn("if self._downloading and not self._installing:", source)


if __name__ == "__main__":
    unittest.main()
