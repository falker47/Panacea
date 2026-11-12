"""Qt updater UI must only invoke the protected, allowlisted flow."""
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication
from qt_app.update_bridge import UpdateBridge

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


class UpdateBridgePollingRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt_application = QCoreApplication.instance() or QCoreApplication([])

    def test_transient_poll_exception_preserves_helper_job_and_exclusion(self):
        bridge = UpdateBridge(SimpleNamespace(busy=False), SimpleNamespace(busy=False),
                              flow=SimpleNamespace(install_eligible=True))
        self.addCleanup(bridge.stop)

        class UnreadableJob:
            def poll(self):
                raise PermissionError("status file temporarily locked")

        job = UnreadableJob()
        bridge._job = job
        bridge._busy = True
        bridge._installing = True

        class WorkerWithPollError:
            def start(self, name, work, **callbacks):
                try:
                    work()
                except Exception as error:
                    callbacks["on_error"](error)
                return True

            def close(self):
                pass

        bridge._workers = WorkerWithPollError()
        with patch("qt_app.update_bridge.QTimer") as timer:
            bridge._poll()
            timer.singleShot.assert_called_once()
        self.assertIs(bridge._job, job)
        self.assertTrue(bridge.busy)
        self.assertTrue(bridge.installing)
        self.assertIn("status", bridge.status.lower())

    def test_overlapping_poll_cannot_drop_running_helper(self):
        bridge = UpdateBridge(SimpleNamespace(busy=False), SimpleNamespace(busy=False),
                              flow=SimpleNamespace(install_eligible=True))
        self.addCleanup(bridge.stop)
        job = SimpleNamespace(poll=lambda: {"status": "preparing"})
        bridge._job = job
        bridge._busy = True
        bridge._installing = True

        class BusyWorker:
            def start(self, name, work, **callbacks):
                return False

            def close(self):
                pass

        bridge._workers = BusyWorker()
        with patch("qt_app.update_bridge.QTimer") as timer:
            bridge._poll()
            timer.singleShot.assert_called_once()
        self.assertIs(bridge._job, job)
        self.assertTrue(bridge.busy)
        self.assertTrue(bridge.installing)
