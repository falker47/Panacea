"""Isolated fake clients: no network, elevated Windows work, or destructive access."""
from pathlib import Path
import tempfile
import unittest

from modules.updater import Release, UpdateVerificationError, UpdateCancelled
from qt_app.update_flow import QtUpdateFlow, production_identity
from version import GITHUB_REPO, VERSION


class FakeClient:
    def __init__(self, repo, version, *, release=None):
        assert (repo, version) == (GITHUB_REPO, VERSION)
        self.release = release or Release("2.0.3", "https://example.test/release",
                                          "https://example.test/exe", 10,
                                          "https://example.test/sha")
        self.downloaded = False

    def check(self):
        return self.release

    def download(self, release, directory, progress):
        assert release is self.release
        self.downloaded = True
        if progress(0, 10) is False:
            raise UpdateCancelled("Cancelled")
        candidate = Path(directory) / "fake-verified.exe"
        candidate.write_bytes(b"fake PE test fixture; no execution")
        if progress(10, 10) is False:
            # Model the real UpdateClient.download cleanup on cancellation.
            candidate.unlink(missing_ok=True)
            raise UpdateCancelled("Cancelled")
        return candidate


class QtUpdateFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.clients = []
        self.calls = []

        def client_factory(repo, version):
            client = FakeClient(repo, version)
            self.clients.append(client)
            return client

        def launch(stage, target, release, client):
            self.calls.append((stage, target, release, client))
            self.assertTrue(stage.is_file())
            return "verified-helper-job"

        self.factory = client_factory
        self.launch = launch

    def make(self, frozen, name):
        return QtUpdateFlow(frozen=frozen,
                            executable=Path(self.temp.name) / name,
                            client_factory=self.factory, launch=self.launch,
                            directory=self.temp.name)

    def test_untrusted_source_and_qa_cannot_download_or_install(self):
        self.assertFalse(production_identity(frozen=False, executable="Panacea.exe"))
        self.assertFalse(production_identity(frozen=True, executable="PanaceaQtCandidate.exe"))
        for frozen, name in [(False, "Panacea.exe"), (True, "PanaceaQtCandidate.exe")]:
            flow = self.make(frozen, name)
            self.assertIsNotNone(flow.check())
            with self.assertRaises(UpdateVerificationError):
                flow.download()
            with self.assertRaises(UpdateVerificationError):
                flow.start_verified_install()
        self.assertEqual(self.calls, [])
        self.assertTrue(all(not client.downloaded for client in self.clients))

    def test_production_identity_uses_existing_secure_backend(self):
        flow = self.make(True, "Panacea.exe")
        with self.assertRaises(UpdateVerificationError):
            flow.download()
        release = flow.check()
        stage = flow.download()
        self.assertTrue(stage.is_file())
        self.assertEqual(flow.start_verified_install(), "verified-helper-job")
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0][1].name, "Panacea.exe")
        self.assertIs(self.calls[0][2], release)
        self.assertFalse(stage.exists())
        self.assertEqual(list(Path(self.temp.name).glob("Panacea-Qt-update-*")), [])

    def test_cancel_cleans_staged_file_without_touching_external_files(self):
        flow = self.make(True, "Panacea.exe")
        flow.check()
        external = Path(self.temp.name) / "do-not-delete.txt"
        external.write_text("preserve", encoding="utf-8")
        flow.cancel_event.set()
        # cancel is reset at download start; request cancellation from progress.
        def cancel_on_progress(received, total):
            flow.cancel_download()
        with self.assertRaises(UpdateCancelled):
            flow.download(progress=cancel_on_progress)
        self.assertEqual(external.read_text(encoding="utf-8"), "preserve")
        self.assertEqual(list(Path(self.temp.name).glob("Panacea-Qt-update-*")), [])
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
