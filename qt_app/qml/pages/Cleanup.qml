import QtQuick
import QtQuick.Layouts
import "../components"

ColumnLayout {
    id: cleanup
    required property var page
    readonly property var preview: page.snapshots.temp_preview || ({})
    readonly property bool hasPreview: typeof preview.count === "number" && typeof preview.bytes === "number"
    spacing: Theme.spacing * 2

    Card {
        Layout.fillWidth: true
        SectionHeader {
            Layout.fillWidth: true
            title: Theme.tr("action.quick_cleanup.title")
            subtitle: Theme.tr("pages.quickDescription")
        }
        AppButton {
            objectName: "action_quick_cleanup"
            text: Theme.tr("pages.reviewCleanup")
            glyph: "cleanup"
            variant: "primary"
            enabled: cleanup.page.canPrepare("quick_cleanup")
            onClicked: cleanup.page.prepareAction("quick_cleanup")
        }
    }
    SequenceProgress {
        Layout.fillWidth: true
        visible: !!result.status
        page: cleanup.page; action: "quick_cleanup"
        operations: ["temp_clean", "recycle_empty", "component_cleanup"]
    }
    FeatureSlot {
        Layout.fillWidth: true; name: "DeepCleanup"
        onNavigateRequested: section => cleanup.page.navigateRequested(section)
    }
    FeatureSlot {
        Layout.fillWidth: true; name: "StorageAnalysis"
        onNavigateRequested: section => cleanup.page.navigateRequested(section)
    }
    ActionRow {
        Layout.fillWidth: true
        objectName: "read_temp_preview"
        glyph: "scan"
        text: Theme.tr("pages.previewTemp")
        description: !cleanup.hasPreview ? Theme.tr(cleanup.preview.available === false ? "pages.previewUnavailable"
                                                                                       : "pages.previewHint")
                     : Theme.tr("pages.previewSize", {count: cleanup.page.number(cleanup.preview.count, 0),
                                                     size: i18n.bytes(cleanup.preview.bytes),
                                                     skipped: cleanup.page.number(cleanup.preview.skipped || 0, 0),
                                                     errors: cleanup.page.number(cleanup.preview.errors || 0, 0)})
        enabled: !cleanup.page.occupied
        onClicked: readService.request("temp_preview")
    }
    ActionList {
        Layout.fillWidth: true; page: cleanup.page; glyph: "cleanup"
        heading: Theme.tr("pages.cleanupIndividual")
        actions: ["temp_clean", "browser_clean", "recycle_empty", "component_cleanup", "open_cleanmgr"]
    }
}
