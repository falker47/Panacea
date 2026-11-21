"""Panacea desktop entry point and Qt-facing maintenance broker."""
from __future__ import annotations
import argparse
import ctypes
import json
import os
from concurrent.futures import ThreadPoolExecutor
import logging
from types import SimpleNamespace
from pathlib import Path
import sys
import time
import faulthandler

_qa_trace_file = None
_qa_started = time.perf_counter()
if "--smoke-test" in sys.argv:
    if "--capture" in sys.argv and sys.argv.index("--capture") + 1 < len(sys.argv):
        _qa_log = Path(sys.argv[sys.argv.index("--capture") + 1]).with_suffix(".lifecycle.log")
        _qa_log.parent.mkdir(parents=True, exist_ok=True)
        _qa_trace_file = _qa_log.open("w", encoding="utf-8")
    else:
        _qa_trace_file = sys.stderr
    if _qa_trace_file is not None:
        faulthandler.enable(file=_qa_trace_file)
        faulthandler.dump_traceback_later(15, repeat=True, file=_qa_trace_file)


def _qa_trace(phase):
    if _qa_trace_file is not None:
        print(f"{(time.perf_counter() - _qa_started) * 1000:.1f} ms · {phase}",
              file=_qa_trace_file, flush=True)


_qa_trace("Python started; importing Qt")

from PySide6.QtCore import QEvent, QObject, Property, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication, QFontDatabase, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

_qa_trace("Qt imports complete")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qt_app.icon_provider import NavigationIconProvider  # noqa: E402
from qt_app.bridges import FeatureFactory, load_extensions  # noqa: E402
from qt_app.i18n import I18n  # noqa: E402
from qt_app.settings import AppSettings  # noqa: E402
from modules.ui_dispatch import UiDispatcher, WorkerController  # noqa: E402
from qt_app.services import READ_ACTIONS, ReadService  # noqa: E402
from qt_app.catalog import SECTIONS, SECTION_ACTIONS, palette_entries  # noqa: E402
from qt_app.confirmation_copy import confirmation_text  # noqa: E402
from qt_app.elevation import elevation_arguments  # noqa: E402
from qt_app.update_bridge import UpdateBridge  # noqa: E402
from qt_app.maintenance import DANGEROUS  # noqa: E402


# Numeric smoke arguments 0..4 keep pointing to the successors of the V2 groups.
SMOKE_SECTIONS = ("home", "cleanup", "repair", "performance", "guided", "startup", "history", "updates", "settings")
FOCUS_SECTIONS = {"cleaning": "cleanup", "apps": "startup", "tools": "repair", "disk": "performance",
                  "turbo": "performance", "startup": "startup"}
_ACTION_SCOPES = {action: section for section in SECTIONS for action in SECTION_ACTIONS[section]}




def _percent(value):
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return "—"
    if not 0 <= number <= 100:
        return "—"
    return f"{number:.1f}%"


def _format_sample(data):
    ram = data.get("ram")
    disk = data.get("disk")
    def capacities(values):
        if not isinstance(values, (tuple, list)) or len(values) < 3:
            return [None, None, None]
        try:
            total, free, used = map(float, values[:3])
            if total <= 0 or not 0 <= free <= total or not 0 <= used <= 100:
                return [None, None, None]
            return [round(total, 1), round(free, 1), round(used, 1)]
        except (TypeError, ValueError, OverflowError):
            return [None, None, None]
    battery = data.get("battery")
    charge = battery[0] if isinstance(battery, (tuple, list)) and len(battery) == 2 else None
    power = battery[1] if isinstance(battery, (tuple, list)) and len(battery) == 2 else "Unknown"
    if isinstance(charge, bool) or not isinstance(charge, (int, float)) or not 0 <= charge <= 100:
        charge = None
    if power not in ("On Battery", "Plugged In", "Charging"):
        power = "Unknown"
    return {
        "cpu": _percent(data.get("cpu")),
        "ram": _percent(ram[2]) if isinstance(ram, (tuple, list)) and len(ram) > 2 else "—",
        "disk": _percent(disk[2]) if isinstance(disk, (tuple, list)) and len(disk) > 2 else "—",
        "details": {
            "ram": capacities(ram), "disk": capacities(disk),
            "battery": charge, "power": power,
            "uptime": str(data.get("uptime") or "Unknown"),
        },
    }


