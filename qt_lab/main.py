"""Isolated Qt Quick UI experiment. No elevation, maintenance, updater or writes to host state."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import logging
from pathlib import Path
import statistics
import sys
import time

from PySide6.QtCore import QObject, Property, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
# Imported from the existing backend; it is never duplicated or modified.
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))


def _percent(value):
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return "Non disponibile"
    if not 0 <= number <= 100:
        return "Non disponibile"
    return f"{number:.1f}%"


def _format_sample(data):
    ram = data.get("ram")
    disk = data.get("disk")
    return {
        "cpu": _percent(data.get("cpu")),
        "ram": _percent(ram[2]) if isinstance(ram, (tuple, list)) and len(ram) > 2 else "Non disponibile",
        "disk": _percent(disk[2]) if isinstance(disk, (tuple, list)) and len(disk) > 2 else "Non disponibile",
    }


class MetricsBridge(QObject):
    """Pass read-only SystemMonitor snapshots to QML without blocking the GUI."""

    changed = Signal()
    sampleReady = Signal(object)

    def __init__(self):
        super().__init__()
        self._values = {"cpu": "—", "ram": "—", "disk": "—"}
        self._monitor = None
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="panacea-qt-lab")
        self._busy = False
        self._closed = False
        self._timer = QTimer(self)
        self._timer.setInterval(3000)
        self._timer.timeout.connect(self.refresh)
        self.sampleReady.connect(self._apply)

    @Property(str, notify=changed)
    def cpu(self):
        return self._values["cpu"]

    @Property(str, notify=changed)
    def ram(self):
        return self._values["ram"]

    @Property(str, notify=changed)
    def disk(self):
        return self._values["disk"]

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
                values = {"cpu": "Non disponibile", "ram": "Non disponibile", "disk": "Non disponibile"}
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
        if values != self._values:
            self._values = values
            self.changed.emit()

    def stop(self):
        self._closed = True
        self._timer.stop()
        if self._monitor is not None:
            self._monitor.close()
        self._executor.shutdown(wait=False, cancel_futures=True)


def _write_report(path, result):
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Panacea Qt Quick Lab — read-only navigation experiment")
    parser.add_argument("--smoke-test", action="store_true", help="Exercise sections and exit; no maintenance calls")
    parser.add_argument("--report", type=Path, help="Save measurement scope and navigation timings")
    parser.add_argument("--capture", type=Path, help="Capture Dashboard screenshot during --smoke-test")
    args = parser.parse_args(argv)
    if args.capture and not args.smoke_test:
        parser.error("--capture requires --smoke-test")

    begun = time.perf_counter()
    app = QGuiApplication([sys.argv[0]])
    bridge = MetricsBridge()
    app.aboutToQuit.connect(bridge.stop)

    engine = QQmlApplicationEngine()
    warnings = []
    engine.warnings.connect(lambda errors: warnings.extend(str(error) for error in errors))
    engine.rootContext().setContextProperty("liveMetrics", bridge)
    # PyInstaller relocates the entrypoint inside _MEIPASS. The bundled QML
    # file retains the qt_lab/ subdirectory added by --add-data.
    source = (
        Path(sys._MEIPASS) / "qt_lab" / "Main.qml"
        if getattr(sys, "frozen", False)
        else Path(__file__).resolve().parent / "Main.qml"
    )
    engine.load(QUrl.fromLocalFile(str(source)))
    root_objects = engine.rootObjects()
    if not root_objects:
        failure = {
            "error": "Qt Quick QML engine did not load a window",
            "qml_file_exists": source.is_file(),
            "qml_warnings": warnings,
            "frozen": bool(getattr(sys, "frozen", False)),
        }
        _write_report(args.report, failure)
        print(json.dumps(failure, ensure_ascii=False), file=sys.stderr, flush=True)
        bridge.stop()
        return 2
    window = root_objects[0]
    if args.smoke_test:
        print('qt-lab: qml loaded', flush=True)
    engine_loaded_ms = round((time.perf_counter() - begun) * 1000, 2)

    if not args.smoke_test:
        QTimer.singleShot(0, bridge.start)
        return app.exec()

    samples = []
    # First visits exercise cold page creation; second visits exercise cached navigation.
    itinerary = [(1, "cold"), (2, "cold"), (3, "cold"), (4, "cold"),
                 (0, "warm"), (1, "warm"), (2, "warm"), (3, "warm"),
                 (4, "warm"), (0, "warm")]

    def finalize():
        print('qt-lab: finalize', flush=True)
        if not window.isVisible() or window.width() < 800 or window.height() < 550:
            _write_report(args.report, {"error": "Qt Quick window is not usable", "navigation": samples})
            app.exit(1)
            return
        if args.capture:
            args.capture.parent.mkdir(parents=True, exist_ok=True)
            print('qt-lab: capturing window', flush=True)
            try:
                # QQmlApplicationEngine may wrap a QQuickWindow as QWindow.
                # QScreen.grabWindow accepts its native WId without downcasting.
                screen = window.screen()
                if screen is None:
                    raise RuntimeError("Qt Lab window is not attached to a screen")
                screenshot = screen.grabWindow(int(window.winId()))
                if screenshot.isNull() or not screenshot.save(str(args.capture)):
                    raise RuntimeError("Qt Quick screenshot unavailable")
            except Exception as exc:
                _write_report(args.report, {"error": str(exc), "navigation": samples})
                app.exit(1)
                return
        buckets = {
            group: [item["callback_and_events_ms"] for item in samples if item["phase"] == group]
            for group in ("cold", "warm")
        }
        report = {
            "source": "Panacea Qt Lab (PySide6 / Qt Quick)",
            "read_only": True,
            "engine_loaded_ms": engine_loaded_ms,
            "window_size": [window.width(), window.height()],
            "navigation": samples,
            "cold_median_ms": round(statistics.median(buckets["cold"]), 2),
            "warm_median_ms": round(statistics.median(buckets["warm"]), 2),
            "method": "One source Qt Quick process; set QML currentTab, process pending Qt events; no paint/compositor timing. Cold page loaders create on first visit; warm pages remain loaded. Read-only and no UAC.",
        }
        _write_report(args.report, report)
        print(json.dumps(report, ensure_ascii=False))
        app.quit()

    def navigate(position=0):
        if position == len(itinerary):
            QTimer.singleShot(350, finalize)
            return
        tab, phase = itinerary[position]
        print(f'qt-lab: navigate {tab} ({phase})', flush=True)
        before = time.perf_counter()
        success = window.setProperty("currentTab", tab)
        if not success:
            app.exit(3)
            return
        app.processEvents()
        samples.append({
            "page": ["Dashboard", "Cleaning", "Tools", "Turbo", "Resurrect"][tab],
            "phase": phase,
            "callback_and_events_ms": round((time.perf_counter() - before) * 1000, 2),
        })
        QTimer.singleShot(110, lambda: navigate(position + 1))

    QTimer.singleShot(300, navigate)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
