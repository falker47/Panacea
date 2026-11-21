"""Offscreen end-to-end probes. The subprocess owns a QGuiApplication and inert services."""
from __future__ import annotations

from functools import lru_cache
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


@lru_cache(maxsize=None)
def probe(case, language="en", scale=1):
    result = subprocess.run([sys.executable, str(Path(__file__)), case, language],
                            env=dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software",
                                     QT_SCALE_FACTOR=str(scale), QML_DISABLE_DISK_CACHE="1", PYTHONUTF8="1"),
                            cwd=ROOT, encoding="utf-8", capture_output=True, timeout=70)
    if result.returncode:
        raise AssertionError(result.stdout[-1500:] + result.stderr[-4000:])
    return json.loads(result.stdout.strip().splitlines()[-1])


def exercise(case, language):
    from PySide6.QtCore import QEvent, QObject, QPointF, Qt, QUrl
    from PySide6.QtGui import QFontDatabase, QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuickControls2 import QQuickStyle
    from PySide6.QtTest import QTest
    from qt_app.catalog import SECTIONS, SECTION_ACTIONS
    from qt_app.i18n import I18n
    from qt_app.main import MaintenanceBridge, MetricsBridge, ReadBridge, configure_context
    from qt_app.qa_fixtures import VisualMaintenance, VisualUpdates, apply_scenario
    from qt_app.settings import AppSettings
    from qt_app.update_bridge import UpdateBridge
    from qt_app.visual_review import inspect_window, items

    QQuickStyle.setStyle("Basic")
    app = QGuiApplication([])
    if os.name == "nt":
        for name in ("SegUIVar.ttf", "segoeui.ttf", "segoeuib.ttf", "seguisb.ttf"):
            path = Path(os.environ["WINDIR"]) / "Fonts" / name
            if path.is_file():
                QFontDatabase.addApplicationFont(str(path))
    reader = ReadBridge()
    service = VisualMaintenance()
    maintenance = MaintenanceBridge(service=service)
    metrics = MetricsBridge()
    updater = UpdateBridge(reader, maintenance, flow=VisualUpdates())
    settings = AppSettings(smoke=True)
    settings.languageChoice = language
    translator = I18n(settings)
    apply_scenario(metrics, reader, maintenance, updater, "default", "home", language)
    reader._maintenance, reader._updater = maintenance, updater
    maintenance._reader, maintenance._updater = reader, updater
    translator.languageChanged.connect(lambda: maintenance.setLanguage(translator.language))
    engine = QQmlApplicationEngine()
    warnings = []
    engine.warnings.connect(lambda errors: warnings.extend(e.toString() for e in errors))
    extensions = configure_context(engine, ROOT / "qt_app", settings, translator, reader, maintenance,
                                   updater, metrics, smoke=case != "lifecycle")
    engine.load(QUrl.fromLocalFile(str(ROOT / "qt_app/Main.qml")))
    assert engine.rootObjects(), warnings
    window = engine.rootObjects()[0]
    window.setWidth(760)
    window.setHeight(480)

    def wait(predicate, message):
        deadline = time.monotonic() + 5
        while not predicate() and time.monotonic() < deadline:
            QTest.qWait(10)
        assert predicate(), f"{message}; QML warnings: {warnings}"

    def find(name):
        return next((i for i in items(window.contentItem()) if i.isVisible() and i.objectName() == name), None)

    def focus_name():
        item = window.activeFocusItem()
        return item.objectName() if item is not None else ""

    def click(item):
        assert item is not None and item.isEnabled(), f"Control unavailable: {item}"
        # Bring the actual control into the viewport, as wheel or Tab navigation would.
        item.forceActiveFocus(Qt.FocusReason.TabFocusReason)
        QTest.qWait(8)
        center = item.mapToScene(QPointF(item.width()/2, item.height()/2)).toPoint()
        assert 0 <= center.x() < window.width() and 0 <= center.y() < window.height(), (item.objectName(), center)
        QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, center)

    def page_ready(section):
        page = find("page_" + section)
        return (window.property("section") == section and page is not None and page.property("ready")
                and page.width() > 1 and page.height() > 1)

    def go(section):
        click(find("nav_" + section))
        wait(lambda: page_ready(section), "navigation to " + section)
        QTest.qWait(15)

    def set_turbo(applied):
        reader._results["turbo_status"] = {"states": dict.fromkeys(("power", "visual", "sysmain", "wsearch", "spooler"), applied),
                                           "master": applied, "restore_available": True, "saved_count": 5}
        reader.changed.emit()

    def dismiss():
        QTest.keyClick(window, Qt.Key.Key_Escape)
        wait(lambda: not maintenance.awaitingConfirmation and find("cancelConfirmation") is None, "cancel consent")

    result = {}
    try:
        wait(lambda: page_ready("home"), "first page")
        QTest.qWait(120)
        if case == "actions":
            prepared = []
            for section, actions in SECTION_ACTIONS.items():
                for action in actions:
                    # Two input clicks, one destination and one named action.
                    go(section)
                    if section == "performance":
                        set_turbo(action.endswith("_off"))
                    button = find("action_" + action)
                    assert button is not None, (section, action)
                    click(button)
                    wait(lambda: find("cancelConfirmation") is not None, f"{section}/{action} consent")
                    assert maintenance.preparedAction == action, maintenance.preparedAction
                    assert not service.executed
                    dismiss()
                    prepared.append(action)
            result["actions"] = sorted(set(prepared))
        elif case == "consent":
            go("cleanup")
            click(find("action_temp_clean"))
            wait(lambda: focus_name() == "cancelConfirmation", "initial focus on Cancel")
            result["body"] = find("confirmationDetails").property("text")
            cycle = []
            for _ in range(4):
                QTest.keyClick(window, Qt.Key.Key_Tab)
                cycle.append(focus_name())
            result["cycle"] = cycle
            dismiss()
            maintenance.confirm()
            result["after_reject"] = len(service.executed)
            maintenance.prepare("temp_clean", "")
            wait(lambda: find("confirmConfirmation") is not None, "fresh confirmation")
            maintenance.reject()
            QTest.qWait(20)
            maintenance.confirm()
            result["after_stale"] = len(service.executed)
            maintenance.prepare("temp_clean", "")
            wait(lambda: find("confirmConfirmation") is not None, "reopen consent")
            click(find("confirmConfirmation"))
            wait(lambda: not maintenance.busy, "fixture completion")
            maintenance.confirm()
            result["executions"] = len(service.executed)
        elif case == "palette":
            QTest.keyClick(window, Qt.Key.Key_K, Qt.KeyboardModifier.ControlModifier)
            wait(lambda: focus_name() == "paletteSearch", "open palette")
            find("paletteSearch").setProperty("text", "file temporanei" if language == "en" else "temporary files")
            QTest.keyClick(window, Qt.Key.Key_Return)
            wait(lambda: find("cancelConfirmation") is not None, "prepare cross-language palette match")
            result.update(section=window.property("section"), action=maintenance.preparedAction, executions=len(service.executed))
            dismiss()
            shortcuts = []
            for key in (Qt.Key.Key_1, Qt.Key.Key_2, Qt.Key.Key_3, Qt.Key.Key_4, Qt.Key.Key_5, Qt.Key.Key_6, Qt.Key.Key_Comma):
                QTest.keyClick(window, key, Qt.KeyboardModifier.ControlModifier)
                QTest.qWait(10)
                shortcuts.append(window.property("section"))
            result["shortcuts"] = shortcuts
        elif case == "closing":
            cancels = []
            service.cancel = lambda: cancels.append(True)
            go("settings")
            maintenance._busy = True
            maintenance._last_action = "sfc"
            maintenance._result_status = "running"
            maintenance.changed.emit()
            QTest.qWait(20)
            result["before_show"] = window.property("section")
            click(find("activityShow"))
            result["after_show"] = window.property("section")
            result["maintenance_close"] = window.close()
            result["cancels"] = len(cancels)
            maintenance._busy = False
            updater._installing = True
            result["helper_close"] = window.close()
            result["visible"] = window.isVisible()
            updater._installing = False
        elif case == "lifecycle":
            requests = []
            original_request = reader._service.collect
            reader._service.collect = lambda key: (requests.append(key), original_request(key))[1]
            reader._busy = True
            reader._last_action = "hardware"
            reader.changed.emit()
            go("repair")
            go("performance")
            result["active_text"] = window.property("activityText")
            result["queued"] = list(reader._pending_reads)
            result["blocked"] = not find("action_turbo_off").isEnabled()
            reader._busy = False
            reader._drain_reads()
            wait(lambda: not reader.busy, "queued fixture reads")
            result["processed"] = requests
            for state in ({"refreshing": True}, {"available": False, "error": "fixture"}, {"states": {"power": True},
                          "master": True, "restore_available": True, "saved_count": 1}):
                reader._results["turbo_status"] = state
                reader.changed.emit()
                QTest.qWait(5)
                result.setdefault("restore", []).append(find("action_turbo_off").isEnabled())
            reader._drives = []
            reader._results["drives"] = {"available": False, "error": "fixture"}
            reader.changed.emit()
            result["drive_disabled"] = not find("action_drive_optimize").isEnabled()
        elif case == "keyboard":
            go("home")
            find("nav_home").forceActiveFocus(Qt.FocusReason.TabFocusReason)
            chain = []
            for _ in range(40):
                QTest.keyClick(window, Qt.Key.Key_Tab)
                chain.append(focus_name())
            result["focus"] = chain
            for width in (760, 999, 1000, 1366, 1920):
                window.setWidth(width)
                QTest.qWait(12)
                entry = inspect_window(window, "home")
                assert not entry["errors"], entry["errors"]
                result.setdefault("widths", []).append(entry["sidebarWidth"])
            settings.sidebarCollapsed = True
            QTest.qWait(15)
            result["collapsed"] = find("sidebar").width()
        elif case == "updates":
            go("updates")
            result["notes"] = find("releaseNotes").property("text")
            result["status"] = find("updateStatus").property("text")
            updater._flow.install_eligible = True
            updater.changed.emit()
            click(find("installUpdate"))
            wait(lambda: find("cancelConfirmation") is not None, "update consent")
            result["pending"] = updater.pending
            QTest.keyClick(window, Qt.Key.Key_Escape)
            wait(lambda: not updater.pending, "reject update")
            result["installing"] = updater.installing
            settings.finishStartup(True)
            whats_new = window.findChild(QObject, "whatsNew")
            wait(lambda: whats_new.property("visible"), "first verified startup notice")
            QTest.keyClick(window, Qt.Key.Key_Escape)
            wait(lambda: not settings.whatsNewVersion, "dismiss what's new")
            settings.finishStartup(True)
            QTest.qWait(30)
            result["repeated"] = bool(whats_new.property("visible"))
        elif case == "localize":
            for scenario in ("default", "unknown", "long-text", "expanded", "running", "partial", "failed",
                             "cancelled", "completed", "confirmation"):
                maintenance._busy = False
                maintenance.reject()
                maintenance._last_action = ""
                maintenance._result_status = ""
                maintenance._results = {}
                maintenance._section_logs = {}
                apply_scenario(metrics, reader, maintenance, updater, scenario, "guided", language)
                for service_obj in (metrics, reader, maintenance, updater):
                    service_obj.changed.emit()
                for ix, section in enumerate(SECTIONS):
                    window.setProperty("currentTab", ix)
                    wait(lambda: page_ready(section), "fixture " + section)
                    QTest.qWait(35)
                    report = inspect_window(window, section)
                    assert not report["errors"], (scenario, section, report["errors"])
                    texts = "\n".join(report["text"])
                    wrong = (("Risultati simulati", "Avvio e app", "Gestione applicazioni", "Stato del PC", "Verifica in corso",
                              "Manutenzione in corso", "GB usati", "Aggiorna stato", "Annullamento richiesto")
                             if language == "en" else
                             ("SIMULATED", "Startup & apps", "System drive is", "PC health", "Temporary files",
                              "Check for official", "GB used", "Refresh status", "Full sequence"))
                    assert not any(token in texts for token in wrong), (scenario, section, texts)
                    import re
                    assert not re.search(r"(?m)^(?:pages|controls|nav|activity|action|update|palette)\.[A-Za-z]", texts), texts
                    if section == "home" and scenario == "default":
                        assert ("30,8" if language == "it" else "30.8") in texts, texts
                    result["count"] = result.get("count", 0) + 1
        else:
            raise ValueError(case)
        assert not warnings, warnings
        return result
    finally:
        maintenance._busy = False
        engine.deleteLater()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        for obj in (updater, maintenance, reader, metrics):
            obj.stop()
        del extensions


if __name__ == "__main__":
    print(json.dumps(exercise(sys.argv[1], sys.argv[2]), ensure_ascii=True))