class MetricsBridge(QObject):
    """Pass read-only SystemMonitor snapshots to QML without blocking the GUI."""

    changed = Signal()
    sampleReady = Signal(object)

    def __init__(self):
        super().__init__()
        self._values = {"cpu": "—", "ram": "—", "disk": "—"}
        self._history = {"cpu": [], "ram": [], "disk": []}
        self._monitor = None
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="panacea-metrics")
        self._busy = False
        self._closed = False
        self._timer = QTimer(self)
        self._timer.setInterval(3000)
        self._timer.timeout.connect(self.refresh)
        self.sampleReady.connect(self._apply)

    @Property("QVariantMap", notify=changed)
    def details(self):
        return self._values.get("details", {})

    @Property(str, notify=changed)
    def cpu(self):
        return self._values["cpu"]

    @Property(str, notify=changed)
    def ram(self):
        return self._values["ram"]

    @Property(str, notify=changed)
    def disk(self):
        return self._values["disk"]

    @Property('QVariantList', notify=changed)
    def cpuHistory(self):
        return self._history["cpu"]

    @Property('QVariantList', notify=changed)
    def ramHistory(self):
        return self._history["ram"]

    @Property('QVariantList', notify=changed)
    def diskHistory(self):
        return self._history["disk"]

    @Slot()
    def start(self):
        self._timer.start()
        self.refresh()

    @Slot()
    def refresh(self):
        if self._busy or self._closed:
            return
        self._busy = True
        future = self._executor.submit(self._sample)

        def done(result_future):
            try:
                values = result_future.result()
            except Exception:
                logging.getLogger(__name__).exception("Read-only metric snapshot failed")
                values = {"cpu": "—", "ram": "—", "disk": "—"}
            if not self._closed:
                self.sampleReady.emit(values)

        future.add_done_callback(done)

    def _sample(self):
        if self._monitor is None:
            from modules.system_monitor import SystemMonitor
            self._monitor = SystemMonitor()
        return _format_sample(self._monitor.sample_fast())

    @Slot(object)
    def _apply(self, values):
        if self._closed:
            return
        self._busy = False
        updated = values != self._values
        self._values = values
        for key in ("cpu", "ram", "disk"):
            displayed = values.get(key)
            if not isinstance(displayed, str) or not displayed.endswith("%"):
                continue
            try:
                number = float(displayed[:-1])
            except ValueError:
                continue
            if 0 <= number <= 100:
                self._history[key] = (self._history[key] + [number])[-60:]
                updated = True
        if updated:
            self.changed.emit()

    def stop(self):
        self._closed = True
        self._timer.stop()
        if self._monitor is not None:
            self._monitor.close()
        self._executor.shutdown(wait=False, cancel_futures=True)



