import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Pane {
    id: empty
    property string title
    property string description
    property string glyph: "history"
    Layout.fillWidth: true
    padding: 24
    implicitWidth: implicitContentWidth + leftPadding + rightPadding
    implicitHeight: implicitContentHeight + topPadding + bottomPadding
    background: Rectangle {
        radius: Theme.radiusM
        color: Theme.surface
        border.color: Theme.border
    }
    contentItem: ColumnLayout {
        spacing: Theme.spacing
        Image {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: 32
            Layout.preferredHeight: 32
            source: Theme.icon(empty.glyph, Theme.textMuted)
            Accessible.ignored: true
        }
        BodyText {
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
            text: empty.title
            font.pixelSize: Theme.fontLabel
            font.weight: Font.DemiBold
        }
        BodyText {
            Layout.fillWidth: true
            visible: text.length > 0
            horizontalAlignment: Text.AlignHCenter
            text: empty.description
            color: Theme.textMuted
        }
    }
}
