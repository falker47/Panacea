"""Optional 2.2 extension for the Qt shell. All maintenance consent belongs to the shell."""
from __future__ import annotations

from queue import Empty, SimpleQueue
import threading

from PySide6.QtCore import QCoreApplication, QObject, Property, QTimer, Signal, Slot

from modules.storage_analysis import StorageAnalysis


def _on_change(source, callback):
    signal = getattr(source, "changed", None)
    if signal is not None:
        signal.connect(callback)


class ReadFeature(QObject):
    changed = Signal()
    action = ""
    mutations = ()

    def __init__(self, context):
        super().__init__()
        self.context = context
        self._was_running = False
        _on_change(context.reader, self.changed.emit)
        _on_change(context.maintenance, self._maintenance_changed)

    def _maintenance_changed(self):
        maintenance = self.context.maintenance
        busy = getattr(maintenance, "busy", False)
        if busy and getattr(maintenance, "lastAction", "") in self.mutations:
            self._was_running = True
        elif self._was_running and not busy:
            self._was_running = False
            self.refresh()
        self.changed.emit()

    @Property("QVariantMap", notify=changed)
    def data(self):
        return getattr(self.context.reader, "results", {}).get(self.action, {})

    @Property(bool, notify=changed)
    def busy(self):
        return getattr(self.context.reader, "busy", False) or getattr(self.context.maintenance, "busy", False)

    @Slot()
    def refresh(self):
        if not self.context.qa_smoke:
            self.context.reader.request(self.action)


class HealthService(ReadFeature):
    action = "health_check"

    @Slot()
    def windowsUpdate(self):
        if not self.context.qa_smoke:
            self.context.maintenance.prepare("windows_update", "")


class StartupService(ReadFeature):
    action = "startup_apps"
    mutations = ("startup_enable", "startup_disable")

    @Slot(str, bool)
    def setEnabled(self, identifier, enabled):
        if not self.context.qa_smoke:
            self.context.maintenance.prepareTarget("startup_enable" if enabled else "startup_disable", identifier)


class CleanupService(ReadFeature):
    action = "deep_cleanup_preview"
    mutations = ("deep_cleanup",)
    outcomesChanged = Signal()

    def __init__(self, context):
        super().__init__(context)
        _on_change(context.maintenance, self.outcomesChanged.emit)

    @Property("QVariantList", notify=outcomesChanged)
    def outcomes(self):
        return getattr(self.context.maintenance, "results", {}).get("deep_cleanup", {}).get("steps", [])

    @Slot(str)
    def prepare(self, categories):
        if not self.context.qa_smoke:
            self.context.maintenance.prepareTarget("deep_cleanup", categories)


class StorageService(QObject):
    changed = Signal()

    def __init__(self, context, *, scanner=None):
        super().__init__()
        self.context = context
        self.scanner = scanner or StorageAnalysis()
        self._cancel = threading.Event()
        self._queue = SimpleQueue()
        self._timer = QTimer(self)
        self._timer.setInterval(75)
        self._timer.timeout.connect(self._drain)
        self._data = {}
        self._busy = False
        self._visited = 0
        self._open_error = False
        _on_change(context.reader, self.changed.emit)
        app = QCoreApplication.instance()
        if app:
            app.aboutToQuit.connect(self.cancel)
        self.destroyed.connect(self._cancel.set)

    @Property("QVariantList", notify=changed)
    def drives(self):
        return [row["letter"] for row in getattr(self.context.reader, "results", {}).get("drives", {}).get("drives", [])
                if row.get("available")]

    @Property("QVariantMap", notify=changed)
    def data(self):
        return self._data

    @Property(bool, notify=changed)
    def busy(self):
        return self._busy

    @Property(int, notify=changed)
    def visited(self):
        return self._visited

    @Property(bool, notify=changed)
    def openError(self):
        return self._open_error

    @Slot()
    def loadDrives(self):
        if not self.context.qa_smoke:
            self.context.reader.request("drives")

    @Slot(str, bool)
    def scan(self, selection, refresh):
        if self.context.qa_smoke or self._busy or (selection != "profile" and selection not in self.drives):
            return
        self._cancel.clear()
        self._busy = True
        self._data, self._visited, self._open_error = {}, 0, False
        # The worker owns no QObject. Shutdown can cancel a scan without waiting on disk I/O.
        scanner, cancel, queue = self.scanner, self._cancel, self._queue

        def worker():
            try:
                result = scanner.scan(selection, cancel=cancel, progress=queue.put, refresh=refresh)
            except Exception as exc:
                result = {"status": "unavailable", "selection": selection, "error": type(exc).__name__}
            queue.put(result)

        threading.Thread(target=worker, name="Panacea storage scan", daemon=True).start()
        self._timer.start()
        self.changed.emit()

    def _drain(self):
        try:
            while True:
                message = self._queue.get_nowait()
                if isinstance(message, int):
                    self._visited = message
                else:
                    self._data, self._busy = message, False
                    self._timer.stop()
        except Empty:
            pass
        self.changed.emit()

    @Slot()
    def cancel(self):
        self._cancel.set()

    @Slot(str)
    def openItem(self, path):
        if self._busy or self.context.qa_smoke or self._data.get("status") in (None, "cancelled", "unavailable"):
            return
        try:
            self.scanner.open_in_explorer(self._data["selection"], path)
            self._open_error = False
        except (OSError, ValueError):
            self._open_error = True
        self.changed.emit()


def create(app_context):
    return {"healthService": HealthService(app_context), "startupService": StartupService(app_context),
            "deepCleanupService": CleanupService(app_context), "storageService": StorageService(app_context)}