class ReadBridge(QObject):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._service = ReadService()
        self._dispatcher = UiDispatcher()
        self._workers = WorkerController(self._dispatcher)
        self._last = ""
        self._busy = False
        self._pending_reads = []
        self._closed = False
        self._maintenance = None
        self._updater = None
        self._drives = []
        self._results = {}
        self._section_logs = {}
        self._state = "idle"
        self._last_action = ""
        self._timer = QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._dispatcher.drain)
        self._timer.timeout.connect(self._drain_reads)
        self._timer.start()

    @Property(str, notify=changed)
    def output(self):
        return self._last

    @Property(bool, notify=changed)
    def busy(self):
        return self._busy

    @Property('QVariantList', notify=changed)
    def driveLetters(self):
        return self._drives

    @Property('QVariantMap', notify=changed)
    def results(self):
        return self._results

    @Property('QVariantMap', notify=changed)
    def sectionLogs(self):
        return self._section_logs

    @Property(str, notify=changed)
    def state(self):
        return self._state

    @Property(str, notify=changed)
    def lastAction(self):
        return self._last_action

    @Slot(str)
    def request(self, action):
        if self._closed or action not in READ_ACTIONS:
            return
        # At most one pending request per allowlisted action. Page navigation
        # during a slow read or mutation must not silently lose its refresh.
        if self._busy and self._last_action == action:
            return
        if action not in self._pending_reads:
            self._pending_reads.append(action)
        self._drain_reads()

    def invalidate(self, action):
        self._results = {**self._results, action: {"available": False, "refreshing": True}}
        self.changed.emit()

    def _drain_reads(self):
        if (self._closed or not self._pending_reads or self._busy
                or (self._maintenance is not None and (
                    self._maintenance.busy or getattr(self._maintenance, "awaitingConfirmation", False)))
                or (self._updater is not None and (
                    self._updater.busy or getattr(self._updater, "pending", False)))):
            return
        action = self._pending_reads.pop(0)
        self._busy = True
        self._state = "running"
        self._last_action = action
        self._last = ""
        if action == "turbo_status":
            self.invalidate(action)
        self.changed.emit()
        def successful(value):
            if action == "hardware":
                value = {key: "" if text in ("Non disponibile", "Unknown") else text
                         for key, text in value.items()}
            self._results = {**self._results, action: value}
            self._state = "completed"
            self._last = json.dumps(value, ensure_ascii=False, indent=2)
            scope = {"temp_preview": "cleanup", "drives": "performance"}.get(action)
            if scope:
                self._section_logs = {**self._section_logs, scope: self._last[-16000:]}
            if action == 'drives':
                self._drives = [row['letter'] for row in value.get('drives', []) if row.get('available') is True]
            self.changed.emit()
        def failed(exc):
            self._state = "error"
            self._last = str(exc)
            self._results = {**self._results, action: {"available": False, "error": str(exc)}}
            if action == "drives":
                self._drives = []
            scope = {"temp_preview": "cleanup", "drives": "performance"}.get(action)
            if scope:
                self._section_logs = {**self._section_logs, scope: self._last}
            self.changed.emit()
        def done():
            self._busy = False
            if (action == "hardware" and getattr(self, "_automatic_updates", False)
                    and not self._closed):
                self._automatic_updates = False
                self.request("windows_updates")
            self._drain_reads()
            self.changed.emit()
        accepted = self._workers.start(
            action, lambda: self._service.collect(action),
            group="read", on_success=successful, on_error=failed, on_done=done)
        if not accepted:
            failed(RuntimeError("Read worker unavailable"))
            done()

    def stop(self):
        if self._closed:
            return
        self._closed = True
        self._pending_reads.clear()
        self._timer.stop()
        self._workers.close()
        from threading import Thread
        Thread(target=self._service.close, name="panacea-read-close", daemon=False).start()



