import QtQuick
import QtQuick.Layouts
import "../components"

ColumnLayout {
    id: guided
    required property var page
    spacing: Theme.spacing * 2
    Card {
        Layout.fillWidth: true
        SectionHeader {
            Layout.fillWidth: true
            title: Theme.tr("action.resurrection.title")
            subtitle: Theme.tr("pages.guidedDescription")
        }
        BodyText { Layout.fillWidth: true; color: Theme.textMuted; text: Theme.tr("pages.guidedRisk") }
        AppButton {
            objectName: "action_resurrection"; text: Theme.tr("pages.reviewGuided")
            glyph: "guided"; variant: "primary"
            enabled: guided.page.canPrepare("resurrection")
            onClicked: guided.page.prepareAction("resurrection")
        }
    }
    ActionRow {
        Layout.fillWidth: true
        objectName: "read_guard_status"; glyph: "shield-plus"
        text: Theme.tr("pages.guard")
        description: Theme.tr(guided.page.guard.blocked === true ? "pages.guardBlocked"
                              : guided.page.guard.blocked === false ? "pages.guardClear" : "pages.guardUnknown")
        tone: guided.page.guard.blocked === true ? "warning" : "neutral"
        enabled: !guided.page.occupied
        onClicked: readService.request("guard_status")
    }
    LogPanel {
        Layout.fillWidth: true
        visible: guided.page.guard.blocked === true && details.length > 0
        title: Theme.tr("pages.guardDetails")
        summary: Theme.tr("pages.guardBlocked")
        details: guided.page.guard.message || ""
    }
    SequenceProgress {
        Layout.fillWidth: true; page: guided.page; action: "resurrection"
        operations: ["restore_point", "browser_clean", "temp_clean", "recycle_empty", "dns_flush",
                     "winsock_reset", "drive_optimize", "chkdsk", "dism_check", "sfc"]
    }
}
