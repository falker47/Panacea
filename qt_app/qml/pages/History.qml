import QtQuick
import QtQuick.Layouts
import "../components"

ColumnLayout {
    id: history
    required property var page
    FeatureSlot {
        id: records
        Layout.fillWidth: true; name: "History"
        onNavigateRequested: section => history.page.navigateRequested(section)
    }
    EmptyState {
        Layout.fillWidth: true
        visible: !records.available && !records.loading
        title: Theme.tr("pages.historyEmpty")
        description: Theme.tr("pages.historyEmptyHint")
        glyph: "clock"
    }
}
