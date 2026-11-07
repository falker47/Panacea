"""Render real QML in a separate GUI process; never invoke a backend operation."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QTimer, QUrl  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from qt_app.main import MetricsBridge, ReadBridge, MaintenanceBridge  # noqa: E402
from qt_app.icon_provider import NavigationIconProvider  # noqa: E402
from qt_app.update_bridge import UpdateBridge  # noqa: E402


def main():
    app = QGuiApplication([])
    metrics, reader, maintenance = MetricsBridge(), ReadBridge(), MaintenanceBridge()
    metrics._values.update(cpu="30.8%", ram="90.7%", disk="97.5%")
    reader._results["hardware"] = {"os": "Windows 11", "cpu_name": "AMD Ryzen 7"}
    updater = UpdateBridge(reader, maintenance)
    engine = QQmlApplicationEngine()
    warnings = []
    engine.warnings.connect(lambda errors: warnings.extend(str(e) for e in errors))
    engine.addImageProvider("panacea-nav", NavigationIconProvider())
    for name, value in {"applicationLanguage": "en", "qaSmokeMode": True,
                        "liveMetrics": metrics, "readService": reader,
                        "maintenanceService": maintenance, "updateService": updater}.items():
        engine.rootContext().setContextProperty(name, value)
    engine.load(QUrl.fromLocalFile(str(ROOT / "qt_app/Main.qml")))
    window = engine.rootObjects()[0]
    window.setWidth(int(sys.argv[1]))
    window.setHeight(int(sys.argv[2]))
    window.setProperty("currentTab", int(sys.argv[3]) if len(sys.argv) > 3 else 0)

    def items(root):
        yield root
        for child in root.childItems():
            yield from items(child)

    def measure():
        visible = [i for i in items(window.contentItem()) if i.isVisible()]
        def text_item(text):
            return next(i for i in visible if i.property("text") == text)
        def box(item):
            p = item.mapToScene(item.boundingRect().topLeft())
            return [round(p.x(), 2), round(p.y(), 2), round(item.width(), 2), round(item.height(), 2)]
        def card(text):
            item = text_item(text)
            return box(item.parentItem().parentItem().parentItem())
        tab = int(window.property("currentTab"))
        result = {"warnings": warnings}
        if tab == 0:
            result.update(windows=card("Windows 11"), updates=card("Windows Update"),
                          metrics=[card(t) for t in ("CPU", "Memory (RAM)", "System drive")])
        if tab == 4:
            steps = sorted((i for i in visible if i.objectName().startswith("resurrection_step_")),
                           key=lambda i: int(i.objectName().rsplit("_", 1)[-1]))
            result["steps"] = [box(i) for i in steps]
        print(json.dumps(result), flush=True)
        app.quit()
    QTimer.singleShot(400, measure)
    app.aboutToQuit.connect(metrics.stop)
    app.aboutToQuit.connect(reader.stop)
    app.aboutToQuit.connect(maintenance.stop)
    app.aboutToQuit.connect(updater.stop)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
