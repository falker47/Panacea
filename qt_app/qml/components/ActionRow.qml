import QtQuick
import QtQuick.Layouts

AppButton {
    id: row
    property alias title: row.text
    property string description
    property string status
    property string tone: "neutral"
    Layout.fillWidth: true
    leftPadding: Theme.spacing
    rightPadding: Theme.spacing
    implicitHeight: Math.max(48, implicitContentHeight + topPadding + bottomPadding)
    implicitWidth: implicitContentWidth + leftPadding + rightPadding
    Accessible.description: [description, status].filter(Boolean).join(". ")

    background: Rectangle {
        radius: Theme.radiusS
        color: row.down || (row.hovered && row.enabled) ? Theme.surfaceAlt : "transparent"
        border.width: Theme.highContrast ? 1 : 0
        border.color: Theme.controlBorder
        FocusRing { control: row }
    }
    contentItem: RowLayout {
        spacing: 12
        Image {
            Layout.preferredWidth: 22
            Layout.preferredHeight: 22
            visible: row.glyph.length > 0
            source: Theme.icon(row.glyph, row.enabled ? Theme.info : Theme.textMuted)
            fillMode: Image.PreserveAspectFit
            Accessible.ignored: true
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 4
            BodyText {
                Layout.fillWidth: true
                text: row.text
                font.weight: Font.DemiBold
                color: row.enabled ? Theme.text : Theme.textMuted
                Accessible.ignored: true
            }
            BodyText {
                Layout.fillWidth: true
                visible: text.length > 0
                text: row.description
                color: Theme.textMuted
                Accessible.ignored: true
            }
        }
        StatusBadge {
            visible: row.status.length > 0
            text: row.status
            tone: row.tone
            Accessible.ignored: true
        }
        Image {
            Layout.preferredWidth: 16
            Layout.preferredHeight: 16
            source: Theme.icon("chevron-right", Theme.textMuted)
            Accessible.ignored: true
        }
    }
}
