import QtQuick
import QtQuick.Layouts
import "../components"

ColumnLayout {
    id: activity
    required property var pageModel
    readonly property var results: maintenanceService.results
    readonly property var actions: sectionActions[pageModel.section] || []
    readonly property bool hasResults: actions.some(function(key) {
        return !!activity.results[key]
    })
    readonly property string readLog: readService.sectionLogs[pageModel.section] || ""
    readonly property string sectionLog: maintenanceService.sectionLogs[pageModel.section] || ""
    readonly property bool hasEntries: hasResults || !!readLog || !!sectionLog
    spacing: Theme.spacing
    SectionHeader { Layout.fillWidth: true; title: Theme.tr("pages.activity") }
    Repeater {
        model: activity.actions
        delegate: Loader {
            id: logLoader
            required property string modelData
            readonly property var result: activity.results[modelData] || ({})
            Layout.fillWidth: true
            active: !!result.status
            visible: active
            sourceComponent: LogPanel {
                objectName: "actionLog_" + logLoader.modelData
                title: Theme.tr("action." + logLoader.modelData + ".title")
                summary: activity.pageModel.statusText(logLoader.result.status)
                details: logLoader.result.output || ""
            }
        }
    }
    LogPanel {
        Layout.fillWidth: true
        visible: !!activity.readLog || !!activity.sectionLog
        title: Theme.tr("pages.sectionLog")
        summary: Theme.tr("pages.sectionLogDescription")
        details: [activity.sectionLog, activity.readLog].filter(Boolean).join("\n")
    }
    AppButton {
        text: Theme.tr("pages.cancelOperation")
        glyph: "close"
        visible: maintenanceService.busy && maintenanceService.activeSection === activity.pageModel.section
        onClicked: maintenanceService.cancel()
    }
}
