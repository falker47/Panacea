"""Qt updater UI must only invoke the protected, allowlisted flow."""
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication
from modules.updater import UpdateNetworkError
from qt_app.i18n import messages
from qt_app.i18n.release_notes import sanitize_notes
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
        self.assertEqual(bridge.status, "update.status.statusUnavailable")

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


class InlineWorker:
    """Exercise normal callbacks without making a request or starting a helper."""
    def start(self, name, work, **callbacks):
        try:
            value = work()
        except Exception as error:
            callbacks["on_error"](error)
        else:
            callbacks["on_success"](value)
        if "on_done" in callbacks:
            callbacks["on_done"]()
        return True

    def close(self):
        pass


class UpdatePresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt_application = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.release = SimpleNamespace(version="2.2.0", notes="# Panacea\n- [Notes](https://example.invalid)")
        self.flow = SimpleNamespace(install_eligible=True, check=lambda: self.release)
        self.maintenance = SimpleNamespace(busy=False, awaitingConfirmation=False)
        self.bridge = UpdateBridge(SimpleNamespace(busy=False), self.maintenance, flow=self.flow)
        self.bridge._workers = InlineWorker()
        self.addCleanup(self.bridge.stop)

    def test_release_and_last_check_are_exposed_and_localizable(self):
        cached = []
        self.bridge.releaseNotesAvailable.connect(lambda *values: cached.append(values))
        self.assertEqual(self.bridge.lastChecked, "")
        self.bridge.check()
        self.assertEqual(self.bridge.notes, "# Panacea\n- Notes")
        self.assertEqual(cached, [("2.2.0", self.bridge.notes)])
        self.assertIsNotNone(datetime.fromisoformat(self.bridge.lastChecked).tzinfo)
        self.assertEqual(self.bridge.status, "update.status.available")
        self.assertEqual(self.bridge.statusParams, {"version": "2.2.0"})
        for locale in ("en", "it"):
            self.assertIn("2.2.0", messages(locale)[self.bridge.status].format_map(self.bridge.statusParams))
        self.bridge.prepareInstall()
        self.assertTrue(self.bridge.pending)
        self.assertEqual(self.bridge.status, "update.status.confirm")
        self.bridge.reject()
        self.assertFalse(self.bridge.pending)
        self.assertEqual(self.bridge.status, "update.status.available")
        self.flow.check = lambda: None
        self.bridge.check()
        self.assertFalse(self.bridge.available)
        self.assertFalse(self.bridge.notes or self.bridge.availableVersion)
        self.assertEqual(self.bridge.status, "update.status.current")

    def test_pending_maintenance_excludes_an_update_without_consuming_confirmation(self):
        self.bridge.check()
        self.maintenance.awaitingConfirmation = True
        self.bridge.prepareInstall()
        self.assertFalse(self.bridge.pending)
        self.maintenance.awaitingConfirmation = False
        self.bridge.prepareInstall()
        self.maintenance.awaitingConfirmation = True
        self.bridge.confirmInstall()
        self.assertTrue(self.bridge.pending)
        self.assertFalse(self.bridge.busy)

    def test_error_code_and_backup_path_preserve_recovery_guidance(self):
        def fail():
            raise UpdateNetworkError("Fixture diagnostic")
        self.flow.check = fail
        self.bridge.check()
        self.assertEqual(self.bridge.status, "update.status.network")
        self.assertIsNotNone(datetime.fromisoformat(self.bridge.lastChecked).tzinfo)
        self.bridge._failed(RuntimeError("Recover the old executable from C:\\Panacea\\.previous.backup."))
        self.assertEqual(self.bridge.status, "update.status.recoveryBackup")
        self.assertEqual(self.bridge.statusParams, {"path": r"C:\Panacea\.previous.backup"})

    def test_qa_can_read_notes_but_cannot_cache_an_install_or_confirm(self):
        self.flow.install_eligible = False
        cached = []
        self.bridge.releaseNotesAvailable.connect(lambda *values: cached.append(values))
        self.bridge.check()
        self.bridge.prepareInstall()
        self.assertFalse(self.bridge.pending)
        self.assertEqual(self.bridge.status, "update.status.availableReadOnly")
        self.assertTrue(self.bridge.notes)
        self.assertFalse(cached)

    def test_qt_markdown_has_formatting_without_anchors_or_resource_requests(self):
        # A separate offscreen GUI avoids mixing QGuiApplication and this suite's
        # QCoreApplication singleton. A refusing resource provider records every
        # attempted load, including local paths, without opening anything.
        raw = """## Changes
- **Faster** startup and `local` formatting
- ![picture](file:///nonexistent) and [website](https://example.invalid)
<img src="data:fixture"><style>body{color:blue}</style>
[reference][r]
[r]: http://example.invalid
www.example.invalid https://example.invalid mail@example.invalid
&#60;img src="file:///nonexistent"&#62;
<b>Plain HTML labels</b>
"""
        safe = sanitize_notes(raw)
        self.assertEqual(sanitize_notes(safe), safe)
        script = """
import json, sys
from PySide6.QtCore import QByteArray
from PySide6.QtGui import QGuiApplication, QTextDocument
app = QGuiApplication([])
loads = []
class Document(QTextDocument):
    def loadResource(self, kind, url):
        loads.append(url.toString())
        return QByteArray()
doc = Document()
doc.setMarkdown(json.load(sys.stdin))
doc.size()
print(json.dumps([doc.toHtml(), doc.toPlainText(), loads]))
"""
        check = subprocess.run([sys.executable, "-c", script], input=json.dumps(safe),
                               env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
                               capture_output=True, text=True, timeout=20, check=True)
        html, plain, loads = json.loads(check.stdout)
        self.assertIn("<h2", html)
        self.assertIn("<ul", html)
        self.assertIn("Faster startup", plain)
        self.assertNotRegex(html.lower(), r"<(?:img|a)\b")
        self.assertEqual(loads, [])
