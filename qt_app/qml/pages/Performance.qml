import QtQuick
import QtQuick.Layouts
import "../components"

ColumnLayout {
    id: performance
    required property var page
    readonly property var turbo: page.turbo
    spacing: Theme.spacing * 2
    function stateLabel(value) {
        return Theme.tr(value === true ? "pages.applied" : value === false ? "pages.inactive" : "pages.unknown")
    }

    Card {
        Layout.fillWidth: true
        RowLayout {
            Layout.fillWidth: true
            SectionHeader {
                Layout.fillWidth: true
                title: Theme.tr("pages.turbo")
                subtitle: Theme.tr("pages.turboDescription")
            }
            IconButton {
                text: Theme.tr("pages.refreshTurbo"); glyph: "refresh-cw"
                enabled: !performance.page.occupied
                onClicked: readService.request("turbo_status")
            }
        }
        Toggle {
            id: master
            Layout.fillWidth: true
            readonly property string actionId: performance.turbo.master === true ? "turbo_off" : "turbo_on"
            objectName: performance.turbo.master === true ? "turboMasterToggle" : "action_turbo_on"
            text: Theme.tr("pages.turboPreset")
            description: performance.turbo.refreshing ? Theme.tr("pages.turboChecking")
                         : performance.turbo.available === false ? Theme.tr("pages.turboUnavailable")
                         : performance.stateLabel(performance.turbo.master)
            checked: performance.turbo.master === true
            enabled: typeof performance.turbo.master === "boolean" && performance.page.canPrepare(actionId)
            onToggled: {
                checked = Qt.binding(function() { return performance.turbo.master === true })
                performance.page.prepareAction(actionId)
            }
        }
        RowLayout {
            Layout.fillWidth: true
            BodyText {
                Layout.fillWidth: true; color: Theme.textMuted
                text: typeof performance.turbo.saved_count === "number"
                      ? Theme.tr("pages.savedOriginals", {count: performance.page.number(performance.turbo.saved_count, 0)})
                      : Theme.tr("pages.savedUnknown")
            }
            AppButton {
                objectName: "action_turbo_off"; text: Theme.tr("pages.restoreOriginals"); glyph: "restore"
                enabled: performance.page.canPrepare("turbo_off")
                onClicked: performance.page.prepareAction("turbo_off")
            }
        }
    }
    Card {
        Layout.fillWidth: true
        SectionHeader { Layout.fillWidth: true; title: Theme.tr("pages.turboSettings") }
        Repeater {
            model: ["power", "visual", "sysmain", "wsearch", "spooler"]
            delegate: Toggle {
                id: setting
                required property string modelData
                readonly property var measured: (performance.turbo.states || {})[modelData]
                readonly property string actionId: modelData + (measured === true ? "_off" : "_on")
                objectName: "action_" + actionId
                Layout.fillWidth: true
                text: Theme.tr("pages.setting." + modelData)
                description: Theme.tr("pages.settingState", {
                    purpose: Theme.tr("pages.setting." + modelData + ".purpose"), state: performance.stateLabel(measured)
                })
                checked: measured === true
                enabled: performance.page.canPrepare(actionId)
                onToggled: {
                    checked = Qt.binding(function() { return setting.measured === true })
                    performance.page.prepareAction(actionId)
                }
            }
        }
    }
    SectionHeader { Layout.fillWidth: true; title: Theme.tr("pages.driveOptimization") }
    DrivePicker { Layout.fillWidth: true; page: performance.page }
    CatalogAction { Layout.fillWidth: true; page: performance.page; actionId: "drive_optimize"; glyph: "drive" }
    CatalogAction { Layout.fillWidth: true; page: performance.page; actionId: "open_defrag"; glyph: "windows" }
}
