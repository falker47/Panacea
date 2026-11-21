"""Qt-facing verified updater; no user-provided URL, executable or checksum.

The QA candidate can check official releases, but can never install one in-place.
The production frozen Panacea.exe reuses the existing protected updater unchanged.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re

from PySide6.QtCore import QObject, Property, QTimer, Signal, Slot

from modules.ui_dispatch import UiDispatcher, WorkerController
from modules.updater import (
    UpdateCancelled, UpdateManifestError, UpdateNetworkError, UpdateRateLimitError, UpdateVerificationError,
)
from qt_app.i18n.release_notes import sanitize_notes
from qt_app.update_flow import QtUpdateFlow
from version import VERSION


class UpdateBridge(QObject):
    changed = Signal()
    releaseNotesAvailable = Signal(str, str)

    def __init__(self, reader, maintenance, *, flow=None, on_ready=None, parent=None):
        super().__init__(parent)
        self._reader = reader
        self._maintenance = maintenance
        self._flow = flow or QtUpdateFlow()
        self._on_ready = on_ready
        self._dispatcher = UiDispatcher()
        self._workers = WorkerController(self._dispatcher)
        self._timer = QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._dispatcher.drain)
        self._timer.start()
        self._busy = False
        self._downloading = False
        self._installing = False
        self._pending = False
        self._available = False
        self._closed = False
        self._job = None
        self._poll_again = False
        self._poll_failures = 0
        self._set_status("idle" if self._flow.install_eligible else "readOnly")
        self._version = ""
        self._percent = 0
        self._notes = ""
        self._last_checked = ""

    @Property(bool, notify=changed)
    def eligible(self):
        return self._flow.install_eligible

    @Property(bool, notify=changed)
    def available(self):
        return self._available

    @Property(bool, notify=changed)
    def busy(self):
        return self._busy

    @Property(bool, notify=changed)
    def downloading(self):
        return self._downloading

    @Property(bool, notify=changed)
    def installing(self):
        return self._installing

    @Property(bool, notify=changed)
    def pending(self):
        return self._pending

    @Property(str, notify=changed)
    def status(self):
        return self._status

    @Property("QVariantMap", notify=changed)
    def statusParams(self):
        return self._params.copy()

    @Property(str, notify=changed)
    def notes(self):
        return self._notes

    @Property(str, notify=changed)
    def lastChecked(self):
        return self._last_checked

    @Property(str, notify=changed)
    def availableVersion(self):
        return self._version

    @Property(str, constant=True)
    def currentVersion(self):
        return VERSION

    @Property(int, notify=changed)
    def progress(self):
        return self._percent

    def _set_status(self, code, **params):
        self._status = "update.status." + code
        self._params = params

    def _error_status(self, error, default):
        # Preserve the helper's specific recovery outcome, including the path
        # to a backup the user may need. It is only ever displayed as text.
        message = str(error)
        backup = re.search(r"(?:recover the old executable from|the backup was preserved at) ([^<>\r\n]+)\.$",
                           message, re.IGNORECASE)
        if backup:
            self._set_status("recoveryBackup", path=backup[1])
        elif "the backup was retained." in message:
            self._set_status("backupRetained")
        elif "the original application remains open." in message:
            self._set_status("restored")
        else:
            for kind, code in ((UpdateCancelled, "cancelled"), (UpdateRateLimitError, "rateLimited"),
                               (UpdateNetworkError, "network"), (UpdateManifestError, "invalidManifest"),
                               (UpdateVerificationError, "verificationFailed")):
                if isinstance(error, kind):
                    self._set_status(code)
                    return
            self._set_status(default)

    def _exclusive(self):
        return (self._closed or self._busy or self._pending or self._reader.busy or self._maintenance.busy
                or getattr(self._maintenance, "awaitingConfirmation", False))

    @Slot()
    def check(self):
        if self._exclusive():
            return
        self._busy = True
        self._available = False
        self._version = ""
        self._notes = ""
        self._set_status("checking")
        self.changed.emit()

        def succeed(release):
            self._last_checked = datetime.now(timezone.utc).isoformat(timespec="seconds")
            self._available = release is not None
            self._version = release.version if release else ""
            if release:
                self._notes = sanitize_notes(release.notes)
                self._set_status("available" if self.eligible else "availableReadOnly", version=release.version)
                if self.eligible:
                    self.releaseNotesAvailable.emit(release.version, self._notes)
            else:
                self._set_status("current", version=VERSION)

        def fail(error):
            self._last_checked = datetime.now(timezone.utc).isoformat(timespec="seconds")
            self._error_status(error, "checkFailed")

        def done():
            self._busy = False
            self.changed.emit()

        if not self._workers.start("check-release", self._flow.check, group="update-check",
                                   on_success=succeed, on_error=fail, on_done=done):
            self._set_status("alreadyChecking")
            done()

    @Slot()
    def prepareInstall(self):
        if self._exclusive() or not self._available or not self.eligible:
            return
        self._pending = True
        self._set_status("confirm", version=self._version)
        self.changed.emit()

    @Slot()
    def reject(self):
        if self._pending:
            self._set_status("available", version=self._version)
        self._pending = False
        self.changed.emit()

    @Slot()
    def confirmInstall(self):
        if (self._closed or not self._pending or self._busy or not self.eligible
                or not self._available or self._maintenance.busy or self._reader.busy
                or getattr(self._maintenance, "awaitingConfirmation", False)):
            return
        self._pending = False
        self._busy = True
        self._downloading = True
        self._percent = 0
        self._set_status("downloading")
        self.changed.emit()

        def progress(received, total):
            percentage = min(100, max(0, 100 * received // max(1, total)))
            self._dispatcher.post(self._set_progress, percentage, key="updater-progress")

        def succeed(_staged):
            self._set_status("verified")
            self.changed.emit()
            self._start_helper()

        def failed(error):
            self._failed(error)

        def done():
            self._downloading = False
            self.changed.emit()

        started = self._workers.start(
            "download-release", lambda: self._flow.download(progress=progress),
            group="update-download", on_success=succeed, on_error=failed, on_done=done,
        )
        if not started:
            self._failed(RuntimeError("Another update download is running."))

    def _set_progress(self, value):
        self._percent = value
        self.changed.emit()

    @Slot()
    def cancelDownload(self):
        if self._downloading and not self._installing:
            self._flow.cancel_download()
            self._set_status("cancelRequested")
            self.changed.emit()

    def _start_helper(self):
        if self._closed:
            self._failed(RuntimeError("Application is closing."))
            return
        self._installing = True
        self._set_status("starting")
        self.changed.emit()

        def prepared(job):
            self._job = job
            self._set_status("started")
            self.changed.emit()
            QTimer.singleShot(400, self._poll)

        if not self._workers.start(
            "prepare-protected-update", self._flow.start_verified_install,
            group="update-install", on_success=prepared, on_error=self._failed,
        ):
            self._failed(RuntimeError("Protected installer worker is unavailable."))

    def _poll(self):
        if self._closed or self._job is None or not self._installing:
            return
        self._poll_again = False

        def got(result):
            self._poll_failures = 0
            state = result.get("status", "failed")
            code = {"preparing": "preparing", "installing": "installing", "waiting_ready": "waitingReady",
                    "ready": "ready"}.get(state, "monitoring")
            self._set_status(code)
            if state == "ready":
                self._installing = False
                self._busy = False
                self._job = None
                self.changed.emit()
                # The new executable has acknowledged startup; now quit the old.
                if self._on_ready is not None:
                    self._on_ready()
            elif state == "failed":
                self._failed(RuntimeError(str(result.get("message") or state)))
            else:
                self._poll_again = True
                self.changed.emit()

        def after():
            if self._poll_again and not self._closed:
                QTimer.singleShot(650, self._poll)

        if not self._workers.start(
            "poll-protected-update", self._job.poll, group="update-poll",
            on_success=got, on_error=self._poll_unavailable, on_done=after,
        ):
            self._poll_unavailable(RuntimeError("Protected installer polling is already in progress."))

    def _poll_unavailable(self, error):
        # The helper may already be replacing the executable. A transient
        # read/worker failure is not a verified install failure: retain the job
        # and keep maintenance/update entry points excluded while monitoring.
        if self._closed or self._job is None or not self._installing:
            return
        self._poll_failures = min(self._poll_failures + 1, 5)
        self._set_status("statusUnavailable")
        self.changed.emit()
        QTimer.singleShot(min(5000, 650 * 2 ** (self._poll_failures - 1)), self._poll)

    def _failed(self, error):
        self._busy = False
        self._downloading = False
        self._installing = False
        self._job = None
        self._pending = False
        self._error_status(error, "failed")
        self.changed.emit()

    def stop(self):
        self._closed = True
        if self._downloading:
            self._flow.cancel_download()
        self._timer.stop()
        self._workers.close()
