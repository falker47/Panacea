"""Qt application migration: isolated read-only service integration."""
from __future__ import annotations
import argparse
import ctypes
import json
import os
import subprocess
from pathlib import Path
import sys
import time
import faulthandler
import hashlib

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

from PySide6.QtCore import QEvent, QObject, QPointF, Property, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication, QFontDatabase, QIcon
from PySide6.QtQml import QQmlApplicationEngine

_qa_trace("Qt imports complete")

_ACTION_SCOPES = {
    **dict.fromkeys(("temp_clean", "browser_clean", "recycle_empty", "component_cleanup", "quick_cleanup", "open_cleanmgr"), "cleaning"),
    **dict.fromkeys(("sfc", "dism_check", "dism_restore", "dns_flush", "winsock_reset", "restore_point"), "tools"),
    **dict.fromkeys(("drive_optimize", "chkdsk", "open_defrag", "battery_report"), "disk"),
    "resurrection": "resurrect",
}

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qt_app.icon_provider import NavigationIconProvider  # noqa: E402
from modules.localization import resolve_language  # noqa: E402
from modules.ui_dispatch import UiDispatcher, WorkerController  # noqa: E402
from qt_app.services import READ_ACTIONS, ReadService  # noqa: E402
from qt_app.catalog import cards  # noqa: E402
from qt_app.confirmation_copy import confirmation_text  # noqa: E402
from qt_app.elevation import elevation_arguments  # noqa: E402
from qt_app.update_bridge import UpdateBridge  # noqa: E402
from qt_lab.main import MetricsBridge  # noqa: E402


class ReadBridge(QObject):
    changed = Signal()

    @Slot(str, str, str, result=str)
    def localizedCopy(self, italian, english, language):
        from modules.localization import translate
        rendered = translate(english, language)
        return italian if language == "it" and rendered == english else rendered

    def __init__(self, parent=None):
        super().__init__(parent)
        self._service = ReadService()
        self._dispatcher = UiDispatcher()
        self._workers = WorkerController(self._dispatcher)
        self._last = "Seleziona una verifica in sola lettura."
        self._busy = False
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
        if (self._closed or action not in READ_ACTIONS or self._busy
                or (self._maintenance is not None and self._maintenance.busy)
                or (self._updater is not None and self._updater.busy)):
            return
        self._busy = True
        self._state = "running"
        self._last_action = action
        self._last = "Verifica in corso, nessuna operazione di manutenzione."
        self.changed.emit()
        def successful(value):
            self._results = {**self._results, action: value}
            self._state = "completed"
            self._last = json.dumps(value, ensure_ascii=False, indent=2)
            scope = {"temp_preview": "cleaning", "drives": "disk"}.get(action)
            if scope:
                self._section_logs = {**self._section_logs, scope: self._last[-16000:]}
            if action == 'drives':
                self._drives = [row['letter'] for row in value.get('drives', []) if row.get('available') is True]
            self.changed.emit()
        def failed(exc):
            self._state = "error"
            self._last = "Dati non disponibili: " + str(exc)
            self._results = {**self._results, action: {"available": False, "error": str(exc)}}
            if action == "drives":
                self._drives = []
            scope = {"temp_preview": "cleaning", "drives": "disk"}.get(action)
            if scope:
                self._section_logs = {**self._section_logs, scope: self._last}
            self.changed.emit()
        def done():
            self._busy = False
            self.changed.emit()
            if (action == "hardware" and getattr(self, "_automatic_updates", False)
                    and not self._closed):
                self._automatic_updates = False
                QTimer.singleShot(0, lambda: self.request("windows_updates"))
        accepted = self._workers.start(
            action, lambda: self._service.collect(action),
            group="read", on_success=successful, on_error=failed, on_done=done)
        if not accepted:
            done()

    def stop(self):
        self._closed = True
        self._timer.stop()
        self._workers.close()
        from threading import Thread
        Thread(target=self._service.close, name="panacea-read-close", daemon=False).start()



