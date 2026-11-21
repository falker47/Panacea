"""Exercise the real metric cards offscreen. The shared harness never starts a native service."""
from contextlib import contextmanager
from functools import wraps
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]


def page_test(section, language="en", scenario="default"):
    """Qt Quick needs a QGuiApplication. Isolate it from unittest's existing QCoreApplication."""
    def decorate(test):
        @wraps(test)
        def run(case):
            module = type(case).__module__.split(".")[-1]
            target = f"qt_app.tests.{module}.{type(case).__name__}.{test.__name__}"
            if os.environ.get("PANACEA_QT_PAGE_TEST") == target:
                with _fixture(section, language, scenario) as fixture:
                    test(case, fixture)
                    case.assertEqual(fixture.warnings, [])
                return
            env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software",
                       PANACEA_QT_PAGE_TEST=target, PYTHONUTF8="1")
            result = subprocess.run([sys.executable, "-m", "unittest", target], cwd=ROOT, env=env,
                                    capture_output=True, text=True, encoding="utf-8", timeout=30)
            case.assertEqual(result.returncode, 0, result.stderr[-4000:])
        return run
    return decorate


def descendants(item):
    yield item
    for child in item.childItems():
        yield from descendants(child)


def find(item, name, *, visible=True):
    return next(node for node in descendants(item) if node.objectName() == name and (not visible or node.isVisible()))


def value(item, key):
    result = item.property(key)
    return result.toVariant() if hasattr(result, "toVariant") else result


@contextmanager
def _fixture(section, language, scenario):
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQuick import QQuickView

    from qt_app.i18n import I18n
    from qt_app.main import MaintenanceBridge, MetricsBridge, ReadBridge, configure_context
    from qt_app.qa_fixtures import VisualMaintenance, VisualUpdates, apply_scenario
    from qt_app.settings import AppSettings
    from qt_app.update_bridge import UpdateBridge

    app = QGuiApplication([])
    read = ReadBridge()
    metrics = MetricsBridge()
    backend = VisualMaintenance()
    maintenance = MaintenanceBridge(service=backend)
    updater = UpdateBridge(read, maintenance, flow=VisualUpdates())
    settings = AppSettings(smoke=True)
    settings.languageChoice = language
    strings = I18n(settings)
    apply_scenario(metrics, read, maintenance, updater, scenario, section, language)
    read._maintenance, read._updater = maintenance, updater
    maintenance._reader, maintenance._updater = read, updater
    view = QQuickView()
    warnings = []
    view.engine().warnings.connect(lambda errors: warnings.extend(error.toString() for error in errors))
    base = ROOT / "qt_app"
    with patch("qt_app.main.load_extensions", return_value={}):
        configure_context(view.engine(), base, settings, strings, read, maintenance, updater, metrics, smoke=True)
    # Integrating branches may supply extensions. This harness validates the standalone T3 host.
    view.rootContext().setContextProperty("featureUrls", {})
    view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
    view.resize(760, 480)
    view.setInitialProperties({"section": section})
    view.setSource(QUrl.fromLocalFile(str(base / "qml" / "pages" / "SectionPage.qml")))
    view.show()
    app.processEvents()
    try:
        page = view.rootObject()
        if page is None:
            raise AssertionError(warnings)
        yield SimpleNamespace(page=page, app=app, view=view, warnings=warnings, reader=read, metrics=metrics,
                              maintenance=maintenance, backend=backend, updater=updater, strings=strings,
                              settings=settings)
    finally:
        view.setSource(QUrl())
        view.close()
        for service in (updater, metrics, read, maintenance):
            service.stop()
        app.processEvents()


class MetricCardTests(unittest.TestCase):
    @page_test("home", "it")
    def test_history_and_localized_values_update_without_recreating_cards(self, f):
        card = find(f.page, "metric_cpu")
        graph = find(card, "metric_graph_cpu")
        self.assertEqual(value(find(card, "value_cpu"), "text"), "30,8%")
        self.assertEqual(value(graph, "history"), f.metrics.cpuHistory)
        self.assertEqual(len(f.metrics.cpuHistory), 11)
        self.assertGreater(graph.height(), 0)
        f.metrics._apply(dict(f.metrics._values, cpu="12.4%"))
        f.app.processEvents()
        self.assertEqual(card, find(f.page, "metric_cpu"))
        self.assertEqual(graph, find(card, "metric_graph_cpu"))
        self.assertEqual(value(graph, "history")[-1], 12.4)
        self.assertEqual(value(find(card, "value_cpu"), "text"), "12,4%")
        f.settings.languageChoice = "en"
        self.assertEqual(value(find(card, "value_cpu"), "text"), "12.4%")
        self.assertIn("14.5 GB used", value(find(f.page, "metric_ram"), "caption"))

    @page_test("home", scenario="unknown")
    def test_unavailable_samples_have_no_synthesized_history_or_percentage(self, f):
        for metric in ("cpu", "ram", "disk"):
            card = find(f.page, f"metric_{metric}")
            self.assertEqual(value(find(card, f"value_{metric}"), "text"), "Unavailable")
            self.assertLess(value(card, "percent"), 0)
        self.assertEqual(value(find(f.page, "metric_graph_cpu"), "history"), [])
        self.assertEqual(value(find(f.page, "metric_graph_ram"), "history"), [])


if __name__ == "__main__":
    unittest.main()
