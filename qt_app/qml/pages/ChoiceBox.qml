import QtQuick
import QtQuick.Controls.Basic as Controls
import "../components"

Controls.ComboBox {
    id: choice
    required property string label
    Accessible.name: label
    focusPolicy: Qt.StrongFocus
    implicitHeight: 40
    leftPadding: 12
    rightPadding: 36
    font.family: Theme.fontFamily
    font.pixelSize: Theme.fontBody
    palette.buttonText: Theme.text
    palette.windowText: Theme.text
    palette.text: Theme.text
    palette.window: Theme.surface
    palette.base: Theme.surface
    palette.highlight: Theme.accent
    palette.highlightedText: Theme.onAccent
    contentItem: BodyText {
        text: choice.displayText
        verticalAlignment: Text.AlignVCenter
        maximumLineCount: 1
        elide: Text.ElideRight
        Accessible.ignored: true
    }
    background: Rectangle {
        radius: Theme.radiusS
        color: Theme.surfaceAlt
        border.width: choice.activeFocus ? 2 : 1
        border.color: choice.activeFocus ? Theme.focus : Theme.controlBorder
    }
    indicator: Image {
        anchors.right: parent.right
        anchors.rightMargin: 10
        anchors.verticalCenter: parent.verticalCenter
        width: 16; height: 16; sourceSize: Qt.size(16, 16)
        source: Theme.icon("chevron-down", Theme.textMuted)
        Accessible.ignored: true
    }
    popup.height: Math.min(8 * 40 + 8, popup.implicitHeight)
}
