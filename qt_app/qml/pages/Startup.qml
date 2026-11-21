import QtQuick
import QtQuick.Layouts
import "../components"

ColumnLayout {
    id: startup
    required property var page
    spacing: Theme.spacing * 2
    FeatureSlot {
        Layout.fillWidth: true; name: "StartupApps"
        onNavigateRequested: section => startup.page.navigateRequested(section)
    }
    ActionList {
        Layout.fillWidth: true
        page: startup.page; glyph: "apps"; heading: Theme.tr("pages.windowsTools")
        actions: ["startup_settings", "apps_settings", "appwiz"]
    }
}
