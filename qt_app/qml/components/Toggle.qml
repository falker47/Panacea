import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Switch {
    id: toggle
    property string description
    Layout.fillWidth: true
    padding: 8
    rightPadding: 8
    spacing: 16
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus
    implicitWidth: implicitContentWidth + leftPadding + rightPadding
    implicitHeight: Math.max(44, implicitContentHeight + topPadding + bottomPadding)
    font.family: Theme.fontFamily
    font.pixelSize: Theme.fontBody
    Accessible.name: text
    Accessible.description: description
    Accessible.onPressAction: if (toggle.enabled) toggle.click()

    background: Rectangle {
        color: toggle.hovered && toggle.enabled ? Theme.surfaceAlt : "transparent"
        radius: Theme.radiusS
        FocusRing { control: toggle }
    }
    indicator: Rectangle {
        id: track
        width: 42
        height: 24
        x: toggle.width - toggle.rightPadding - width
        y: (toggle.height - height) / 2
        radius: height / 2
        color: toggle.checked ? Theme.accent : Theme.surfaceAlt
        border.color: toggle.checked ? Theme.accent : Theme.controlBorder
        Rectangle {
            width: 16
            height: 16
            x: 4 + toggle.visualPosition * (track.width - width - 8)
            y: 4
            radius: height / 2
            color: toggle.checked ? Theme.onAccent : Theme.textMuted
        }
    }
    contentItem: ColumnLayout {
        spacing: 4
        BodyText {
            Layout.fillWidth: true
            Layout.rightMargin: track.width + toggle.spacing
            text: toggle.text
            font.weight: Font.DemiBold
            color: toggle.enabled ? Theme.text : Theme.textMuted
            Accessible.ignored: true
        }
        BodyText {
            Layout.fillWidth: true
            Layout.rightMargin: track.width + toggle.spacing
            visible: text.length > 0
            text: toggle.description
            color: Theme.textMuted
            Accessible.ignored: true
        }
    }
}
