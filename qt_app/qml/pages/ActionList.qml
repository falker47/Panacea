import QtQuick
import QtQuick.Layouts
import "../components"

ColumnLayout {
    id: group
    required property var page
    required property var actions
    required property string glyph
    property string heading: ""
    spacing: Theme.spacing
    SectionHeader {
        Layout.fillWidth: true
        visible: !!group.heading
        title: group.heading
    }
    Repeater {
        model: group.actions
        delegate: CatalogAction {
            required property string modelData
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            page: group.page
            actionId: modelData
            glyph: group.glyph
        }
    }
}
