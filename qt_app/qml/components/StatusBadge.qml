import QtQuick
import QtQuick.Layouts

RowLayout {
    id: badge
    property string text
    property string tone: "neutral"
    property string glyph: Theme.toneGlyph(tone)
    readonly property color ink: Theme.toneColor(tone)
    spacing: 6
    Accessible.role: Accessible.StaticText
    Accessible.name: text
    Image {
        Layout.preferredWidth: 16
        Layout.preferredHeight: 16
        source: Theme.icon(badge.glyph, badge.ink)
        fillMode: Image.PreserveAspectFit
        Accessible.ignored: true
    }
    BodyText {
        text: badge.text
        color: badge.ink
        font.pixelSize: Theme.fontSmall
        font.weight: Font.DemiBold
        Accessible.ignored: true
    }
}
