import QtQuick

Rectangle {
    objectName: "focusRing"
    required property Item control
    anchors.fill: parent
    anchors.margins: -3
    radius: Theme.radiusS + 3
    color: "transparent"
    border.color: Theme.focus
    border.width: 2
    visible: control.visualFocus
    Accessible.ignored: true
}