class MaintenanceBridge(QObject):
    """One-use confirmation broker; backend execution never runs on the QML thread."""
    changed = Signal()

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

    @Property('QVariantList', notify=changed)
    def actionCards(self):
        return [[item for item in page if item['action']] for page in cards(self._language)]

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
                "total": self._progress_total, "steps": list(self._steps)}}

    @Property(str, notify=changed)
    def activeSection(self):
        return _ACTION_SCOPES.get(self._last_action, "")

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

    @Slot(str, str)
    def prepare(self, action, drive):
        if (self._closed or self._busy or (self._reader is not None and self._reader.busy)
                or (self._updater is not None and self._updater.busy)):
            return
        self.reject()
        try:
            data = self._service.prepare(action, drive)
            self._pending = data["nonce"]
            self._prepared_action = action
            title, warning = confirmation_text(action, data, self._language)
            self._details = title + "\n" + warning
        except (ValueError, RuntimeError) as exc:
            self._output = "Azione rifiutata: " + str(exc)
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
        self._last_action = self._prepared_action
        self._prepared_action = ""
        self._pending = ""
        self._details = ""
        self._busy = True
        self._result_status = "running"
        self._progress_done = 0
        self._progress_total = 10 if self._last_action == "resurrection" else (3 if self._last_action == "quick_cleanup" else 0)
        self._steps = []
        self._output = "Manutenzione in corso. Non chiudere il programma."
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
            self._append(self._result_status + ": " + result.get("message", ""))

        def failure(exc):
            self._result_status = "failed"
            self._append("Errore o completamento da verificare: " + str(exc))

        def done():
            self._busy = False
            self.changed.emit()

            # Reflect the measured state after an acknowledged change, as V2 does.
            # Failed/unknown/cancelled completion never implies a successful toggle.
            from qt_app.maintenance import TURBO
            if (self._last_action in TURBO and self._reader is not None
                    and self._result_status in ("completed", "partial") and not self._closed):
                QTimer.singleShot(0, lambda: self._reader.request("turbo_status"))

        accepted = self._workers.start(
            "maintenance", lambda: self._service.execute(nonce, log=log, progress=progress),
            group="maintenance", on_success=success, on_error=failure, on_done=done)
        if not accepted:
            self._service.reject()
            self._append("Operazione non avviata: worker occupato.")
            done()

    def _append(self, message):
        self._output = (self._output + "\n" + message)[-16000:]
        scope = _ACTION_SCOPES.get(self._last_action)
        if scope:
            self._section_logs = {**self._section_logs, scope:
                                  (self._section_logs.get(scope, "") + "\n" + message)[-16000:]}
        self._remember_result()
        self.changed.emit()

    @Slot()
    def cancel(self):
        if self._busy:
            self._service.cancel()
            self._append("Annullamento richiesto. Il comando Windows corrente potrebbe proseguire.")

    def stop(self):
        self._closed = True
        self._timer.stop()
        self._service.close()
        self._workers.close()

