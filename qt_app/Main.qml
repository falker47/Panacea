import QtQuick
import QtQuick.Controls.Basic as Basic
import QtQuick.Layouts
import "qml"
import "qml/components"
import "qml/pages" as Pages

Basic.ApplicationWindow {
    id: shell
    width: 1160
    height: 760
    minimumWidth: 760
    minimumHeight: 480
    visible: true
    title: "Panacea " + updateService.currentVersion + (updateService.eligible ? "" : Theme.tr("shell.qa"))
    color: Theme.bg
    font.family: Theme.fontFamily
    font.pixelSize: Theme.fontBody
    palette.window: Theme.bg
    palette.windowText: Theme.text
    palette.base: Theme.surface
    palette.button: Theme.surfaceAlt
    palette.buttonText: Theme.text
    palette.text: Theme.text
    palette.highlight: Theme.accent
    palette.highlightedText: Theme.onAccent

    property int currentTab: 0
    readonly property string section: sectionIds[currentTab]
    readonly property string language: i18n.language
    property int visitedMask: 1
    property int loadedMask: 0
    property string queuedAction: ""
    readonly property bool compact: width < 1000 || appSettings.sidebarCollapsed
    readonly property bool occupied: maintenanceService.busy || readService.busy || updateService.busy
    readonly property bool inDialog: confirmSheet.visible || whatsNew.visible || paletteDialog.visible
    readonly property bool pendingConsent: maintenanceService.awaitingConfirmation || updateService.pending
    readonly property string activitySection: maintenanceService.busy ? maintenanceService.activeSection :
        updateService.busy ? "updates" : ({"temp_preview":"cleanup", "drives":"performance",
                                         "guard_status":"guided", "turbo_status":"performance"})[readService.lastAction] || "home"
    readonly property string operationTitle: maintenanceService.lastAction && sectionActions[maintenanceService.activeSection] &&
        sectionActions[maintenanceService.activeSection].indexOf(maintenanceService.lastAction) >= 0
        ? Theme.tr("action." + maintenanceService.lastAction + ".title") : maintenanceService.lastTitle
    readonly property string activityText: maintenanceService.busy ?
        Theme.tr("activity." + (maintenanceService.resultStatus === "cancelling" ? "cancelling" : "running"),
                 {action: operationTitle}) : updateService.busy ? Theme.tr(updateService.status, updateService.statusParams)
        : Theme.tr("activity.read")

    function navigate(id) {
        const index = sectionIds.indexOf(id)
        if (index >= 0 && !pendingConsent)
            currentTab = index
    }
    function tryPrepare() {
        if (!queuedAction || occupied || pendingConsent || !(loadedMask & (1 << currentTab)))
            return
        const page = pageLoaders.itemAt(currentTab).item
        if (!page || !page.ready) return
        const action = queuedAction
        queuedAction = ""
        if (!page.prepareAction(action))
            feedback.present(Theme.tr("maintenance.unavailable"), "warning")
    }
    function synchronizeDialogs() {
        if (pendingConsent) {
            if (paletteDialog.visible) paletteDialog.close()
            if (whatsNew.visible) whatsNew.close()
            if (!confirmSheet.visible) confirmSheet.open()
        } else {
            if (confirmSheet.visible) confirmSheet.close()
            if (appSettings.whatsNewVersion && !whatsNew.visible && !paletteDialog.visible)
                whatsNew.open()
        }
    }
    onPendingConsentChanged: Qt.callLater(synchronizeDialogs)
    onOccupiedChanged: if (!occupied) Qt.callLater(tryPrepare)
    onCurrentTabChanged: {
        queuedAction = ""
        visitedMask |= (1 << currentTab)
        const destination = sectionIds[currentTab]
        maintenanceService.setSection(destination)
        if (!qaSmokeMode) {
            if (destination === "home") {
                readService.request("hardware")
                readService.request("windows_updates")
            } else if (destination === "repair" || destination === "performance") {
                readService.request("drives")
                if (destination === "performance") readService.request("turbo_status")
            } else if (destination === "guided") {
                readService.request("guard_status")
            }
        }
    }
    onClosing: function(event) {
        if (maintenanceService.busy || updateService.installing) {
            event.accepted = false
            if (maintenanceService.busy) maintenanceService.cancel()
        }
    }
    Component.onCompleted: Qt.callLater(synchronizeDialogs)

    Shortcut { sequence: "Ctrl+1"; enabled: !shell.inDialog; onActivated: shell.navigate("home") }
    Shortcut { sequence: "Ctrl+2"; enabled: !shell.inDialog; onActivated: shell.navigate("cleanup") }
    Shortcut { sequence: "Ctrl+3"; enabled: !shell.inDialog; onActivated: shell.navigate("startup") }
    Shortcut { sequence: "Ctrl+4"; enabled: !shell.inDialog; onActivated: shell.navigate("repair") }
    Shortcut { sequence: "Ctrl+5"; enabled: !shell.inDialog; onActivated: shell.navigate("performance") }
    Shortcut { sequence: "Ctrl+6"; enabled: !shell.inDialog; onActivated: shell.navigate("guided") }
    Shortcut { sequence: "Ctrl+,"; enabled: !shell.inDialog; onActivated: shell.navigate("settings") }
    Shortcut { sequence: "Ctrl+K"; enabled: !shell.inDialog; onActivated: paletteDialog.open() }

    component Destination: Basic.Button {
        id: dest
        required property string modelData
        objectName: "nav_" + modelData
        Layout.fillWidth: true
        Layout.preferredHeight: shell.height < 600 ? 34 : 42
        text: Theme.tr("nav." + modelData)
        readonly property bool selected: shell.section === modelData
        readonly property color ink: selected ? Theme.accent : Theme.textMuted
        Accessible.name: text
        Accessible.role: Accessible.PageTab
        Accessible.selected: selected
        Basic.ToolTip.visible: shell.compact && hovered
        Basic.ToolTip.text: text
        hoverEnabled: true
        leftPadding: shell.compact ? 0 : 12
        rightPadding: leftPadding
        contentItem: RowLayout {
            spacing: shell.compact ? 0 : 12
            Item { Layout.fillWidth: true; visible: shell.compact }
            Image {
                Layout.preferredWidth: 20
                Layout.preferredHeight: 20
                sourceSize.width: 24
                sourceSize.height: 24
                source: Theme.icon(dest.modelData, dest.ink)
            }
            BodyText {
                visible: !shell.compact
                Layout.fillWidth: true
                text: dest.text
                font.weight: dest.selected ? Font.DemiBold : Font.Normal
                font.pixelSize: Theme.fontBody
                color: dest.selected ? Theme.text : Theme.textMuted
                maximumLineCount: 1
                // Long translations or fallback fonts shrink to the 12 px floor before eliding.
                wrapMode: Text.NoWrap
                fontSizeMode: Text.HorizontalFit
                minimumPixelSize: Theme.fontSmall
                elide: Text.ElideRight
            }
            BodyText {
                visible: !shell.compact && dest.modelData === "updates" && updateService.available
                text: updateService.availableVersion
                color: Theme.accent
                font.pixelSize: Theme.fontSmall
                Accessible.ignored: true
            }
            Item { Layout.fillWidth: true; visible: shell.compact }
        }
        background: Rectangle {
            color: dest.selected || dest.hovered ? Theme.surfaceAlt : "transparent"
            radius: Theme.radiusS
            border.width: dest.visualFocus ? 2 : 0
            border.color: Theme.focus
            Rectangle {
                visible: dest.selected
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                width: 3
                height: 18
                radius: 1
                color: Theme.accent
            }
            Rectangle {
                visible: shell.compact && dest.modelData === "updates" && updateService.available
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 2
                width: 15
                height: width
                radius: width/2
                color: Theme.accent
                Image { anchors.centerIn: parent; width: 11; height: 11; source: Theme.icon("download", Theme.onAccent) }
            }
        }
        Accessible.description: modelData === "updates" && updateService.available ?
            Theme.tr("activity.updateAvailable", {version: updateService.availableVersion}) : ""
        onClicked: shell.navigate(modelData)
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0
        Rectangle {
            id: sidebar
            objectName: "sidebar"
            Layout.preferredWidth: shell.compact ? 64 : 240
            Layout.fillHeight: true
            color: Theme.surface
            Rectangle { anchors.right: parent.right; width: 1; height: parent.height; color: Theme.border }
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: shell.compact ? 8 : 12
                spacing: shell.height < 600 ? 3 : 6
                RowLayout {
                    Layout.fillWidth: true
                    Layout.preferredHeight: shell.height < 600 ? 40 : 64
                    Layout.leftMargin: shell.compact ? 0 : 8
                    spacing: 8
                    Image {
                        objectName: "brandLogo"
                        Layout.preferredWidth: shell.compact ? 36 : 38
                        Layout.preferredHeight: shell.compact ? 36 : 38
                        Layout.alignment: Qt.AlignCenter
                        source: Qt.resolvedUrl("../assets/panacea_icon.png")
                        sourceSize.width: 76
                        sourceSize.height: 76
                        fillMode: Image.PreserveAspectFit
                        Accessible.name: "Panacea"
                        Accessible.role: Accessible.Graphic
                    }
                    BodyText {
                        visible: !shell.compact
                        Layout.fillWidth: true
                        text: "Panacea"
                        color: Theme.text
                        font.pixelSize: Theme.fontTitle
                        font.weight: Font.DemiBold
                    }
                    IconButton {
                        visible: !shell.compact
                        glyph: "panel"
                        text: Theme.tr("sidebar.collapse")
                        variant: "ghost"
                        onClicked: appSettings.sidebarCollapsed = true
                    }
                }
                AppButton {
                    objectName: "openPalette"
                    Layout.fillWidth: true
                    Layout.preferredHeight: shell.height < 600 ? 32 : 38
                    text: shell.compact ? "" : Theme.tr("palette.button")
                    Accessible.name: Theme.tr("palette.search")
                    display: shell.compact ? Basic.AbstractButton.IconOnly : Basic.AbstractButton.TextBesideIcon
                    glyph: "search"
                    onClicked: paletteDialog.open()
                }
                Item { Layout.preferredHeight: shell.height < 600 ? 0 : 10 }
                Repeater { model: sectionIds.slice(0, 6); Destination {} }
                Item { Layout.fillHeight: true; Layout.minimumHeight: 0 }
                Rectangle { Layout.fillWidth: true; height: 1; color: Theme.border }
                Repeater { model: sectionIds.slice(6); Destination {} }
                IconButton {
                    visible: shell.width >= 1000 && shell.compact
                    Layout.alignment: Qt.AlignHCenter
                    text: Theme.tr("sidebar.expand")
                    glyph: "panel"
                    variant: "ghost"
                    onClicked: appSettings.sidebarCollapsed = false
                }
            }
        }
        Item {
            id: workspace
            objectName: "workspace"
            Layout.fillWidth: true
            Layout.fillHeight: true
            readonly property int inset: width < 780 ? 16 : 32
            ColumnLayout {
                id: document
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                anchors.topMargin: workspace.inset
                anchors.bottomMargin: 12
                width: Math.min(1100, parent.width - 2 * workspace.inset)
                spacing: 12
                Pages.FeatureSlot {
                    name: "RecoveryBanner"
                    Layout.fillWidth: true
                    onNavigateRequested: section => shell.navigate(section)
                }
                RowLayout {
                    Layout.fillWidth: true
                    BodyText {
                        objectName: "pageTitle"
                        Layout.fillWidth: true
                        text: Theme.tr("nav." + shell.section)
                        font.pixelSize: Theme.fontDisplay
                        font.weight: Font.DemiBold
                        Accessible.role: Accessible.Heading
                    }
                    BodyText {
                        visible: shell.section === "home"
                        text: "v" + updateService.currentVersion
                        color: Theme.textMuted
                        font.pixelSize: Theme.fontSmall
                    }
                }
                Item {
                    id: pages
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    Repeater {
                        id: pageLoaders
                        model: sectionIds
                        Loader {
                            id: pageLoader
                            required property int index
                            required property string modelData
                            anchors.fill: parent
                            active: !!(shell.visitedMask & (1 << index))
                            visible: shell.currentTab === index
                            asynchronous: true
                            Component.onCompleted: setSource("qml/pages/SectionPage.qml", {section: modelData})
                            onLoaded: {
                                shell.loadedMask |= (1 << index)
                                Qt.callLater(shell.tryPrepare)
                            }
                            Connections {
                                target: pageLoader.item
                                function onReadyChanged() { Qt.callLater(shell.tryPrepare) }
                                function onNavigateRequested(section) { shell.navigate(section) }
                            }
                        }
                    }
                    Skeleton { anchors.fill: parent; visible: !(shell.loadedMask & (1 << shell.currentTab)) }
                }
                Rectangle {
                    id: activity
                    objectName: "activityBar"
                    visible: shell.occupied
                    Layout.fillWidth: true
                    implicitHeight: activityRow.implicitHeight + 12
                    radius: Theme.radiusM
                    color: Theme.surfaceAlt
                    RowLayout {
                        id: activityRow
                        anchors.fill: parent
                        anchors.leftMargin: 12
                        anchors.rightMargin: 8
                        spacing: 8
                        Image { source: Theme.icon("activity", Theme.info); Layout.preferredWidth: 20; Layout.preferredHeight: 20 }
                        BodyText { Layout.fillWidth: true; text: shell.activityText }
                        BodyText {
                            visible: maintenanceService.busy && maintenanceService.progressTotal > 0 || updateService.downloading
                            text: updateService.downloading ? i18n.number(updateService.progress, 0) + "%" :
                                i18n.number(maintenanceService.progressDone, 0) + " / " + i18n.number(maintenanceService.progressTotal, 0)
                        }
                        AppButton { objectName: "activityShow"; text: Theme.tr("activity.show"); variant: "ghost"; onClicked: shell.navigate(shell.activitySection) }
                        AppButton {
                            visible: maintenanceService.busy || updateService.downloading
                            text: Theme.tr("activity.cancel")
                            onClicked: maintenanceService.busy ? maintenanceService.cancel() : updateService.cancelDownload()
                        }
                    }
                }
            }
        }
    }
    CommandPalette {
        id: paletteDialog
        onChosen: function(section, action) {
            shell.navigate(section)
            shell.queuedAction = action
            Qt.callLater(shell.tryPrepare)
        }
    }
    ConfirmSheet {
        id: confirmSheet
        objectName: "confirmationSheet"
        title: updateService.pending ? Theme.tr("confirm.install") : maintenanceService.details.split("\n")[0]
        details: updateService.pending ? Theme.tr(updateService.status, updateService.statusParams) :
            maintenanceService.details.split("\n").slice(1).join("\n")
        destructive: maintenanceService.awaitingConfirmation && maintenanceService.destructive
        onAccepted: {
            if (maintenanceService.awaitingConfirmation) maintenanceService.confirm()
            else if (updateService.pending) updateService.confirmInstall()
        }
        onRejected: {
            if (maintenanceService.awaitingConfirmation) maintenanceService.reject()
            else if (updateService.pending) updateService.reject()
        }
    }
    Basic.Dialog {
        id: whatsNew
        objectName: "whatsNew"
        parent: Basic.Overlay.overlay
        anchors.centerIn: parent
        width: Math.min(540, parent.width - 32)
        modal: true
        focus: true
        title: Theme.tr("update.whatsNew", {version: appSettings.whatsNewVersion})
        background: Rectangle { color: Theme.surface; radius: Theme.radiusM; border.color: Theme.controlBorder }
        contentItem: ColumnLayout {
            spacing: 16
            Basic.ScrollView {
                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(220, newsText.implicitHeight + 8)
                contentWidth: availableWidth
                clip: true
                BodyText {
                    id: newsText
                    width: parent.width
                    text: appSettings.whatsNewNotes || (appSettings.whatsNewVersion === "2.2.0" ?
                        Theme.tr("update.highlights220") : Theme.tr("update.installed"))
                    textFormat: Text.MarkdownText
                }
            }
            AppButton {
                Layout.alignment: Qt.AlignRight
                text: Theme.tr("update.gotIt")
                variant: "primary"
                onClicked: whatsNew.accept()
            }
        }
        onAccepted: appSettings.dismissWhatsNew()
        onRejected: appSettings.dismissWhatsNew()
    }
    Toast { id: feedback }
    Connections {
        target: appSettings
        ignoreUnknownSignals: true
        function onSaveFailed() { feedback.present(Theme.tr("settings.saveFailed"), "danger") }
        function onWhatsNewChanged() { Qt.callLater(shell.synchronizeDialogs) }
    }
    Connections {
        target: maintenanceService
        property bool wasBusy: false
        function onPreparationRejected(key) {
            feedback.present(Theme.tr(key), "danger")
        }
        function onChanged() {
            if (wasBusy !== maintenanceService.busy) {
                wasBusy = maintenanceService.busy
                const message = wasBusy ? shell.activityText : Theme.tr("activity.finished", {action: shell.operationTitle,
                    result: Theme.tr("pages.result." + maintenanceService.resultStatus)})
                if (wasBusy) workspace.Accessible.announce(message, Accessible.Polite)
                else feedback.present(message, maintenanceService.resultStatus === "completed" ? "success" : "warning")
            }
        }
    }
}
