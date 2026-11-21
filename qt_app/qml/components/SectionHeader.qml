import QtQuick
import QtQuick.Layouts

ColumnLayout {
    id: control
    property string title
    property string subtitle
    property bool large: false
    spacing: 4
    BodyText {
        Layout.fillWidth: true
        text: control.title
        font.pixelSize: control.large ? Theme.fontDisplay : Theme.fontTitle
        font.weight: Font.DemiBold
        Accessible.role: Accessible.Heading
        Accessible.name: text
    }
    BodyText {
        Layout.fillWidth: true
        visible: text.length > 0
        text: control.subtitle
        color: Theme.textMuted
    }
}
