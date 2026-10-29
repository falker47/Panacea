"""Qt application migration: isolated read-only service integration."""
from __future__ import annotations
import argparse
import ctypes
import json
import os
import subprocess
from pathlib import Path
import sys

from PySide6.QtCore import QObject, Property, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from qt_app.icon_provider import NavigationIconProvider

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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
            if action == 'drives':
                self._drives = [row['letter'] for row in value.get('drives', []) if row.get('available') is True]
            self.changed.emit()
        def failed(exc):
            self._state = "error"
            self._last = "Dati non disponibili: " + str(exc)
            self.changed.emit()
        def done():
            self._busy = False
            self.changed.emit()
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
        self._output = "Nessuna manutenzione eseguita."
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
        self.changed.emit()

        def log(message):
            self._dispatcher.post(lambda: self._append(str(message)))

        def progress(done, total, label):
            def apply():
                self._progress_done = done
                self._progress_total = total
                self._append(f"{done}/{total}: {label}")
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

        accepted = self._workers.start(
            "maintenance", lambda: self._service.execute(nonce, log=log, progress=progress),
            group="maintenance", on_success=success, on_error=failure, on_done=done)
        if not accepted:
            self._service.reject()
            self._append("Operazione non avviata: worker occupato.")
            done()

    def _append(self, message):
        self._output = (self._output + "\n" + message)[-16000:]
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
    args = parser.parse_args(argv)
    if args.capture and not args.smoke_test:
        parser.error("--capture requires --smoke-test")
    if not args.smoke_test and (args.smoke_tab != 0 or args.smoke_width
                                or args.smoke_height or args.smoke_language):
        parser.error("smoke viewport options require --smoke-test")
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
    app = QGuiApplication([sys.argv[0]])
    metrics = MetricsBridge()
    reader = ReadBridge()
    maintenance = MaintenanceBridge()
    updater = UpdateBridge(reader, maintenance, on_ready=app.quit)
    reader._maintenance = maintenance
    reader._updater = updater
    maintenance._reader = reader
    maintenance._updater = updater
    app.aboutToQuit.connect(updater.stop)
    app.aboutToQuit.connect(metrics.stop)
    app.aboutToQuit.connect(reader.stop)
    app.aboutToQuit.connect(maintenance.stop)
    engine = QQmlApplicationEngine()
    engine.addImageProvider("panacea-nav", NavigationIconProvider())
    engine.rootContext().setContextProperty("applicationLanguage", resolve_language())
    engine.rootContext().setContextProperty("qaSmokeMode", bool(args.smoke_test))
    engine.rootContext().setContextProperty("liveMetrics", metrics)
    engine.rootContext().setContextProperty("readService", reader)
    engine.rootContext().setContextProperty("maintenanceService", maintenance)
    engine.rootContext().setContextProperty("updateService", updater)
    source = ((Path(getattr(sys, "_MEIPASS")) / "qt_app" / "Main.qml")
              if getattr(sys, "frozen", False)
              else Path(__file__).with_name("Main.qml"))
    engine.load(QUrl.fromLocalFile(str(source)))
    if not engine.rootObjects():
        updater.stop()
        reader.stop()
        maintenance.stop()
        metrics.stop()
        return 2
    if not args.smoke_test:
        # The original V2 loads metadata without a manual "read" click.
        QTimer.singleShot(0, lambda: reader.request("hardware"))
    if args.smoke_test:
        window = engine.rootObjects()[0]

        def configure_qa_view():
            if args.smoke_width is not None:
                window.setWidth(args.smoke_width)
            if args.smoke_height is not None:
                window.setHeight(args.smoke_height)
            if args.smoke_language is not None:
                window.setProperty("language", args.smoke_language)
            window.setProperty("currentTab", args.smoke_tab)

        QTimer.singleShot(0, configure_qa_view)
        if args.capture:
            def capture():
                args.capture.parent.mkdir(parents=True, exist_ok=True)
                try:
                    # A successful root shell load does not prove the selected
                    # lazy subview compiled; require its actual QML object.
                    if not (int(window.property("loadedMask") or 0) & (1 << args.smoke_tab)):
                        raise RuntimeError("Selected Qt V2 page was not created")
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
                        }, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8",
                    )
                except Exception as exc:
                    print(f"Qt UI screenshot failure: {exc}", file=sys.stderr, flush=True)
                    app.exit(3)
            QTimer.singleShot(950, capture)
        QTimer.singleShot(1600 if args.capture else 1200, app.quit)
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
        QTimer.singleShot(0, metrics.start)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
