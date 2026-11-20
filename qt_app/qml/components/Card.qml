import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Pane {
    id: control
    default property alias body: column.data
    property int bodySpacing: Theme.spacing
    property color fill: Theme.surface
    padding: 2 * Theme.spacing
    implicitWidth: column.implicitWidth + leftPadding + rightPadding
    implicitHeight: column.implicitHeight + topPadding + bottomPadding
    background: Rectangle {
        color: control.fill
        border.color: Theme.border
        radius: Theme.radiusM
    }
    contentItem: ColumnLayout {
        id: column
        spacing: control.bodySpacing
    }
}
