"""Exercise the actual design-system controls in an isolated, offscreen Qt window."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
TOKENS = ("bg", "surface", "surfaceAlt", "border", "controlBorder", "text", "textMuted",
          "accent", "onAccent", "info", "success", "warning", "danger", "focus")

FIXTURE = br"""
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "components"
ApplicationWindow {
    id: win; width: 760; height: 480; visible: true
    property QtObject tokens: Theme
    property int activated: 0
    property int acceptedCount: 0
    property int rejectedCount: 0
    ColumnLayout {
        width: parent.width - 32; x: 16; y: 16; spacing: 8
        RowLayout {
            AppButton { objectName: "primary"; text: "Run"; variant: "primary"; onClicked: win.activated++ }
            IconButton { objectName: "icon"; text: "Search"; glyph: "search" }
            Toggle { objectName: "toggle"; text: "Enable"; description: "Option"; Layout.preferredWidth: 160 }
        }
        ActionRow { objectName: "action"; text: "Repair"; description: "Description"; glyph: "repair" }
        Card {
            objectName: "card"; Layout.fillWidth: true
            SectionHeader { title: "Heading"; subtitle: "Description"; Layout.fillWidth: true }
            BodyText { objectName: "metric"; text: "25%"; tabular: true }
        }
        LogPanel { objectName: "log"; summary: "Summary"; details: "Row one\nRow two" }
    }
    Item {
        visible: false
        StatusBadge { text: "Done"; tone: "success" }
        ProgressSteps { width: 420; steps: [{title: "Read", state: "unknown"}] }
        InlineBanner { title: "Warning"; description: "Details"; tone: "warning" }
        EmptyState { title: "History"; description: "No events" }
        Skeleton { }
    }
    ConfirmSheet {
        objectName: "confirmSheet"; title: fixtureTitle; details: fixtureDetails; destructive: true
        onAccepted: win.acceptedCount++
        onRejected: win.rejectedCount++
    }
    Toast { objectName: "toast" }
}
"""


def _probe():
    sys.path.insert(0, str(ROOT))
    from PySide6.QtCore import QCoreApplication, QEvent, QObject, QPointF, Qt, QUrl
    from PySide6.QtGui import QAccessible, QAccessibleActionInterface, QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtTest import QTest
    from qt_app.confirmation_copy import confirmation_text
    from qt_app.icon_provider import NavigationIconProvider
    from qt_app.i18n import I18n
    from qt_app.maintenance import WARNINGS
    from qt_app.settings import AppSettings

    app = QGuiApplication([])
    QAccessible.setActive(True)
    engine = QQmlApplicationEngine()
    settings = AppSettings(smoke=True)
    settings.languageChoice = "en"
    catalog = I18n(settings)
    title, effects = confirmation_text("recycle_empty", {"title": "Empty Recycle Bin", "details": WARNINGS["recycle_empty"]}, "en")
    warnings = []
    engine.warnings.connect(lambda errors: warnings.extend(error.toString() for error in errors))
    engine.addImageProvider("panacea-nav", NavigationIconProvider())
    for name, value in (("appSettings", settings), ("i18n", catalog), ("fixtureTitle", title),
                        ("fixtureDetails", "\n".join([effects] * 35))):
        engine.rootContext().setContextProperty(name, value)
    engine.loadData(FIXTURE, QUrl.fromLocalFile(str(ROOT / "qt_app/qml/TestControls.qml")))
    if not engine.rootObjects():
        raise AssertionError(warnings)
    win = engine.rootObjects()[0]

    def item(name):
        result = win.findChild(QObject, name)
        if result is None:
            raise LookupError(name)
        return result

    def key(code):
        QTest.keyClick(win, code)
        app.processEvents()
        return win.activeFocusItem().objectName()

    try:
        win.requestActivate()
        QTest.qWait(30)
        theme, primary = win.property("tokens"), item("primary")
        data = {"dark": {name: theme.property(name).name() for name in TOKENS},
                "scale": [theme.property(n) for n in ("fontSmall", "fontBody", "fontLabel", "fontTitle", "fontDisplay")]}
        button = item("icon")
        glyph = button.findChild(QObject, "buttonGlyph")
        center = glyph.mapToItem(button, QPointF(glyph.width() / 2, glyph.height() / 2))
        data["icon_offset"] = [center.x() - button.width() / 2, center.y() - button.height() / 2]
        data["roles"] = []
        for name in ("primary", "icon", "toggle", "action", "toggleLogDetails"):
            interface = QAccessible.queryAccessibleInterface(item(name))
            data["roles"].append([interface.role().name, interface.text(QAccessible.Name)])
        primary.forceActiveFocus(Qt.TabFocusReason)
        ring = primary.findChild(QObject, "focusRing")
        data["focus_visible"] = ring.isVisible()
        data["tab_order"] = [key(Qt.Key_Tab), key(Qt.Key_Tab), key(Qt.Key_Tab)]
        primary.forceActiveFocus(Qt.TabFocusReason)
        key(Qt.Key_Space)
        action_api = QAccessible.queryAccessibleInterface(primary).actionInterface()
        action_api.doAction(QAccessibleActionInterface.pressAction())
        primary.setProperty("loading", True)
        data["button_state"] = [win.property("activated"), primary.isEnabled()]
        data["metric_features"] = bytes(item("metric").property("font").featureTags()[0].toString()).decode("ascii")
        log = item("log")
        data["initial_log"] = [log.property("expanded"), item("logDetails").isVisible()]
        item("toggleLogDetails").click()
        app.processEvents()
        item("copyLog").click()
        data["expanded_log"] = [log.property("expanded"), item("logDetails").isVisible(),
                                item("logDetails").property("readOnly"), app.clipboard().text()]
        sheet = item("confirmSheet")
        sheet.open()
        QTest.qWait(40)
        initial = win.activeFocusItem().objectName()
        data["dialog"] = [initial, key(Qt.Key_Tab), key(Qt.Key_Tab), key(Qt.Key_Backtab)]
        key(Qt.Key_PageDown)
        viewport = item("confirmationViewport")
        data["viewport"] = [sheet.property("height"), viewport.height(), viewport.property("contentHeight"),
                            viewport.property("contentY")]
        data["effects"] = [item("confirmationDetails").property("text"), item("confirmConfirmation").property("variant")]
        key(Qt.Key_Escape)
        data["cancelled"] = [sheet.property("visible"), win.property("acceptedCount"), win.property("rejectedCount")]
        sheet.open()
        app.processEvents()
        key(Qt.Key_Tab)
        key(Qt.Key_Return)
        data["confirmed"] = [sheet.property("visible"), win.property("acceptedCount"), win.property("rejectedCount")]
        settings.languageChoice = "it"
        data["localized_cancel"] = item("cancelConfirmation").property("text")
        settings._colors = {k: "#ffffff" for k in TOKENS if k != "controlBorder"}
        settings._colors.update(bg="#000000", surface="#000000", surfaceAlt="#000000", accent="#00ffff", onAccent="#000000")
        settings._system_reduced = True
        settings.systemAppearanceChanged.emit()
        data["system"] = [theme.property("highContrast"), theme.property("accent").name(), theme.property("reducedMotion")]
        settings._colors, settings._system_reduced = {}, False
        settings.systemAppearanceChanged.emit()
        settings.reduceMotion = True
        data["preference"] = [theme.property("highContrast"), theme.property("reducedMotion")]
        data["warnings"] = warnings
        return data
    finally:
        engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def _contrast(first, second):
    def luminance(value):
        channels = [int(value[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        rgb = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in channels]
        return sum(v * weight for v, weight in zip(rgb, (0.2126, 0.7152, 0.0722)))

    low, high = sorted((luminance(first), luminance(second)))
    return (high + 0.05) / (low + 0.05)


class SharedControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software")
        result = subprocess.run([sys.executable, str(Path(__file__)), "--probe"], cwd=ROOT,
                                env=env, capture_output=True, text=True, timeout=30)
        if result.returncode:
            raise AssertionError(f"Component fixture failed: {result.stderr[-4000:]}")
        cls.data = json.loads(result.stdout)

    def test_real_controls_load_without_warnings_and_report_names_and_roles(self):
        self.assertEqual(self.data["warnings"], [])
        for role, name in self.data["roles"]:
            self.assertIn(role, ("Button", "CheckBox"))
            self.assertTrue(name)
        self.assertEqual(self.data["tab_order"], ["icon", "toggle", "action"])
        self.assertTrue(all(abs(offset) <= 1 for offset in self.data["icon_offset"]), self.data["icon_offset"])
        self.assertTrue(self.data["focus_visible"])
        self.assertEqual(self.data["button_state"], [2, False])

    def test_dark_contrast_typography_and_live_system_override(self):
        palette = self.data["dark"]
        for background in ("bg", "surface", "surfaceAlt"):
            for text in ("text", "textMuted", "info", "success", "warning", "danger"):
                self.assertGreaterEqual(_contrast(palette[text], palette[background]), 4.5, (text, background))
            for outline in ("controlBorder", "focus"):
                self.assertGreaterEqual(_contrast(palette[outline], palette[background]), 3, (outline, background))
        for fill in ("accent", "danger"):
            self.assertGreaterEqual(_contrast(palette["onAccent"], palette[fill]), 4.5)
        self.assertEqual(self.data["scale"], [12, 14, 16, 20, 28])
        self.assertEqual(self.data["metric_features"], "tnum")
        self.assertEqual(self.data["system"], [True, "#00ffff", True])
        self.assertEqual(self.data["preference"], [False, True])

    def test_log_disclosure_copy_and_language_change(self):
        self.assertEqual(self.data["initial_log"], [False, False])
        self.assertEqual(self.data["expanded_log"], [True, True, True, "Row one\nRow two"])
        self.assertEqual(self.data["localized_cancel"], "Annulla")

    def test_modal_starts_on_cancel_traps_both_directions_and_keeps_effects_readable(self):
        from qt_app.maintenance import WARNINGS

        self.assertEqual(self.data["dialog"], ["cancelConfirmation", "confirmConfirmation",
                                              "cancelConfirmation", "confirmConfirmation"])
        height, viewport, content, scrolled = self.data["viewport"]
        self.assertLessEqual(height, 480)
        self.assertGreater(content, viewport)
        self.assertGreater(scrolled, 0, self.data["viewport"])
        self.assertEqual(self.data["effects"][0].splitlines(), [WARNINGS["recycle_empty"]] * 35)
        self.assertEqual(self.data["effects"][1], "danger")
        self.assertEqual(self.data["cancelled"], [False, 0, 1])
        self.assertEqual(self.data["confirmed"], [False, 1, 1])


if __name__ == "__main__":
    if "--probe" in sys.argv:
        print(json.dumps(_probe()))
    else:
        unittest.main()
