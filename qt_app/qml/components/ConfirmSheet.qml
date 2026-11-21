import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Dialog {
    id: sheet
    property string details
    property bool destructive: false
    property string confirmText: Theme.tr("controls.confirm")
    property string cancelButtonName: "cancelConfirmation"
    property string confirmButtonName: "confirmConfirmation"

    parent: Overlay.overlay
    anchors.centerIn: parent
    modal: true
    focus: true
    closePolicy: Popup.CloseOnEscape
    width: Math.min(520, parent ? Math.max(0, parent.width - 32) : 520)
    height: Math.min(implicitHeight, parent ? Math.max(0, parent.height - 32) : implicitHeight)
    implicitHeight: implicitContentHeight + topPadding + bottomPadding
    padding: 24
    header: null
    footer: null
    onAboutToShow: copyViewport.contentY = 0
    onOpened: cancelButton.forceActiveFocus(Qt.TabFocusReason)
    background: Rectangle {
        radius: Theme.radiusM
        color: Theme.surface
        border.color: Theme.controlBorder
    }
    Overlay.modal: Rectangle { color: Qt.rgba(Theme.bg.r, Theme.bg.g, Theme.bg.b, 0.78) }

    contentItem: ColumnLayout {
        spacing: 16
        Accessible.role: Accessible.Dialog
        Accessible.name: sheet.title
        Accessible.description: sheet.details
        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            Image {
                Layout.preferredWidth: 28
                Layout.preferredHeight: 28
                source: Theme.icon(sheet.destructive ? "warning" : "info", sheet.destructive ? Theme.danger : Theme.info)
                Accessible.ignored: true
            }
            BodyText {
                Layout.fillWidth: true
                text: sheet.title
                font.pixelSize: Theme.fontTitle
                font.weight: Font.DemiBold
                Accessible.role: Accessible.Heading
                Accessible.name: text
            }
        }
        Flickable {
            id: copyViewport
            objectName: "confirmationViewport"
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.preferredHeight: copyText.implicitHeight
            Layout.minimumHeight: 0
            contentWidth: width
            contentHeight: copyText.implicitHeight
            boundsBehavior: Flickable.StopAtBounds
            flickableDirection: Flickable.VerticalFlick
            clip: true
            ScrollBar.vertical: ScrollBar {
                policy: ScrollBar.AsNeeded
                focusPolicy: Qt.NoFocus
                Accessible.name: Theme.tr("controls.confirm.scroll")
            }
            BodyText {
                id: copyText
                objectName: "confirmationDetails"
                width: Math.max(0, copyViewport.width - 16)
                text: sheet.details
                lineHeight: 1.2
            }
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            Item { Layout.fillWidth: true }
            AppButton {
                id: confirmButton
                objectName: sheet.confirmButtonName
                text: sheet.confirmText
                variant: sheet.destructive ? "danger" : "primary"
                onClicked: sheet.accept()
                KeyNavigation.tab: cancelButton
                KeyNavigation.backtab: cancelButton
                Keys.onEscapePressed: sheet.reject()
            }
            AppButton {
                id: cancelButton
                objectName: sheet.cancelButtonName
                text: Theme.tr("controls.cancel")
                onClicked: sheet.reject()
                KeyNavigation.tab: confirmButton
                KeyNavigation.backtab: confirmButton
                Keys.onEscapePressed: sheet.reject()
            }
        }
        Keys.onPressed: function(event) {
            const up = event.key === Qt.Key_PageUp || event.key === Qt.Key_Up
            const down = event.key === Qt.Key_PageDown || event.key === Qt.Key_Down
            if (!up && !down) return
            const page = event.key === Qt.Key_PageUp || event.key === Qt.Key_PageDown
            const delta = (up ? -1 : 1) * (page ? copyViewport.height : 24)
            const limit = Math.max(0, copyViewport.contentHeight - copyViewport.height)
            copyViewport.contentY = Math.max(0, Math.min(limit, copyViewport.contentY + delta))
            event.accepted = true
        }
    }
}
