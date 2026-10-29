"""Qt-facing verified updater; no user-provided URL, executable or checksum.

The QA candidate can check official releases, but can never install one in-place.
The production frozen Panacea.exe reuses the existing protected updater unchanged.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Property, QTimer, Signal, Slot

from modules.ui_dispatch import UiDispatcher, WorkerController
from qt_app.update_flow import QtUpdateFlow
from version import VERSION


class UpdateBridge(QObject):
    changed = Signal()

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
        self._status = "Check for official stable updates. QA builds cannot install them."
        self._version = ""
        self._percent = 0

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

    @Property(str, notify=changed)
    def availableVersion(self):
        return self._version

    @Property(str, constant=True)
    def currentVersion(self):
        return VERSION

    @Property(int, notify=changed)
    def progress(self):
        return self._percent

    def _exclusive(self):
        return self._closed or self._busy or self._pending or self._reader.busy or self._maintenance.busy

    @Slot()
    def check(self):
        if self._exclusive():
            return
        self._busy = True
        self._available = False
        self._version = ""
        self._status = "Checking the official falker47/Panacea stable release..."
        self.changed.emit()

        def succeed(release):
            self._available = release is not None
            self._version = release.version if release else ""
            if not release:
                self._status = f"Panacea {VERSION} is up to date."
            elif self.eligible:
                self._status = f"Verified release metadata for Panacea {release.version}. Review before installing."
            else:
                self._status = (f"Panacea {release.version} is available. "
                                "This QA executable cannot replace the stable application.")

        def fail(error):
            self._status = f"Update check failed: {error}"

        def done():
            self._busy = False
            self.changed.emit()

        if not self._workers.start("check-release", self._flow.check, group="update-check",
                                   on_success=succeed, on_error=fail, on_done=done):
            self._status = "An update check is already running."
            done()

    @Slot()
    def prepareInstall(self):
        if self._exclusive() or not self._available or not self.eligible:
            return
        self._pending = True
        self._status = (f"Confirm verified download and protected installation of Panacea "
                        f"{self._version}. Windows may restart the application.")
        self.changed.emit()

    @Slot()
    def reject(self):
        self._pending = False
        self.changed.emit()

    @Slot()
    def confirmInstall(self):
        if (self._closed or not self._pending or self._busy or not self.eligible
                or not self._available or self._maintenance.busy or self._reader.busy):
            return
        self._pending = False
        self._busy = True
        self._downloading = True
        self._percent = 0
        self._status = "Downloading the official release; validating SHA-256 and executable."
        self.changed.emit()

        def progress(received, total):
            percentage = min(100, max(0, 100 * received // max(1, total)))
            self._dispatcher.post(self._set_progress, percentage, key="updater-progress")

        def succeed(_staged):
            self._status = "Download verified. Preparing protected helper and rollback."
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
            self._status = "Download cancellation requested. No executable has been replaced."
            self.changed.emit()

    def _start_helper(self):
        if self._closed:
            self._failed(RuntimeError("Application is closing."))
            return
        self._installing = True
        self._status = "Starting the verified installer. The old executable remains available."
        self.changed.emit()

        def prepared(job):
            self._job = job
            self._status = "Installer started. Waiting for verified startup or rollback."
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
            state = result.get("status", "failed")
            self._status = "Updater: " + str(result.get("message") or state)
            if state == "ready":
                self._installing = False
                self._busy = False
                self._job = None
                self.changed.emit()
                # The new executable has acknowledged startup; now quit the old.
                if self._on_ready is not None:
                    self._on_ready()
            elif state == "failed":
                self._failed(RuntimeError(self._status))
            else:
                self._poll_again = True
                self.changed.emit()

        def after():
            if self._poll_again and not self._closed:
                QTimer.singleShot(650, self._poll)

        if not self._workers.start(
            "poll-protected-update", self._job.poll, group="update-poll",
            on_success=got, on_error=self._failed, on_done=after,
        ):
            self._failed(RuntimeError("Could not poll protected installer status."))

    def _failed(self, error):
        self._busy = False
        self._downloading = False
        self._installing = False
        self._job = None
        self._pending = False
        self._status = f"Update unsuccessful: {error}. The existing application remains installed; verify updater status."
        self.changed.emit()

    def stop(self):
        self._closed = True
        if self._downloading:
            self._flow.cancel_download()
        self._timer.stop()
        self._workers.close()
