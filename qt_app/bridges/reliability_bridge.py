"""T4 extension. QML receives fixed actions, typed results and one-use consent."""
import secrets
import threading

from PySide6.QtCore import QObject, Property, Qt, QTimer, Signal, Slot

from modules import crash_guard, diagnostics, history
from modules.maintenance_guard import MaintenanceGuard, _state


class _AsyncService(QObject):
    changed = Signal()
    _finished = Signal(object, object)

    def __init__(self):
        super().__init__()
        self._busy = False
        self._finished.connect(self._deliver, Qt.ConnectionType.QueuedConnection)

    @Property(bool, notify=changed)
    def busy(self):
        return self._busy

    def _run(self, work, receive):
        if self._busy:
            return False
        self._busy = True
        self.changed.emit()

        def run():
            try:
                result = work()
            except TimeoutError:
                result = {"error": "busy_other_instance"}
            except ValueError:
                result = {"error": "state_changed"}
            except Exception:
                result = {"error": "storage_unavailable"}
            self._finished.emit(receive, result)

        threading.Thread(target=run, name="panacea-reliability", daemon=False).start()
        return True

    @Slot(object, object)
    def _deliver(self, receive, result):
        self._busy = False
        receive(result)
        self.changed.emit()


class HistoryService(_AsyncService):
    def __init__(self, smoke):
        super().__init__()
        self._smoke = smoke
        self._page = {"items": [], "total": 0, "corrupt": 0, "has_more": False, "unavailable": False}
        self._request = None
        self._loaded = False
        self._revision = 0

    @Property("QVariantMap", notify=_AsyncService.changed)
    def pageData(self):
        return self._page

    @Slot(int, str)
    def loadPage(self, offset, status):
        self._loaded = True
        self._revision += 1
        self._request = (max(0, offset), status)
        if self._busy or self._smoke:
            return
        request, revision = self._request, self._revision

        def receive(result):
            if self._revision != revision:
                self.refresh()
            else:
                self._page = result if "items" in result else {**self._page, "unavailable": True}
        self._run(lambda: history.page(request[0], 20, request[1]), receive)

    @Slot()
    def refresh(self):
        if self._loaded:
            self.loadPage(*self._request)


class ReliabilityService(_AsyncService):
    historyChanged = Signal()

    def __init__(self, context, guard, capture):
        super().__init__()
        self._context = context
        self._guard = guard
        self._capture = capture
        self._state = _state("clear")
        self._notice = ""
        self._pending = None
        self._was_running = False
        self._refresh_due = False
        changed = getattr(context.maintenance, "changed", None)
        if changed is not None:
            changed.connect(self._maintenance_changed)

    @Property("QVariantMap", notify=_AsyncService.changed)
    def guardState(self):
        return self._state

    @Property(bool, notify=_AsyncService.changed)
    def previousCrash(self):
        return bool(self._capture and self._capture.previous_crash)

    @Property(str, notify=_AsyncService.changed)
    def notice(self):
        return self._notice

    @Property("QStringList", constant=True)
    def diagnosticFiles(self):
        return list(diagnostics.FILES)

    @Slot()
    def _maintenance_changed(self):
        running = bool(getattr(self._context.maintenance, "busy", False))
        finished = self._was_running and not running
        self._was_running = running
        if finished:
            self.historyChanged.emit()
            self.refresh()

    def _receive(self, result):
        self._notice = result.get("notice", result.get("error", ""))
        if "state" in result:
            self._state = result["state"]
        if result.get("archived"):
            self.historyChanged.emit()
        if self._refresh_due:
            self._refresh_due = False
            QTimer.singleShot(0, self.refresh)

    @Slot()
    def refresh(self):
        if self._context.qa_smoke:
            return
        if self._busy:
            self._refresh_due = True
            return
        self._run(lambda: {"state": self._guard.status()}, self._receive)

    def _recover(self, operation, manual=False):
        def work():
            try:
                state = operation()
            except TimeoutError:
                return {"state": _state("busy_other_instance"), "error": "busy_other_instance"}
            except ValueError:
                return {"state": self._guard.status(), "error": "state_changed"}
            except Exception:
                return {"state": self._guard.status(), "error": "storage_unavailable"}
            return {"state": state, "archived": manual, "notice": "archived" if manual else ""}
        self._run(work, self._receive)

    @Slot()
    def verifyAgain(self):
        if not self._context.qa_smoke:
            self._recover(self._guard.verify_again)

    @Slot(result=str)
    def prepareArchive(self):
        self._pending = None
        if (self._context.qa_smoke or self._busy or self._was_running
                or self._state["code"] not in ("interrupted_journal", "unverifiable_storage")):
            return ""
        nonce = secrets.token_urlsafe(24)
        self._pending = (nonce, self._state.copy())
        return nonce

    @Slot()
    def cancelArchive(self):
        self._pending = None

    @Slot(str, result=bool)
    def confirmArchive(self, nonce):
        pending, self._pending = self._pending, None
        if (not pending or not nonce.isascii() or not secrets.compare_digest(nonce, pending[0])
                or self._busy or self._was_running or self._context.qa_smoke):
            return False
        self._recover(lambda: self._guard.archive(pending[1]), manual=True)
        return True

    @Slot()
    def exportDiagnostics(self):
        if self._context.qa_smoke:
            return
        language = self._context.language()

        def work():
            archive = diagnostics.export(self._guard.status(), language)
            try:
                diagnostics.reveal(archive)
            except OSError:
                return {"notice": "exported_no_explorer"}
            return {"notice": "exported"}
        self._run(work, self._receive)

    @Slot()
    def dismissCrash(self):
        if self._capture:
            try:
                self._capture.dismiss()
            except OSError:
                self._notice = "storage_unavailable"
            self.changed.emit()


def create(app_context):
    # Share the operation owner's in-memory fail-closed latch as well as its
    # durable records. T3 supplies a bridge; tests can pass its backend directly.
    owner = getattr(app_context.maintenance, "_service", app_context.maintenance)
    guard = owner._manager("guard") if hasattr(owner, "_manager") else MaintenanceGuard()
    capture = None
    if not app_context.qa_smoke:
        try:
            capture = crash_guard.install()
        except (OSError, RuntimeError):
            pass
    recovery = ReliabilityService(app_context, guard, capture)
    records = HistoryService(app_context.qa_smoke)
    recovery.historyChanged.connect(records.refresh)
    if not app_context.qa_smoke:
        QTimer.singleShot(0, recovery.refresh)
    return {"reliabilityService": recovery, "historyService": records}
