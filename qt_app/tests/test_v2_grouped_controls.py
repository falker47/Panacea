"""Verify shared palette/row eligibility and the optional feature host with inert Qt fixtures."""
from pathlib import Path
import tempfile
import unittest

from qt_app.tests.test_v2_graph import ROOT, find, page_test, value


class SectionEligibilityTests(unittest.TestCase):
    @page_test("settings", "it")
    def test_settings_controls_follow_saved_values_and_retranslate_the_open_page(self, f):
        language = find(f.page, "languageChoice")
        language.activated.emit(2)
        self.assertEqual(f.settings.languageChoice, "en")
        switches = {"autoCheck": True, "reduceMotion": False, "sidebarCollapsed": False}
        for key, initial in switches.items():
            toggle = find(f.page, key)
            self.assertEqual(value(toggle, "checked"), initial)
            toggle.click()
            self.assertEqual(getattr(f.settings, key), not initial)
            setattr(f.settings, key, initial)
            self.assertEqual(value(toggle, "checked"), initial)
        self.assertEqual(value(find(f.page, "autoCheck"), "text"), f.strings.t("pages.autoCheck"))
        self.assertEqual(value(language, "currentIndex"), 2)

    @page_test("performance")
    def test_measured_switch_waits_for_confirmation_and_partial_restore_stays_available(self, f):
        power = find(f.page, "action_power_off")
        self.assertTrue(power.isEnabled())
        self.assertTrue(value(power, "checked"))
        power.click()
        self.assertEqual(f.maintenance.preparedAction, "power_off")
        self.assertTrue(value(power, "checked"), "The visual state must still describe the PC")
        self.assertFalse(f.backend.executed)
        self.assertFalse(f.page.prepareAction("turbo_on"), "Cannot replace pending consent")
        f.maintenance.reject()
        self.assertTrue(value(power, "checked"))
        self.assertTrue(f.page.prepareAction("turbo_off"))
        self.assertEqual(f.maintenance.preparedAction, "turbo_off")
        f.maintenance.reject()

        snapshot = f.reader._results["turbo_status"]
        for master in (True, False, None):
            snapshot["master"] = master
            for saved in (True, False):
                snapshot["restore_available"] = saved
                f.reader.changed.emit()
                restore = find(f.page, "action_turbo_off")
                self.assertEqual(restore.isEnabled(), saved)
                self.assertEqual(f.page.canPrepare("turbo_off"), saved)
        self.assertFalse(f.page.canPrepare("turbo_on"))
        self.assertFalse(f.page.canPrepare("power_off"))

    @page_test("performance")
    def test_missing_state_and_busy_operations_exclude_palette_and_row_equally(self, f):
        for snapshot in ({}, {"refreshing": True, "available": False}, {"available": False, "error": "fixture"}):
            f.reader._results["turbo_status"] = snapshot
            f.reader.changed.emit()
            for action in ("turbo_on", "turbo_off", "power_on", "visual_on", "sysmain_on", "wsearch_on", "spooler_on"):
                self.assertFalse(find(f.page, "action_" + action).isEnabled(), action)
                self.assertFalse(f.page.prepareAction(action), action)
                self.assertFalse(f.maintenance.awaitingConfirmation)
        for owner in (f.reader, f.maintenance, f.updater):
            owner._busy = True
            owner.changed.emit()
            self.assertFalse(find(f.page, "action_drive_optimize").isEnabled())
            self.assertFalse(f.page.prepareAction("drive_optimize"))
            owner._busy = False
            owner.changed.emit()
        self.assertFalse(f.page.prepareAction("dns_flush"), "Wrong section")
        self.assertFalse(f.page.prepareAction("unknown_fixture_action"))

    @page_test("repair")
    def test_drive_uses_eligible_selection_and_clears_it_on_refresh_failure(self, f):
        f.reader._drives = ["C:", "D:"]
        f.reader._results["drives"]["drives"].append(
            {"letter": "D:", "available": True, "total_bytes": 90000, "free_bytes": 1000})
        f.reader.changed.emit()
        combo = find(f.page, "driveSelector")
        combo.activated.emit(1)
        self.assertEqual(value(f.page, "selectedDrive"), "D:")
        row = find(f.page, "action_chkdsk")
        row.click()
        self.assertEqual(f.maintenance.preparedAction, "chkdsk")
        self.assertIn("D:", f.maintenance.details)
        f.maintenance.reject()
        f.reader._drives = []
        f.reader._results["drives"] = {"available": False, "error": "fixture"}
        f.reader.changed.emit()
        self.assertEqual(value(f.page, "selectedDrive"), "")
        self.assertFalse(row.isEnabled())
        self.assertFalse(f.page.prepareAction("chkdsk"))
        self.assertFalse(f.maintenance.awaitingConfirmation)

    @page_test("home")
    def test_blocked_guard_allows_native_settings_and_read_only_information(self, f):
        f.reader._results["guard_status"] = {"blocked": True, "message": "fixture"}
        f.reader.changed.emit()
        self.assertFalse(f.page.canPrepare("restore_point"))
        self.assertFalse(find(f.page, "action_restore_point").isEnabled())
        self.assertTrue(f.page.canPrepare("windows_update"))
        find(f.page, "action_windows_update").click()
        self.assertEqual(f.maintenance.preparedAction, "windows_update")
        self.assertFalse(f.backend.executed)

    @page_test("home")
    def test_optional_features_receive_live_language_theme_and_forward_navigation(self, f):
        from PySide6.QtCore import QUrl
        from PySide6.QtTest import QTest

        path = ROOT / "qt_app/qml/pages/SectionPage.qml"
        f.view.setSource(QUrl())
        build = ROOT / "build"
        build.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=build) as directory:
            folder = Path(directory)
            valid = folder / "HealthCheck.qml"
            valid.write_text(
                "import QtQuick\nItem { required property string language; required property var theme; "
                "signal navigateRequested(string section); property color heading: theme.text; implicitHeight: 45 }",
                encoding="utf-8")
            broken = folder / "StorageAnalysis.qml"
            broken.write_text("import QtQuick\nMissingType { }", encoding="utf-8")
            incomplete = folder / "DeepCleanup.qml"
            incomplete.write_text(
                "import QtQuick\nItem { required property string language; required property var theme; "
                "required property int missingInput }", encoding="utf-8")
            incompatible = folder / "StartupApps.qml"
            incompatible.write_text("import QtQuick\nItem { }", encoding="utf-8")
            urls = {name: QUrl.fromLocalFile(str(file)).toString() for name, file in
                    (("HealthCheck", valid), ("StorageAnalysis", broken), ("DeepCleanup", incomplete),
                     ("StartupApps", incompatible))}
            f.view.rootContext().setContextProperty("featureUrls", urls)
            f.view.setInitialProperties({"section": "home"})
            f.view.setSource(QUrl.fromLocalFile(str(path)))
            page = f.view.rootObject()
            slot = find(page, "feature_HealthCheck", visible=False)
            for _ in range(100):
                if value(slot, "available"):
                    break
                QTest.qWait(10)
            feature = value(slot, "feature")
            self.assertTrue(slot.isVisible())
            self.assertEqual(value(feature, "language"), "en")
            self.assertTrue(value(feature, "heading").isValid())
            f.settings.languageChoice = "it"
            self.assertEqual(value(feature, "language"), "it")
            navigations = []
            page.navigateRequested.connect(navigations.append)
            feature.navigateRequested.emit("repair")
            self.assertEqual(navigations, ["repair"])
            for section, name in (("cleanup", "StorageAnalysis"), ("cleanup", "DeepCleanup"),
                                  ("startup", "StartupApps"), ("history", "History")):
                page.setProperty("section", section)
                absent = find(page, "feature_" + name, visible=False)
                for _ in range(100):
                    if not value(absent, "loading"):
                        break
                    QTest.qWait(10)
                self.assertFalse(absent.isVisible(), name)
                self.assertFalse(value(absent, "available"), name)
            f.view.setSource(QUrl())


if __name__ == "__main__":
    unittest.main()
