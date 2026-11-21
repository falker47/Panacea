import QtQuick
import QtQuick.Controls.Basic as Controls
import QtQuick.Layouts
import "../components"

ColumnLayout {
    id: updates
    required property var page
    spacing: Theme.spacing * 2
    Timer {
        id: clock
        property int minute: 0
        interval: 60000; repeat: true; running: updates.visible && !!updateService.lastChecked
        onTriggered: ++minute
    }
    function lastCheck(iso, minute) {
        return iso ? Theme.tr("pages.lastCheck", {date: i18n.dateTime(iso), elapsed: i18n.relativeTime(iso)})
                   : Theme.tr("pages.neverChecked")
    }
    Card {
        Layout.fillWidth: true
        RowLayout {
            Layout.fillWidth: true
            SectionHeader { Layout.fillWidth: true; title: Theme.tr("pages.panaceaVersion") }
            StatusBadge {
                visible: updateService.available
                text: Theme.tr("pages.newVersion", {version: updateService.availableVersion})
                tone: "info"; glyph: "download"
            }
        }
        BodyText {
            Layout.fillWidth: true
            objectName: "installedVersion"
            text: updateService.currentVersion
            font.pixelSize: Theme.fontDisplay; font.weight: Font.DemiBold; tabular: true
        }
        BodyText {
            Layout.fillWidth: true; color: Theme.textMuted; font.pixelSize: Theme.fontSmall
            text: updates.lastCheck(updateService.lastChecked, clock.minute)
        }
        BodyText {
            Layout.fillWidth: true
            objectName: "updateStatus"
            text: Theme.tr(updateService.status, updateService.statusParams)
        }
        Controls.ProgressBar {
            Layout.fillWidth: true
            visible: updateService.downloading
            from: 0; to: 100; value: updateService.progress
            palette.highlight: Theme.info
            Accessible.name: Theme.tr("pages.downloadProgress", {value: updates.page.number(value, 0)})
        }
        RowLayout {
            Layout.fillWidth: true
            AppButton {
                objectName: "checkForUpdates"
                text: Theme.tr("pages.checkUpdates"); glyph: "refresh-cw"
                variant: updateService.available && updateService.eligible ? "secondary" : "primary"
                enabled: !updates.page.occupied
                loading: updateService.busy && !updateService.downloading && !updateService.installing
                onClicked: updateService.check()
            }
            AppButton {
                objectName: "installUpdate"
                visible: updateService.available && updateService.eligible
                text: Theme.tr("pages.installUpdate"); glyph: "download"; variant: "primary"
                enabled: !updates.page.occupied
                onClicked: updateService.prepareInstall()
            }
            AppButton {
                visible: updateService.downloading && !updateService.installing
                text: Theme.tr("pages.cancelDownload"); glyph: "close"
                onClicked: updateService.cancelDownload()
            }
        }
    }
    Card {
        Layout.fillWidth: true
        visible: !!updateService.notes
        SectionHeader { Layout.fillWidth: true; title: Theme.tr("pages.releaseNotes") }
        BodyText {
            Layout.fillWidth: true
            objectName: "releaseNotes"
            textFormat: Text.MarkdownText
            text: updateService.notes
            wrapMode: Text.Wrap
        }
    }
}
