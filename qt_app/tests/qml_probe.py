"""Render real QML in a separate GUI process; never invoke a backend operation."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QPoint, QPointF, QTimer, QUrl  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtGui import QGuiApplication, QFontDatabase  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from qt_app.main import MetricsBridge, ReadBridge, MaintenanceBridge  # noqa: E402
from qt_app.icon_provider import NavigationIconProvider  # noqa: E402
from qt_app.update_bridge import UpdateBridge  # noqa: E402


def main():
    app = QGuiApplication([])
    for font in ("segoeui.ttf", "segoeuib.ttf", "seguisb.ttf", "seguisym.ttf"):
        QFontDatabase.addApplicationFont("C:/Windows/Fonts/" + font)
    metrics, reader, maintenance = MetricsBridge(), ReadBridge(), MaintenanceBridge()
    metrics._values.update(cpu="30.8%", ram="90.7%", disk="97.5%")
    reader._results["hardware"] = {"os": "Windows 11", "cpu_name": "AMD Ryzen 7"}
    reader._results["drives"] = {"drives": [
        {"letter": "C:", "available": True, "used_percent": 50},
        {"letter": "D:", "available": True, "used_percent": 50},
        {"letter": "Z:", "available": False, "error": "Fixture offline"}]}
    reader._drives = ["C:", "D:"]
    if len(sys.argv) > 4 and sys.argv[4] == "preview-first-visit":
        reader._last_action = "temp_preview"
        reader._busy = True
    if len(sys.argv) > 4 and sys.argv[4] == "many-drives":
        reader._drives = [chr(65 + i) + ":" for i in range(26)]
        reader._results["drives"] = {"drives": [{"letter": letter, "available": True} for letter in reader._drives]}
    updater = UpdateBridge(reader, maintenance)
    if len(sys.argv) > 4 and sys.argv[4] in ("cancelled", "failed"):
        maintenance._last_action = "resurrection"
        maintenance._result_status = sys.argv[4]
        maintenance._progress_done = 2 if sys.argv[4] == "cancelled" else 1
        maintenance._progress_total = 10
        maintenance._steps = [{"success": sys.argv[4] != "failed", "message": "Fixture only"}
                              for _ in range(maintenance._progress_done)]
        maintenance._remember_result()
    if len(sys.argv) > 4 and sys.argv[4] in ("noisy-cleanup", "cleanup-step-two",
                                              "cleanup-partial", "full-cleanup-log"):
        scenario = sys.argv[4]
        maintenance._last_action = "quick_cleanup"
        maintenance._result_status = "partial" if scenario == "cleanup-partial" else "running"
        maintenance._busy = scenario != "cleanup-partial"
        maintenance._progress_done = 1 if scenario == "cleanup-step-two" else 0
        maintenance._progress_total = 3
        maintenance._section_logs["cleaning"] = (
            "Scanning C:\\Windows\\Temp...\n"
            "Deleted 50 files...\nDeleted 100 files...\nDeleted 150 files...\n"
            "Access denied: protected item\n"
            "Scanning C:\\Users\\Test\\AppData\\Local\\Temp...\n"
            "Deleted 200 files...\nDeleted 250 files..."
        )
        maintenance._remember_result()
    if len(sys.argv) > 4 and sys.argv[4] == "confirmation":
        maintenance._pending = "invalid-fixture"
        maintenance._details = "Safety warning requiring explicit confirmation. " * 50
    engine = QQmlApplicationEngine()
    warnings = []
    engine.warnings.connect(lambda errors: warnings.extend(str(e) for e in errors))
    engine.addImageProvider("panacea-nav", NavigationIconProvider())
    for name, value in {"applicationLanguage": sys.argv[5] if len(sys.argv) > 5 else "en", "qaSmokeMode": True, "nativeConfirmationsEnabled": False,
                        "liveMetrics": metrics, "readService": reader,
                        "maintenanceService": maintenance, "updateService": updater}.items():
        engine.rootContext().setContextProperty(name, value)
    engine.load(QUrl.fromLocalFile(str(ROOT / "qt_app/Main.qml")))
    if not engine.rootObjects():
        raise RuntimeError(warnings)
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
            p = item.mapToScene(QPointF(0, 0))
            return [round(p.x(), 2), round(p.y(), 2), round(item.width(), 2), round(item.height(), 2)]
        def card(text):
            if text == "Windows Update":
                return box(next(i for i in visible if i.objectName() == "windowsUpdateCard"))
            item = text_item(text)
            return box(item.parentItem().parentItem().parentItem())
        tab = int(window.property("currentTab"))
        result = {"warnings": warnings}
        brand_logo = next(i for i in visible if i.objectName() == "brandLogo")
        brand_title = next(i for i in visible if i.objectName() == "brandWordmark")
        brand_subtitle = next(i for i in visible if i.objectName() == "brandTagline")
        result["brand"] = {"logo": box(brand_logo), "title": box(brand_title), "subtitle": box(brand_subtitle)}
        scrollbar = next((i for i in visible if i.objectName() == "pageScrollbar"), None)
        thumb = next((i for i in visible if i.objectName() == "pageScrollThumb"), None)
        result["scrollbar"] = box(scrollbar) if scrollbar else None
        result["scroll_thumb"] = box(thumb) if thumb else None
        caption = "Analyze" if int(window.property("currentTab")) == 0 else "Run quick cleanup"
        action = next((i for i in visible if i.property("caption") == caption), None)
        if action:
            result["action_color"] = action.property("color").name()
        for scope in ("cleaning", "tools", "disk"):
            log = next((i for i in visible if i.objectName() == "sectionLog_" + scope), None)
            if log:
                result[scope + "_log"] = {"rect": box(log), "expanded": log.property("expanded")}
        overflow = []
        for item in visible:
            if not isinstance(item.property("text"), str):
                continue
            rect = box(item)
            if rect[0] >= 302 and rect[0] + rect[2] > window.width() + 1:
                overflow.append({"text": item.property("text"), "rect": rect})
        result["horizontal_overflow"] = overflow
        if len(sys.argv) > 4 and sys.argv[4] == "confirmation":
            copy = text_item(maintenance.details)
            result["confirmation_scrollable"] = copy.parentItem().property("contentHeight") is not None
            result["confirmation_readable_height"] = copy.implicitHeight() <= copy.height() + 1
        if tab == 1 and len(sys.argv) > 4 and sys.argv[4] in (
                "noisy-cleanup", "cleanup-step-two", "cleanup-partial", "full-cleanup-log"):
            status_heading = next(i for i in items(window.contentItem()) if i.objectName() == "quickCleanupStatusHeading")
            status_step = next(i for i in items(window.contentItem()) if i.objectName() == "quickCleanupStatusStep")
            section = next(i for i in items(window.contentItem()) if i.objectName() == "sectionLog_cleaning")
            surface = next(i for i in items(window.contentItem()) if i.objectName() == "consoleSurface_cleaning")
            console = next(i for i in items(window.contentItem()) if i.objectName() == "consoleText_cleaning")
            font = console.property("font")
            result["cleanup_status"] = {
                "heading": status_heading.property("text"),
                "step": status_step.property("text"),
            }
            result["console"] = {
                "expanded": bool(section.property("expanded")),
                "background": surface.property("color").name(),
                "font": font.family(),
                "font_size": font.pixelSize(),
                "show_full": bool(section.property("showFullOutput")),
                "text": console.property("text"),
            }
        if tab == 0 and len(sys.argv) > 4 and sys.argv[4] == "metric-refresh":
            initial = {i.objectName(): i for i in visible if i.objectName().startswith("metricCard_")}
            metrics._values["cpu"] = "41.7%"
            metrics._history["cpu"] = [10.0, 20.0, 41.7]
            metrics.changed.emit()
            app.processEvents()
            after = {i.objectName(): i for i in items(window.contentItem()) if i.objectName().startswith("metricCard_")}
            result["metric_cards_preserved"] = (
                set(initial) == {"metricCard_cpu", "metricCard_ram", "metricCard_disk"}
                and set(after) == set(initial)
                and all(initial[key] is after[key] for key in initial)
            )
        if tab == 0:
            metric_titles = ("CPU", "Memoria (RAM)", "Unità di sistema") if window.property("language") == "it" else ("CPU", "Memory (RAM)", "System drive")
            result.update(windows=card("Windows 11"), updates=card("Windows Update"),
                          metrics=[card(title) for title in metric_titles])
            system_title = next(i for i in visible if i.objectName() == "dashboardSystemTitle")
            result["system_title"] = {"text": system_title.property("text"),
                                      "truncated": bool(system_title.property("truncated")),
                                      "width": round(system_title.width(), 2),
                                      "implicit_width": round(system_title.implicitWidth(), 2)}
            update_labels = [next(i for i in visible if i.objectName() == name)
                             for name in ("updateHeaderTitle", "updateStatusCaption")]
            result["update_caption_lines"] = [
                {"text": item.property("text"), "lines": int(item.property("lineCount")),
                 "truncated": bool(item.property("truncated")),
                 "visible_width": round(item.width(), 2), "implicit_width": round(item.implicitWidth(), 2)}
                for item in update_labels
            ]
            badge = next(i for i in visible if i.objectName() == "updateStateBadge")
            result["update_badge"] = {"rect": box(badge), "color": badge.property("color").name()}
            update_card = next(i for i in visible if i.objectName() == "windowsUpdateCard")
            update_button = next(i for i in visible if i.objectName() == "updateOpenButton")
            result["update_card_layout"] = {
                "card": box(update_card), "title": box(update_labels[0]),
                "badge": box(badge), "action": box(update_button),
                "compact": bool(update_card.property("compact"))
            }
            action_titles = (("File temporanei", "Punto di ripristino") if window.property("language") == "it"
                             else ("Temporary files", "Restore point"))
            result["dashboard_action_titles"] = [
                {"text": label, "width": round(text_item(label).width(), 2),
                 "lines": int(text_item(label).property("lineCount"))}
                for label in action_titles
            ]
            result["graph_height_pixels"] = [i.height() * window.devicePixelRatio() for i in visible
                                             if i.objectName().startswith("metric_graph_")]
        if tab == 4:
            actions = next(i for i in visible if i.objectName() == "resurrectionActions")
            start_button = next(i for i in visible if i.objectName() == "resurrectionStartButton")
            result["guided_action_widths"] = {"container": round(actions.width(), 2), "start": round(start_button.width(), 2)}
            steps = sorted((i for i in visible if i.objectName().startswith("resurrection_step_")),
                           key=lambda i: int(i.objectName().rsplit("_", 1)[-1]))
            result["steps"] = [box(i) for i in steps]
            merged = steps[1]
            merged_title = next(i for i in items(merged) if i.objectName() == "guidedTitle_1")
            merged_summary = next(i for i in items(merged) if i.objectName() == "mergedGuidedSummary")
            merged_phases = [i for i in items(merged) if i.objectName().startswith("resurrection_phase_")]
            result["merged_card"] = {
                "title": merged_title.property("text"),
                "height": round(merged.height(), 2),
                "first_card_height": round(steps[0].height(), 2),
                "summary_visible": merged_summary.isVisible(),
                "visible_phase_count": sum(i.isVisible() for i in merged_phases),
                "backend_indices": sorted(i.property("backendIndex") for i in merged_phases)
            }
            phases = [item for step in steps for item in items(step)
                      if item.objectName().startswith("resurrection_phase_")]
            result["phase_states"] = [item.property("phaseStatus") for item in phases]
            result["phase_indices"] = sorted(item.property("backendIndex") for item in phases)
            panel = next(i for i in visible if i.objectName() == "resurrectionSafety")
            descendants = list(items(panel))
            result["warning_content_height"] = max(box(i)[1] + box(i)[3] for i in descendants) - box(panel)[1]
            result["warning_panel_height"] = panel.height()
        if tab in (1, 2):
            if window.property("language") == "it":
                names = ("Pulizia", "App installate") if tab == 1 else ("Strumenti di riparazione", "Ottimizzazione unità")
            else:
                names = ("Cleanup", "Installed apps") if tab == 1 else ("Repair tools", "Drive optimization")
            result["panels"] = [box(text_item(t).parentItem().parentItem()) for t in names]
            if tab == 2 and window.property("language") == "en":
                result["group_heading"] = box(next(i for i in visible if i.property("text") == "Diagnostics & Repair" and box(i)[0] >= 302))
            if tab == 2:
                picker = next(i for i in visible if i.objectName() == "driveSelector")
                result["drive_card_height"] = picker.parentItem().parentItem().parentItem().height()
                menu = next((i for i in visible if i.objectName() == "drivePopup"), None)
                result["drive_popup_height"] = menu.height() if menu else None
                result["drive_popup_visible"] = menu is not None
                page = next(i for i in visible if i.objectName() == "parityPage_2")
                result["selected_drive"] = page.property("selectedDrive")
                result["drive_error_visible"] = any(i.property("text") == "Drive information unavailable: Fixture query failed" for i in visible)
        if tab == 3:
            primary_options = next(i for i in visible if i.objectName() == "primaryTurboOptions")
            secondary_options = next(i for i in visible if i.objectName() == "secondaryTurboOptions")
            result["turbo_distribution"] = {
                "primary": {"rect": box(primary_options), "count": primary_options.property("optionCount")},
                "secondary": {"rect": box(secondary_options), "count": secondary_options.property("optionCount")}
            }
        if tab == 3 and window.property("language") == "en":
            toggle = next(i for i in visible if i.property("caption") == "High performance")
            result["turbo_layout"] = {"title": box(text_item("High performance")), "toggle": box(toggle)}
            master = next(i for i in visible if i.property("caption") == "Apply all optimizations")
            state = next(i for i in master.parentItem().childItems() if i.property("text") == "Unknown")
            result["master_layout"] = {"title": box(text_item("Apply all optimizations")), "toggle": box(master), "state": box(state)}
        print(json.dumps(result), flush=True)
        maintenance._busy = False
        reader._busy = False
        app.quit()
    def arrange():
        if len(sys.argv) > 4 and sys.argv[4] == "full-cleanup-log":
            log = next(i for i in items(window.contentItem()) if i.objectName() == "sectionLog_cleaning")
            log.setProperty("showFullOutput", True)
        if len(sys.argv) > 4 and sys.argv[4] == "drive-query-failed":
            reader._results["drives"] = {"available": False, "error": "Fixture query failed"}
            reader._drives = []
            reader.changed.emit()
        if len(sys.argv) > 4 and sys.argv[4] == "disabled-action":
            reader._last_action = "hardware"
            reader._busy = True
            reader.changed.emit()
        if len(sys.argv) > 4 and sys.argv[4] == "operation-running":
            maintenance._last_action = "sfc"
            maintenance._busy = True
            maintenance.changed.emit()
        if len(sys.argv) > 4 and sys.argv[4] == "drive-refresh":
            reader._last_action = "drives"
            reader._busy = True
            reader.changed.emit()
        if len(sys.argv) > 4 and sys.argv[4] in ("drive-choices", "many-drives", "drive-focus-out"):
            page = next(i for i in items(window.contentItem()) if i.objectName() == "parityPage_2")
            page.setProperty("showDriveChoices", True)
            if sys.argv[4] == "drive-focus-out":
                picker = next(i for i in items(page) if i.objectName() == "driveSelector")
                QTimer.singleShot(200, picker.forceActiveFocus)
        if len(sys.argv) > 4 and sys.argv[4] == "hover-action":
            caption = "Analyze" if int(window.property("currentTab")) == 0 else "Run quick cleanup"
            action = next(i for i in items(window.contentItem()) if i.isVisible() and i.property("caption") == caption)
            def hover_action():
                position = action.mapToScene(QPointF(action.width() / 2, action.height() / 2))
                QTest.mouseMove(window, QPoint(round(position.x()), round(position.y())))
            QTimer.singleShot(200, hover_action)
        if len(sys.argv) > 4 and sys.argv[4] == "scrolled":
            page = next(i for i in items(window.contentItem()) if i.objectName() == "parityPage_" + str(window.property("currentTab")))
            viewport = next(i for i in items(page) if i.objectName() == "pageViewport")
            QTimer.singleShot(200, lambda: viewport.setProperty("contentY", 100))
        if len(sys.argv) > 4 and sys.argv[4] == "expanded":
            page = next(i for i in items(window.contentItem()) if i.objectName() == "parityPage_" + str(window.property("currentTab")))
            page.setProperty("showIndividualCleaning", True)
            page.setProperty("showExtraDriveTools", True)
            for i in items(page):
                if i.metaObject().indexOfProperty("expanded") >= 0:
                    i.setProperty("expanded", True)
        def checked_measure():
            try:
                measure()
            except Exception:
                import traceback
                traceback.print_exc()
                app.exit(1)
        QTimer.singleShot(400, checked_measure)
    QTimer.singleShot(0, arrange)
    app.aboutToQuit.connect(metrics.stop)
    app.aboutToQuit.connect(reader.stop)
    app.aboutToQuit.connect(maintenance.stop)
    app.aboutToQuit.connect(updater.stop)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
