import QtQuick
import QtQuick.Window
import QtQuick.Controls.Basic as Controls
import QtQuick.Layouts
import "../components"

Item {
    id: page
    objectName: "page_" + section
    property string section: "home"
    readonly property bool ready: body.status === Loader.Ready && body.item !== null
    signal navigateRequested(string section)
    readonly property var snapshots: readService.results
    readonly property var turbo: snapshots.turbo_status || ({})
    readonly property var guard: snapshots.guard_status || ({})
    readonly property var driveLetters: readService.driveLetters
    readonly property bool occupied: maintenanceService.busy || maintenanceService.awaitingConfirmation
                                     || updateService.busy || updateService.pending || readService.busy
    property string selectedDrive: ""
    property bool initialized: false
    readonly property var sections: ({
        home: "Home.qml", cleanup: "Cleanup.qml", startup: "Startup.qml", repair: "Repair.qml",
        performance: "Performance.qml", guided: "Guided.qml", history: "History.qml",
        updates: "Updates.qml", settings: "Settings.qml"
    })

    function syncDrive() {
        if (driveLetters.indexOf(selectedDrive) < 0)
            selectedDrive = driveLetters.length ? driveLetters[0] : ""
    }
    onDriveLettersChanged: syncDrive()
    function number(value, digits) {
        return i18n.language ? i18n.number(value, digits) : ""
    }
    function isDriveAction(action) {
        return action === "chkdsk" || action === "drive_optimize"
    }
    function canPrepare(action) {
        if (occupied || (sectionActions[section] || []).indexOf(action) < 0)
            return false
        const shortcuts = ["windows_update", "windows_optional", "apps_settings", "appwiz",
                           "startup_settings", "open_cleanmgr", "open_defrag"]
        if (guard.blocked === true && shortcuts.indexOf(action) === -1)
            return false
        if (isDriveAction(action)) {
            const drives = snapshots.drives || {}
            return drives.available !== false && !drives.error && driveLetters.indexOf(selectedDrive) !== -1
        }
        const turboReady = turbo.available !== false && turbo.refreshing !== true
        if (action === "turbo_off")
            return turboReady && turbo.restore_available === true
        if (action === "turbo_on")
            return turboReady && turbo.master === false
        const setting = /^(power|visual|sysmain|wsearch|spooler)_(on|off)$/.exec(action)
        if (setting) {
            const measured = (turbo.states || {})[setting[1]]
            return turboReady && typeof measured === "boolean"
                   && (setting[2] === "on" ? !measured : measured && turbo.restore_available === true)
        }
        return true
    }
    function prepareAction(action) {
        if (!canPrepare(action))
            return false
        maintenanceService.prepare(action, isDriveAction(action) ? selectedDrive : "")
        return true
    }
    function statusText(status) {
        const known = ["running", "cancelling", "completed", "failed", "partial", "cancelled", "unknown"]
        return status ? Theme.tr("pages.result." + (known.indexOf(status) >= 0 ? status : "unknown")) : ""
    }
    function toneFor(status) {
        if (status === "failed") return "danger"
        if (status === "unknown" || status === "partial") return "warning"
        if (status === "completed") return "success"
        return "info"
    }
    function loadSection() {
        if (sections[section]) body.setSource(Qt.resolvedUrl(sections[section]), {page: page})
        else body.source = ""
        viewport.contentY = 0
    }
    Component.onCompleted: { initialized = true; syncDrive(); loadSection() }
    onSectionChanged: if (initialized) loadSection()

    Flickable {
        id: viewport
        objectName: "pageViewport"
        anchors.fill: parent
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        flickableDirection: Flickable.VerticalFlick
        contentWidth: width
        contentHeight: stack.implicitHeight + 24
        Controls.ScrollBar.vertical: Controls.ScrollBar {
            visible: viewport.contentHeight > viewport.height + 1
            active: size < 1
            policy: Controls.ScrollBar.AsNeeded
            Accessible.name: Theme.tr("pages.scroll")
        }
        ColumnLayout {
            id: stack
            width: Math.min(1100, Math.max(0, viewport.width - 16))
            spacing: Theme.spacing * 2
            ActionRow {
                Layout.fillWidth: true
                visible: page.guard.blocked === true &&
                         ["home", "cleanup", "startup", "repair", "performance"].indexOf(page.section) >= 0
                text: Theme.tr("pages.guard")
                description: Theme.tr("pages.guardBlocked")
                glyph: "warning"; tone: "warning"
                enabled: !page.occupied
                onClicked: page.navigateRequested("guided")
            }
            Loader {
                id: body
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                focus: true
            }
            ActivityLog {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                visible: ["home", "cleanup", "startup", "repair", "performance", "guided"].indexOf(page.section) >= 0 && hasEntries
                pageModel: page
            }
        }
    }
    // Follow keyboard focus inside a long page, including controls loaded by extensions.
    Connections {
        target: page.Window.window
        function onActiveFocusItemChanged() {
            const focusItem = page.Window.window.activeFocusItem
            if (!focusItem || !page.visible) return
            let ancestor = focusItem
            while (ancestor && ancestor !== viewport.contentItem) ancestor = ancestor.parent
            if (!ancestor) return
            const bounds = focusItem.mapToItem(viewport.contentItem, 0, 0, focusItem.width, focusItem.height)
            if (bounds.y < viewport.contentY)
                viewport.contentY = Math.max(0, bounds.y - Theme.spacing)
            else if (bounds.y + bounds.height > viewport.contentY + viewport.height)
                viewport.contentY = Math.min(Math.max(viewport.contentHeight - viewport.height, 0),
                    bounds.y + bounds.height - viewport.height + Theme.spacing)
        }
    }
}