class MaintenanceBridge(QObject):
    """One-use confirmation broker; backend execution never runs on the QML thread."""
    changed = Signal()

    preparationRejected = Signal(str)

    def __init__(self, parent=None, service=None):
        super().__init__(parent)
        from qt_app.maintenance import MaintenanceService
        self._service = service if service is not None else MaintenanceService()
        self._dispatcher = UiDispatcher()
        self._workers = WorkerController(self._dispatcher)
        self._pending = ""
        self._details = ""
        self._output = ""
        self._busy = False
        self._closed = False
        self._reader = None
        self._updater = None
        self._language = 'it'
        self._prepared_action = ""
        self._prepared_danger = False
        self._view_section = "home"
        self._last_title = ""
        self._section = ""
        self._last_action = ""
        self._result_status = ""
        self._progress_done = 0
        self._progress_total = 0
        self._steps = []
        self._results = {}
        self._section_logs = {}
        self._timer = QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._dispatcher.drain)
        self._timer.start()

    @Slot(str)
    def setLanguage(self, language):
        if language in ('it', 'en'):
            self._language = language
            self.changed.emit()

    @Property(str, notify=changed)
    def lastAction(self):
        return self._last_action

    @Property(str, notify=changed)
    def resultStatus(self):
        return self._result_status

    @Property(int, notify=changed)
    def progressDone(self):
        return self._progress_done

    @Property(int, notify=changed)
    def progressTotal(self):
        return self._progress_total

    @Property('QVariantList', notify=changed)
    def steps(self):
        return self._steps

    @Property('QVariantMap', notify=changed)
    def results(self):
        return self._results

    @Property('QVariantMap', notify=changed)
    def sectionLogs(self):
        return self._section_logs

    def _remember_result(self):
        if self._last_action:
            self._results = {**self._results, self._last_action: {
                "status": self._result_status, "done": self._progress_done,
                "total": self._progress_total, "steps": list(self._steps), "output": self._output}}

    @Property(str, notify=changed)
    def activeSection(self):
        return _ACTION_SCOPES.get(self._last_action, self._section)

    @Property(str, notify=changed)
    def details(self):
        return self._details

    @Property(str, notify=changed)
    def output(self):
        return self._output

    @Property(bool, notify=changed)
    def busy(self):
        return self._busy

    @Property(bool, notify=changed)
    def awaitingConfirmation(self):
        return bool(self._pending)

    @Property(str, notify=changed)
    def preparedAction(self):
        return self._prepared_action

    @Property(str, notify=changed)
    def lastTitle(self):
        return self._last_title

    @Property(bool, notify=changed)
    def destructive(self):
        return self._prepared_action in DANGEROUS or self._prepared_danger

    @Slot(str)
    def setSection(self, section):
        if section in SECTIONS:
            self._view_section = section

    @Slot(str, str)
    def prepare(self, action, drive):
        self._prepare(action, drive)

    @Slot(str, str)
    def prepareTarget(self, action, target):
        self._prepare(action, "", target=target)

    def _prepare(self, action, drive, **options):
        if (self._closed or self._busy or self._pending or (self._reader is not None and self._reader.busy)
                or (self._updater is not None and (self._updater.busy or getattr(self._updater, "pending", False)))):
            return
        try:
            data = self._service.prepare(action, drive, **options)
            title, warning = confirmation_text(action, data, self._language)
            self._details = title + "\n" + warning
            self._pending = data["nonce"]
            self._prepared_action = action
            self._prepared_danger = bool(data.get("destructive") or data.get("dangerous") or options)
        except (KeyError, ValueError, RuntimeError, TypeError) as exc:
            self.reject()
            self._output = str(exc)
            self.preparationRejected.emit("maintenance.targetRejected" if options else "maintenance.rejected")
        self.changed.emit()

    @Slot()
    def reject(self):
        self._service.reject()
        self._pending = ""
        self._prepared_action = ""
        self._details = ""
        self.changed.emit()

    @Slot()
    def confirm(self):
        if (self._closed or self._busy or not self._pending
                or (self._reader is not None and self._reader.busy)
                or (self._updater is not None and self._updater.busy)):
            return
        nonce = self._pending
        self._last_title = self._details.partition("\n")[0]
        self._section = self._view_section
        self._last_action = self._prepared_action
        self._prepared_action = ""
        self._pending = ""
        self._details = ""
        self._busy = True
        self._result_status = "running"
        self._progress_done = 0
        self._progress_total = 10 if self._last_action == "resurrection" else (3 if self._last_action == "quick_cleanup" else 0)
        self._steps = []
        self._output = ""
        from qt_app.maintenance import TURBO
        if self._last_action in TURBO and self._reader is not None:
            self._reader.invalidate("turbo_status")
        self._remember_result()
        self.changed.emit()

        def log(message):
            self._dispatcher.post(lambda: self._append(str(message)))

        def progress(done, total, label):
            def apply():
                self._progress_done = done
                self._progress_total = total
                # Resurrection sends a structured result; quick cleanup reuses
                # the original StepResult. Never infer success from the count.
                row = label if isinstance(label, dict) else (
                    {"name": label.name, "success": label.success, "message": label.message}
                    if hasattr(label, "success") and hasattr(label, "name") else None)
                if row is not None and done == len(self._steps) + 1:
                    self._steps = [*self._steps, {"name": str(row.get("name", "")),
                                                "success": row.get("success") is True,
                                                "message": str(row.get("message", ""))}]
                self._append(f"{done}/{total}: " + (str(row.get("name", "")) if row else str(label)))
            self._dispatcher.post(apply)

        def success(result):
            self._result_status = result.get("status", "unknown")
            self._steps = list(result.get("steps") or [])
            if self._steps:
                self._progress_done = len(self._steps)
                self._progress_total = result.get("total", self._progress_total)
            self._append(result.get("message", ""))

        def failure(exc):
            self._result_status = "failed"
            self._append(str(exc))

        def done():
            self._busy = False
            self.changed.emit()

            # A failed setter may follow a successful one. Keep the attempt's
            # outcome and independently remeasure machine state and originals.
            if (self._last_action in TURBO and self._reader is not None
                    and not self._closed):
                self._reader.request("turbo_status")

        accepted = self._workers.start(
            "maintenance", lambda: self._service.execute(nonce, log=log, progress=progress),
            group="maintenance", on_success=success, on_error=failure, on_done=done)
        if not accepted:
            self._service.reject()
            self._result_status = "failed"
            self._remember_result()
            self.preparationRejected.emit("maintenance.workerBusy")
            done()

    def _append(self, message):
        self._output = (self._output + "\n" + message)[-16000:]
        scope = self.activeSection
        if scope:
            self._section_logs = {**self._section_logs, scope:
                                  (self._section_logs.get(scope, "") + "\n" + message)[-16000:]}
        self._remember_result()
        self.changed.emit()

    @Slot()
    def cancel(self):
        if self._busy:
            self._service.cancel()
            self._result_status = "cancelling"
            self._remember_result()
            self.changed.emit()

    def stop(self):
        self._closed = True
        self._timer.stop()
        self._service.close()
        self._workers.close()

