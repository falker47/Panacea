import QtQuick
import QtQuick.Layouts
import "../components"

Card {
    id: drive
    required property var page
    readonly property var snapshot: page.snapshots.drives || ({})
    readonly property var selected: (snapshot.drives || []).find(function(row) {
        return row.letter === drive.page.selectedDrive && row.available === true
    })
    readonly property bool checking: readService.busy && readService.lastAction === "drives"
    readonly property string capacity: {
        if (checking) return Theme.tr("pages.drivesChecking")
        if (snapshot.available === false || snapshot.error) return Theme.tr("pages.drivesUnavailable")
        if (!snapshot.drives) return Theme.tr("pages.drivesUnverified")
        if (selected && typeof selected.free_bytes === "number" && typeof selected.total_bytes === "number")
            return Theme.tr("pages.driveCapacity", {free: i18n.bytes(selected.free_bytes), total: i18n.bytes(selected.total_bytes)})
        return Theme.tr(page.driveLetters.length ? "pages.capacityUnavailable" : "pages.noEligibleDrive")
    }
    RowLayout {
        Layout.fillWidth: true
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 4
            BodyText {
                Layout.fillWidth: true
                text: Theme.tr("pages.targetDrive")
                font.pixelSize: Theme.fontLabel; font.weight: Font.DemiBold
            }
            BodyText {
                Layout.fillWidth: true
                text: drive.capacity
                color: Theme.textMuted; font.pixelSize: Theme.fontSmall
            }
        }
        ChoiceBox {
            objectName: "driveSelector"
            label: Theme.tr("pages.targetDrive")
            model: drive.page.driveLetters
            Layout.preferredWidth: 120
            currentIndex: drive.page.driveLetters.indexOf(drive.page.selectedDrive)
            enabled: !drive.page.occupied && count > 0
            displayText: currentIndex >= 0 ? currentText : Theme.tr("pages.noDrive")
            onActivated: index => drive.page.selectedDrive = drive.page.driveLetters[index]
        }
        IconButton {
            text: Theme.tr("pages.refreshDrives")
            glyph: "refresh-cw"
            enabled: !drive.page.occupied
            onClicked: readService.request("drives")
        }
    }
    LogPanel {
        Layout.fillWidth: true
        visible: details.length > 0
        title: Theme.tr("pages.driveDiagnostics")
        summary: Theme.tr("pages.drivesUnavailable")
        details: [drive.snapshot.error || ""].concat((drive.snapshot.drives || []).filter(
            row => row.available !== true && row.error
        ).map(row => row.letter + " · " + row.error)).filter(Boolean).join("\n")
    }
}
