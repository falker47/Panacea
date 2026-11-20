import QtQuick
import QtQuick.Layouts
import "../components"

ColumnLayout {
    id: repair
    required property var page
    spacing: Theme.spacing * 2
    GridLayout {
        Layout.fillWidth: true
        columns: width >= 808 ? 2 : 1
        columnSpacing: Theme.spacing * 2
        rowSpacing: Theme.spacing * 2
        ActionList {
            Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.preferredWidth: 1; Layout.alignment: Qt.AlignTop
            page: repair.page; glyph: "repair"; heading: Theme.tr("pages.systemFiles")
            actions: ["sfc", "dism_check", "dism_restore"]
        }
        ActionList {
            Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.preferredWidth: 1; Layout.alignment: Qt.AlignTop
            page: repair.page; glyph: "windows"; heading: Theme.tr("pages.network")
            actions: ["dns_flush", "winsock_reset"]
        }
    }
    SectionHeader { Layout.fillWidth: true; title: Theme.tr("pages.diagnostics") }
    DrivePicker { Layout.fillWidth: true; page: repair.page }
    CatalogAction { Layout.fillWidth: true; page: repair.page; actionId: "chkdsk"; glyph: "scan" }
    CatalogAction { Layout.fillWidth: true; page: repair.page; actionId: "restore_point"; glyph: "restore" }
    CatalogAction { Layout.fillWidth: true; page: repair.page; actionId: "battery_report"; glyph: "battery-report" }
}