def _check_initial_release_when_idle(reader, maintenance, updater):
    """One metadata check after startup reads finish; never download or install."""
    if updater._closed or not getattr(updater, "auto_check_enabled", lambda: True)():
        return False
    if (reader.busy or maintenance.busy or getattr(maintenance, "awaitingConfirmation", False)
            or updater.busy or updater.pending):
        QTimer.singleShot(1000, lambda: _check_initial_release_when_idle(reader, maintenance, updater))
        return False
    updater.check()
    return True


FEATURE_NAMES = ("RecoveryBanner", "History", "HealthCheck", "DeepCleanup", "StorageAnalysis", "StartupApps")


def configure_context(engine, qml_dir, settings, translator, reader, maintenance, updater, metrics, *, smoke):
    """Keep extension objects alive as long as their QML context."""
    context = engine.rootContext()
    engine.addImageProvider("panacea-nav", NavigationIconProvider())
    features = {name: QUrl.fromLocalFile(str(path)).toString() for name in FEATURE_NAMES
                if (path := qml_dir / "qml" / "features" / (name + ".qml")).is_file()}
    for name, value in {
        "appSettings": settings, "i18n": translator, "qaSmokeMode": smoke,
        "liveMetrics": metrics, "readService": reader, "maintenanceService": maintenance,
        "updateService": updater, "sectionIds": list(SECTIONS), "paletteEntries": palette_entries(),
        "sectionActions": {section: list(actions) for section, actions in SECTION_ACTIONS.items()},
        "featureUrls": features, "featureFactory": FeatureFactory(engine),
    }.items():
        context.setContextProperty(name, value)
    app_context = SimpleNamespace(reader=reader, maintenance=maintenance, updater=updater, metrics=metrics,
                                  language=lambda: translator.language, qa_smoke=smoke, qml_context=context)
    return load_extensions(app_context)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Panacea Qt UI migration QA")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--smoke-test", action="store_true")
    modes.add_argument("--smoke-backend-imports", action="store_true",
                       help="Verify bundled maintenance modules without launching Windows actions")
    modes.add_argument("--panacea-update-helper", metavar="WORKSPACE",
                       help="Protected updater helper; never called by a user action")
    modes.add_argument("--panacea-update-ready", metavar="TOKEN",
                       help="Acknowledge verified startup after protected replacement")
    parser.add_argument("--capture", type=Path, help="Save a QA screenshot with --smoke-test")
    parser.add_argument("--smoke-tab", choices=(*SECTIONS, *(str(i) for i in range(len(SECTIONS)))),
                        help="QA section id, or legacy numeric tab")
    parser.add_argument("--smoke-all-sections", action="store_true",
                        help="Capture each section with the same inert services and viewport")
    parser.add_argument("--smoke-width", type=int, help="QA only: logical viewport width")
    parser.add_argument("--smoke-height", type=int, help="QA only: logical viewport height")
    parser.add_argument("--smoke-language", choices=("it", "en"), help="QA only: visible locale")
    parser.add_argument("--smoke-scenario", default="default", choices=(
        "default", "expanded", "unknown", "running", "completed", "partial", "failed",
        "cancelled", "confirmation", "long-text"))
    parser.add_argument("--smoke-scroll", type=float, default=0, help="QA only: scroll fraction 0..1")
    parser.add_argument("--smoke-focus", choices=("cleaning", "apps", "tools", "disk", "turbo", "startup"))
    parser.add_argument("--smoke-profile", type=Path, help="QA only: geometry/render navigation measurements")
    args = parser.parse_args(argv)
    if args.capture and not args.smoke_test:
        parser.error("--capture requires --smoke-test")
    if not args.smoke_test and (args.smoke_tab is not None or args.smoke_all_sections or args.smoke_width
                                or args.smoke_height or args.smoke_language
                                or args.smoke_scenario != "default" or args.smoke_scroll or args.smoke_focus
                                or args.smoke_profile):
        parser.error("smoke viewport options require --smoke-test")
    if not 0 <= args.smoke_scroll <= 1:
        parser.error("--smoke-scroll must be between 0 and 1")
    if args.smoke_width is not None and args.smoke_width < 760:
        parser.error("--smoke-width must be at least 760")
    if args.smoke_height is not None and args.smoke_height < 480:
        parser.error("--smoke-height must be at least 480")
    if args.smoke_all_sections and not args.capture:
        parser.error("--smoke-all-sections requires --capture")
    if args.panacea_update_helper:
        from modules.update_install import run_update_helper
        return run_update_helper(args.panacea_update_helper)
    if args.panacea_update_ready and (
        not getattr(sys, "frozen", False) or Path(sys.executable).name != "Panacea.exe"
    ):
        # Never acknowledge replacement of a QA executable or a Python interpreter.
        print("Updater readiness requires a protected, packaged Panacea.exe", file=sys.stderr)
        return 4
    if args.smoke_backend_imports:
        # Import only; never instantiate a manager or start a Windows process.
        from importlib import import_module
        for module, cls in (
            ("modules.commands", "CommandRunner"),
            ("modules.cleanup", "CleanupManager"),
            ("modules.disk", "DiskOptimizer"),
            ("modules.restore", "RestoreManager"),
            ("modules.performance", "PerformanceManager"),
            ("modules.maintenance_guard", "MaintenanceGuard"),
        ):
            if not callable(getattr(import_module(module), cls, None)):
                raise RuntimeError(f"Missing packaged backend: {module}")
        return 0
    if os.name == 'nt' and not args.smoke_test:
        from modules.utils import is_admin
        if not is_admin():
            frozen = bool(getattr(sys, "frozen", False))
            startup_argv = sys.argv if argv is None else [sys.argv[0], *argv]
            parameters = elevation_arguments(startup_argv, frozen=frozen)
            if frozen:
                os.environ['PYINSTALLER_RESET_ENVIRONMENT'] = '1'
            code = ctypes.windll.shell32.ShellExecuteW(None, 'runas', sys.executable, parameters, None, 1)
            if code <= 32:
                print(f'Administrator elevation declined or failed ({code})', file=sys.stderr)
                return 1
            return 0
    from qt_app.branding import application_id, configure_windows_identity
    app_id = application_id(smoke=args.smoke_test, frozen=bool(getattr(sys, "frozen", False)), executable=sys.executable)
    if os.name == "nt":
        app_id = configure_windows_identity(app_id)
    _qa_trace("creating QGuiApplication")
    QQuickStyle.setStyle("Basic")
    app = QGuiApplication([sys.argv[0]])
    _qa_trace("QGuiApplication created")
    icon = (Path(getattr(sys, "_MEIPASS", ROOT)) / "assets" / "panacea_icon.ico")
    if icon.is_file():
        app.setWindowIcon(QIcon(str(icon)))
    if args.smoke_test and os.name == "nt" and os.environ.get("QT_QPA_PLATFORM") == "offscreen":
        # The offscreen QPA has no Windows font catalog. Without registering
        # platform-owned fonts, screenshots can display tofu despite a fully
        # legible native Windows window. QA loads the system fonts in-memory;
        # no font files are embedded or distributed with Panacea.
        fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
        registered = []
        for filename in ("SegUIVar.ttf", "segoeui.ttf", "segoeuib.ttf", "seguisb.ttf", "seguisym.ttf"):
            installed = fonts / filename
            if installed.is_file():
                family_id = QFontDatabase.addApplicationFont(str(installed))
                if family_id >= 0:
                    registered.extend(QFontDatabase.applicationFontFamilies(family_id))
        if not registered:
            print("Qt offscreen QA: Windows Segoe UI fonts unavailable", file=sys.stderr)
            return 4
        print("Qt offscreen QA fonts:", ", ".join(sorted(set(registered))), flush=True)

    settings = AppSettings(smoke=args.smoke_test, defer_load=bool(args.panacea_update_ready))
    translator = I18n(settings, language_override=args.smoke_language)
    metrics = MetricsBridge()
    reader = ReadBridge()
    reader._automatic_updates = not args.smoke_test
    if args.smoke_test:
        from qt_app.qa_fixtures import VisualMaintenance, VisualUpdates, apply_scenario, run_smoke
        requested = args.smoke_tab or "home"
        section = SMOKE_SECTIONS[int(requested)] if requested.isdecimal() else requested
        section = FOCUS_SECTIONS.get(args.smoke_focus, section)
        maintenance = MaintenanceBridge(service=VisualMaintenance())
        updater = UpdateBridge(reader, maintenance, flow=VisualUpdates())
        apply_scenario(metrics, reader, maintenance, updater, args.smoke_scenario, section, translator.language)
    else:
        maintenance = MaintenanceBridge()
        updater = UpdateBridge(reader, maintenance, on_ready=app.quit)
    maintenance.setLanguage(translator.language)
    translator.languageChanged.connect(lambda: maintenance.setLanguage(translator.language))
    updater.releaseNotesAvailable.connect(settings.cacheReleaseNotes)
    updater.auto_check_enabled = lambda: settings.autoCheck
    reader._maintenance = maintenance
    reader._updater = updater
    maintenance._reader = reader
    maintenance._updater = updater
    for service in (updater, metrics, reader, maintenance):
        app.aboutToQuit.connect(service.stop)

    engine = QQmlApplicationEngine()
    qml_warnings = []

    def qml_warning(errors):
        qml_warnings.extend(error.toString() for error in errors)
        _qa_trace("QML warnings: " + "; ".join(error.toString() for error in errors))

    engine.warnings.connect(qml_warning)
    source = Path(getattr(sys, "_MEIPASS", ROOT)) / "qt_app" / "Main.qml"
    extensions = configure_context(engine, source.parent, settings, translator, reader, maintenance,
                                   updater, metrics, smoke=args.smoke_test)
    _qa_trace("loading QML")
    engine.load(QUrl.fromLocalFile(str(source)))
    _qa_trace("QML load returned")
    if not engine.rootObjects():
        for service in (updater, metrics, reader, maintenance):
            service.stop()
        return 2
    window = engine.rootObjects()[0]
    if args.smoke_test:
        run_smoke(app, window, args, section, translator.language, qml_warnings, app_id, _qa_trace)
    else:
        if args.panacea_update_ready:
            def acknowledge_update():
                from modules.update_install import acknowledge_ready
                try:
                    ready = acknowledge_ready(sys.executable, args.panacea_update_ready)
                except Exception as exc:
                    print(f"Protected updater acknowledgment failed: {exc}", file=sys.stderr)
                    ready = False
                if not ready:
                    app.exit(4)
                    return
                settings.finishStartup(True)
            QTimer.singleShot(0, acknowledge_update)
        else:
            QTimer.singleShot(0, lambda: settings.finishStartup(False))
        QTimer.singleShot(0, lambda: reader.request("hardware"))
        QTimer.singleShot(2000, lambda: _check_initial_release_when_idle(reader, maintenance, updater))
        QTimer.singleShot(0, metrics.start)
    _qa_trace("event loop entering")
    result = app.exec()
    _qa_trace("event loop exited")
    engine.deleteLater()
    app.sendPostedEvents(None, QEvent.DeferredDelete)
    del extensions
    _qa_trace("QML engine disposed")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
