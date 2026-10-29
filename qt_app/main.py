"""Qt application migration: isolated read-only service integration."""
from __future__ import annotations
import argparse
from pathlib import Path
import sys

from PySide6.QtCore import QObject, Property, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.ui_dispatch import UiDispatcher, WorkerController  # noqa: E402
from qt_app.services import READ_ACTIONS, ReadService  # noqa: E402
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

    @Slot(str)
    def request(self, action):
        if self._closed or action not in READ_ACTIONS or self._busy:
            return
        self._busy = True
        self._last = "Verifica in corso, nessuna operazione di manutenzione."
        self.changed.emit()
        def successful(value):
            self._last = str(value)
            self.changed.emit()
        def failed(exc):
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


def main(argv=None):
    parser = argparse.ArgumentParser(description="Panacea Qt UI migration QA")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--capture", type=Path, help="Save a QA screenshot with --smoke-test")
    args = parser.parse_args(argv)
    if args.capture and not args.smoke_test:
        parser.error("--capture requires --smoke-test")
    app = QGuiApplication([sys.argv[0]])
    metrics = MetricsBridge()
    reader = ReadBridge()
    app.aboutToQuit.connect(metrics.stop)
    app.aboutToQuit.connect(reader.stop)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("liveMetrics", metrics)
    engine.rootContext().setContextProperty("readService", reader)
    source = ((Path(getattr(sys, "_MEIPASS")) / "qt_app" / "Main.qml")
              if getattr(sys, "frozen", False)
              else Path(__file__).with_name("Main.qml"))
    engine.load(QUrl.fromLocalFile(str(source)))
    if not engine.rootObjects():
        reader.stop()
        metrics.stop()
        return 2
    if args.smoke_test:
        if args.capture:
            def capture():
                args.capture.parent.mkdir(parents=True, exist_ok=True)
                try:
                    window = engine.rootObjects()[0]
                    screen = window.screen()
                    if screen is None:
                        raise RuntimeError("Qt window has no screen")
                    img = screen.grabWindow(int(window.winId()))
                    if img.isNull() or not img.save(str(args.capture)):
                        raise RuntimeError("Qt screenshot is empty or cannot be saved")
                except Exception as exc:
                    print(f"Qt UI screenshot failure: {exc}", file=sys.stderr, flush=True)
                    app.exit(3)
            QTimer.singleShot(550, capture)
        QTimer.singleShot(1200, app.quit)
    else:
        QTimer.singleShot(0, metrics.start)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