def _check_initial_release_when_idle(reader, maintenance, updater):
    """One metadata check after startup reads finish; never download or install."""
    if updater._closed:
        return False
    if reader.busy or maintenance.busy or updater.busy or updater.pending:
        QTimer.singleShot(1000, lambda: _check_initial_release_when_idle(reader, maintenance, updater))
        return False
    updater.check()
    return True


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
    parser.add_argument("--smoke-tab", type=int, choices=range(5), default=0,
                        help="QA only: navigate to one of the five V2 groups")
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
    if not args.smoke_test and (args.smoke_tab != 0 or args.smoke_width
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
        for filename in ("segoeui.ttf", "segoeuib.ttf", "seguisb.ttf", "seguisym.ttf"):
            installed = fonts / filename
            if installed.is_file():
                family_id = QFontDatabase.addApplicationFont(str(installed))
                if family_id >= 0:
                    registered.extend(QFontDatabase.applicationFontFamilies(family_id))
        if not registered:
            print("Qt offscreen QA: Windows Segoe UI fonts unavailable", file=sys.stderr)
            return 4
        print("Qt offscreen QA fonts:", ", ".join(sorted(set(registered))), flush=True)

    metrics = MetricsBridge()
    reader = ReadBridge()
    reader._automatic_updates = not args.smoke_test
    if args.smoke_test:
        # Deterministic visual fixture, never enabled for an interactive launch.
        # The reference V2 captures show a high-usage disk and RAM condition.
        metrics._values.update({
            "cpu": "30.8%", "ram": "90.7%", "disk": "97.5%",
            "details": {
                "ram": [16.0, 1.5, 90.7], "disk": [256.0, 6.4, 97.5],
                "battery": 72, "power": "Plugged In",
                "uptime": "0d 3h 8m",
            },
        })
        metrics._history["cpu"] = [17, 16, 18, 19, 17, 24, 27, 31, 30, 32, 30.8]
        metrics._history["ram"] = [84, 84.3, 85, 85.1, 86, 88, 89, 90.7]
        reader._results["hardware"] = {
            "os": "Windows 11", "cpu_name": "AMD Ryzen 7",
            "ram_info": "16.0 GB RAM", "disk_model": "System SSD",
        }
    if args.smoke_test:
        from qt_app.qa_fixtures import VisualMaintenance, VisualUpdates, apply_scenario
        maintenance = MaintenanceBridge(service=VisualMaintenance())
        apply_scenario(metrics, reader, maintenance, args.smoke_scenario,
                       args.smoke_tab, args.smoke_language or resolve_language(), args.smoke_focus)
    else:
        maintenance = MaintenanceBridge()
    updater = UpdateBridge(reader, maintenance, flow=VisualUpdates() if args.smoke_test else None, on_ready=app.quit)
    reader._maintenance = maintenance
    reader._updater = updater
    maintenance._reader = reader
    maintenance._updater = updater
    app.aboutToQuit.connect(updater.stop)
    app.aboutToQuit.connect(metrics.stop)
    app.aboutToQuit.connect(reader.stop)
    app.aboutToQuit.connect(maintenance.stop)
    _qa_trace("bridges created")
    engine = QQmlApplicationEngine()
    qml_warnings = []
    def qml_warning(errors):
        qml_warnings.extend(str(error) for error in errors)
        _qa_trace("QML warnings: " + "; ".join(str(error) for error in errors))
    engine.warnings.connect(qml_warning)
    engine.addImageProvider("panacea-nav", NavigationIconProvider())
    engine.rootContext().setContextProperty("applicationLanguage", resolve_language())
    engine.rootContext().setContextProperty("qaSmokeMode", bool(args.smoke_test))
    native_confirmations = os.name == "nt" and not args.smoke_test and app.platformName() == "windows"
    engine.rootContext().setContextProperty("nativeConfirmationsEnabled", native_confirmations)
    engine.rootContext().setContextProperty("liveMetrics", metrics)
    engine.rootContext().setContextProperty("readService", reader)
    engine.rootContext().setContextProperty("maintenanceService", maintenance)
    engine.rootContext().setContextProperty("updateService", updater)
    source = ((Path(getattr(sys, "_MEIPASS")) / "qt_app" / "Main.qml")
              if getattr(sys, "frozen", False)
              else Path(__file__).with_name("Main.qml"))
    _qa_trace("loading QML")
    engine.load(QUrl.fromLocalFile(str(source)))
    _qa_trace("QML load returned")
    if not engine.rootObjects():
        updater.stop()
        reader.stop()
        maintenance.stop()
        metrics.stop()
        return 2
    if not args.smoke_test:
        if native_confirmations:
            from qt_app.native_dialogs import NativeConfirmations
            NativeConfirmations(maintenance, updater, lambda: int(engine.rootObjects()[0].winId()), parent=app)
        # The original V2 loads metadata without a manual "read" click.
        QTimer.singleShot(0, lambda: reader.request("hardware"))
    if args.smoke_test:
        window = engine.rootObjects()[0]
        qa_configured = [False]

        def configure_qa_view():
            if args.smoke_width is not None:
                window.setWidth(args.smoke_width)
            if args.smoke_height is not None:
                window.setHeight(args.smoke_height)
            if args.smoke_language is not None:
                window.setProperty("language", args.smoke_language)
            window.setProperty("currentTab", args.smoke_tab)
            def configure_page():
                def visual_items(item):
                    yield item
                    for child in item.childItems():
                        yield from visual_items(child)
                page = next((item for item in visual_items(window.contentItem())
                             if item.objectName() == "parityPage_" + str(args.smoke_tab)), None)
                if page is None:
                    _qa_trace("Selected fixture page not created")
                    app.exit(3)
                    return
                if args.smoke_scenario == "expanded":
                    page.setProperty("showIndividualCleaning", True)
                    page.setProperty("showExtraDriveTools", True)
                    for item in visual_items(page):
                        if item.metaObject().indexOfProperty("expanded") >= 0:
                            item.setProperty("expanded", True)
                def scroll():
                    viewport = next((item for item in visual_items(page) if item.objectName() == "pageViewport"), None)
                    if viewport is not None:
                        maximum = max(0, viewport.property("contentHeight") - viewport.height())
                        viewport.setProperty("contentY", maximum * args.smoke_scroll)
                        if args.smoke_focus:
                            target = next((item for item in visual_items(page) if item.objectName() == "legacyView_" + args.smoke_focus), None)
                            if target is not None:
                                offset = target.mapToItem(viewport, QPointF(0, 0)).y() + viewport.property("contentY") - 10
                                viewport.setProperty("contentY", max(0, min(maximum, offset)))
                            else:
                                _qa_trace("Requested fixture subview was not created")
                                app.exit(3)
                                return
                    qa_configured[0] = True
                    _qa_trace("fixture page configured")
                QTimer.singleShot(100, scroll)
            QTimer.singleShot(0, configure_page)

        QTimer.singleShot(0, configure_qa_view)
        if args.smoke_profile:
            def profile_navigation():
                try:
                    rows = []
                    for phase in ("first", "warm"):
                        for tab in range(5):
                            begun = time.perf_counter()
                            window.setProperty("currentTab", tab)
                            callback = time.perf_counter()
                            app.processEvents()
                            geometry = time.perf_counter()
                            frame = window.grabWindow()
                            if frame.isNull():
                                raise RuntimeError("Profile did not render the selected QML group")
                            rendered = time.perf_counter()
                            rows.append({"tab": tab, "phase": phase,
                                         "callback_ms": round((callback - begun) * 1000, 3),
                                         "geometry_ms": round((geometry - callback) * 1000, 3),
                                         "frame_capture_ms": round((rendered - geometry) * 1000, 3)})
                    window.setProperty("currentTab", args.smoke_tab)
                    args.smoke_profile.parent.mkdir(parents=True, exist_ok=True)
                    args.smoke_profile.write_text(json.dumps({
                        "fixture_only": True, "platform": app.platformName(),
                        "logical_size": [window.width(), window.height()],
                        "method": "GUI callback, event/geometry flush and software frame capture; not compositor latency",
                        "navigation": rows}, indent=2) + "\n", encoding="utf-8")
                    _qa_trace("navigation profile saved")
                except Exception as exc:
                    _qa_trace("navigation profile failed: " + str(exc))
                    app.exit(3)
            QTimer.singleShot(200, profile_navigation)
        if args.capture:
            def capture():
                _qa_trace("capture begin")
                args.capture.parent.mkdir(parents=True, exist_ok=True)
                try:
                    # A successful root shell load does not prove the selected
                    # lazy subview compiled; require its actual QML object.
                    if not (int(window.property("loadedMask") or 0) & (1 << args.smoke_tab)):
                        raise RuntimeError("Selected Qt V2 page was not created")
                    if not qa_configured[0]:
                        raise RuntimeError("Requested fixture configuration was not applied")
                    image = window.grabWindow()
                    if image.isNull():
                        screen = window.screen()
                        if screen is None:
                            raise RuntimeError("Qt window has no screen")
                        image = screen.grabWindow(int(window.winId()))
                    if image.isNull() or not image.save(str(args.capture)):
                        raise RuntimeError("Qt screenshot is empty or cannot be saved")
                    (args.capture.with_suffix(".json")).write_text(
                        json.dumps({
                            "tab": args.smoke_tab,
                            "language": args.smoke_language or resolve_language(),
                            "logical_size": [window.width(), window.height()],
                            "image_size": [image.width(), image.height()],
                            "qt_scale_factor": os.environ.get("QT_SCALE_FACTOR", "1"),
                            "safe_mode": True,
                            "visual_fixture": True,
                            "scenario": args.smoke_scenario,
                            "scroll_fraction": args.smoke_scroll,
                            "focus_view": args.smoke_focus,
                            "qml_warnings": qml_warnings,
                            "platform": app.platformName(),
                            "windows_application_id": app_id,
                            "scaling_method": "QT_SCALE_FACTOR simulation; no Windows display setting changed",
                            "source_sha256": {name: hashlib.sha256((source.parent / name).read_bytes()).hexdigest()
                                              for name in ("Main.qml", "ParityPage.qml")},
                        }, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8",
                    )
                    _qa_trace("capture saved")
                    if qml_warnings:
                        raise RuntimeError("QML emitted warnings; see capture metadata")
                except Exception as exc:
                    print(f"Qt UI screenshot failure: {exc}", file=sys.stderr, flush=True)
                    app.exit(3)
            QTimer.singleShot(950, capture)
        def finish_qa():
            _qa_trace("QA exit requested")
            # Only the inert visual fixture may release its synthetic busy flag.
            # The interactive close/cancellation safety policy is untouched.
            maintenance._busy = False
            app.exit(0)
        QTimer.singleShot(1600 if args.capture else 1200, finish_qa)
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
            # Only acknowledge after QML has loaded and the Qt event loop started.
            QTimer.singleShot(250, acknowledge_update)
        QTimer.singleShot(2000, lambda: _check_initial_release_when_idle(reader, maintenance, updater))
        QTimer.singleShot(0, metrics.start)
    _qa_trace("event loop entering")
    result = app.exec()
    _qa_trace("event loop exited")
    # Dispose QML while every Python context object is still alive. Relying on
    # local-variable finalization can leave bindings pointing at deleted bridges.
    engine.deleteLater()
    app.sendPostedEvents(None, QEvent.DeferredDelete)
    _qa_trace("QML engine disposed")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
