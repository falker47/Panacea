import QtQuick
import QtQuick.Layouts

Rectangle {
    id: placeholder
    property string label: Theme.tr("controls.loading")
    implicitHeight: 64
    implicitWidth: 160
    Layout.fillWidth: true
    color: Theme.surface
    radius: Theme.radiusM
    border.color: Theme.border
    Accessible.role: Accessible.ProgressBar
    Accessible.name: label
    Column {
        id: lines
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        anchors.margins: 16
        spacing: 8
        Rectangle { width: parent.width * 0.4; height: 8; radius: 4; color: Theme.border }
        Rectangle { width: parent.width * 0.66; height: 8; radius: 4; color: Theme.border }
        SequentialAnimation on opacity {
            running: placeholder.visible && !Theme.reducedMotion && !Theme.highContrast
            loops: Animation.Infinite
            NumberAnimation { from: 1; to: 0.5; duration: 700 }
            NumberAnimation { from: 0.5; to: 1; duration: 700 }
            onStopped: lines.opacity = 1
        }
    }
}
