import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Pane {
    id: banner
    property string title
    property string description
    property string tone: "info"
    property string glyph: Theme.toneGlyph(tone)
    readonly property color ink: Theme.toneColor(tone)
    Layout.fillWidth: true
    padding: 12
    implicitHeight: implicitContentHeight + topPadding + bottomPadding
    implicitWidth: implicitContentWidth + leftPadding + rightPadding
    background: Rectangle {
        radius: Theme.radiusS
        color: Theme.wash(banner.ink, 0.07, Theme.surface)
        border.color: Theme.highContrast ? Theme.border : Theme.wash(banner.ink, 0.42, Theme.surface)
    }
    contentItem: RowLayout {
        spacing: 12
        Image {
            Layout.alignment: Qt.AlignTop
            Layout.preferredWidth: 20
            Layout.preferredHeight: 20
            source: Theme.icon(banner.glyph, banner.ink)
            Accessible.ignored: true
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 4
            BodyText {
                Layout.fillWidth: true
                text: banner.title
                visible: text.length > 0
                font.weight: Font.DemiBold
            }
            BodyText {
                Layout.fillWidth: true
                text: banner.description
                visible: text.length > 0
                color: Theme.textMuted
            }
        }
    }
}
