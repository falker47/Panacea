import QtQuick
import QtQuick.Window
import QtQuick.Layouts

Window {
    id: shell
    width: 1020
    height: 680
    minimumWidth: 760
    minimumHeight: 480
    visible: true
    title: "Panacea 2.0.2 · Qt QA"
    color: "#0b1525"

    property string language: applicationLanguage
    property int currentTab: 0
    property int loadedMask: 0
    property var visited: [true, false, false, false, false]
    function label(it, en) { return language === "it" ? it : en }
    Component.onCompleted: maintenanceService.setLanguage(language)
    onLanguageChanged: maintenanceService.setLanguage(language)
    onCurrentTabChanged: {
        var visits = visited.slice()
        visits[currentTab] = true
        visited = visits
        if (!qaSmokeMode && currentTab === 2 && !readService.busy) readService.request("drives")
        if (!qaSmokeMode && currentTab === 3 && !readService.busy) readService.request("turbo_status")
    }
    onClosing: function(event) {
        if (maintenanceService.busy || updateService.installing) {
            event.accepted = false
            if (maintenanceService.busy) maintenanceService.cancel()
        }
    }
    Connections {
        target: readService
        property bool wasBusy: false
        function onChanged() {
            if (!qaSmokeMode && readService.busy && !wasBusy && readService.lastAction === "temp_preview")
                shell.currentTab = 1
            wasBusy = readService.busy
        }
    }
    Connections {
        target: maintenanceService
        property bool wasBusy: false
        function onChanged() {
            if (!qaSmokeMode && maintenanceService.busy && !wasBusy) {
                var section = maintenanceService.activeSection
                if (section === "cleaning") shell.currentTab = 1
                else if (section === "tools" || section === "disk") shell.currentTab = 2
                else if (section === "resurrect") shell.currentTab = 4
            }
            wasBusy = maintenanceService.busy
        }
    }

    readonly property var tabs: [
        { name: "Dashboard", detail: shell.label("Panoramica", "Overview"), icon: "dashboard" },
        { name: "Cleaning", detail: shell.label("Spazio e pulizia", "Space & Cleanup"), icon: "clean" },
        { name: "Tools", detail: shell.label("Diagnostica e riparazione", "Diagnostics & Repair"), icon: "tools" },
        { name: "Turbo", detail: shell.label("Prestazioni e avvio", "Performance & Startup"), icon: "turbo" },
        { name: "Resurrect", detail: shell.label("Manutenzione guidata", "Guided Maintenance"), icon: "resurrect" }
    ]

    Shortcut { sequence: "Ctrl+1"; onActivated: shell.currentTab = 0 }
    Shortcut { sequence: "Ctrl+2"; onActivated: shell.currentTab = 1 }
    Shortcut { sequence: "Ctrl+3"; onActivated: shell.currentTab = 2 }
    Shortcut { sequence: "Ctrl+4"; onActivated: shell.currentTab = 3 }
    Shortcut { sequence: "Ctrl+5"; onActivated: shell.currentTab = 4 }

    RowLayout {
        anchors.fill: parent
        spacing: 0
        Rectangle {
            Layout.preferredWidth: 302
            Layout.fillHeight: true
            color: "#0e192b"
            ColumnLayout {
                anchors.fill: parent
                anchors.leftMargin: 11
                anchors.rightMargin: 11
                anchors.topMargin: shell.height < 620 ? 10 : 20
                anchors.bottomMargin: 10
                spacing: shell.height < 620 ? 4 : 12

                RowLayout {
                    id: sidebarBrandRow
                    Layout.fillWidth: true
                    Layout.preferredHeight: shell.height < 620 ? 65 : 112
                    Layout.bottomMargin: shell.height < 620 ? 0 : 11
                    spacing: 9
                    Image {
                        objectName: "brandLogo"
                        Layout.alignment: Qt.AlignVCenter
                        source: Qt.resolvedUrl("../assets/panacea_icon.png")
                        sourceSize.width: 148
                        sourceSize.height: 148
                        fillMode: Image.PreserveAspectFit
                        Layout.preferredWidth: shell.height < 620 ? 74 : 82
                        Layout.preferredHeight: shell.height < 620 ? 74 : 82
                        Accessible.role: Accessible.Graphic
                        Accessible.name: "Panacea"
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignVCenter
                        spacing: 0
                        Text {
                            objectName: "brandWordmark"
                            text: "Panacea"
                            font.family: "Segoe UI"
                            font.pixelSize: shell.height < 620 ? 32 : 38
                            font.bold: true
                            color: "#f1f3f8"
                        }
                        Text {
                            objectName: "brandTagline"
                            text: "SYSTEM MAINTENANCE"
                            font.family: "Segoe UI Semibold"
                            font.pixelSize: shell.height < 620 ? 11 : 12
                            font.bold: true
                            color: "#e4c579"
                        }
                    }
                }

                Repeater {
                    model: shell.tabs
                    Rectangle {
                        id: navEntry
                        Layout.fillWidth: true
                        Layout.preferredHeight: shell.height < 620 ? 43 : 52
                        Layout.topMargin: shell.height < 620 ? 2 : 6
                        radius: 6
                        color: shell.currentTab === index ? "#263a56" : "transparent"
                        border.width: 1
                        border.color: activeFocus ? "#76b6e2" : shell.currentTab === index ? "#e4c579" : "transparent"
                        activeFocusOnTab: true
                        Accessible.role: Accessible.Button
                        Accessible.name: modelData.detail
                        function activate() { shell.currentTab = index }
                        Keys.onSpacePressed: activate()
                        Keys.onReturnPressed: activate()
                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 12
                            anchors.rightMargin: 8
                            spacing: 12
                            Image {
                                source: "image://panacea-nav/" + modelData.icon + "/" + (shell.currentTab === index ? "active" : "idle")
                                fillMode: Image.PreserveAspectFit
                                sourceSize.width: 96
                                sourceSize.height: 96
                                Layout.preferredWidth: 35
                                Layout.preferredHeight: 35
                                opacity: shell.currentTab === index ? 1 : 0.73
                            }
                            Text {
                                text: modelData.detail
                                color: shell.currentTab === index ? "#f1f3f8" : "#9eafc8"
                                font.family: "Segoe UI"
                                font.pixelSize: 16
                                font.weight: Font.DemiBold
                                Layout.fillWidth: true
                                wrapMode: Text.WordWrap
                            }
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: navEntry.activate()
                        }
                    }
                }

                Item { Layout.fillHeight: true }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: updateColumn.implicitHeight + 18
                    color: "#1b2b44"
                    border.color: "#2e415c"
                    radius: 9
                    Column {
                        id: updateColumn
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.leftMargin: 10
                        anchors.rightMargin: 10
                        anchors.top: parent.top
                        anchors.topMargin: 10
                        spacing: 8
                        Text {
                            width: parent.width
                            text: updateService.status
                            color: "#9eafc8"
                            font.family: "Segoe UI"
                            font.pixelSize: 11
                            wrapMode: Text.WordWrap
                            maximumLineCount: 3
                            elide: Text.ElideRight
                        }
                        Rectangle {
                            visible: updateService.available && updateService.eligible
                            width: parent.width; height: visible ? 31 : 0
                            radius: 6
                            color: !updateService.busy ? "#765f33" : "#334158"
                            activeFocusOnTab: visible && !updateService.busy
                            Accessible.role: Accessible.Button
                            Accessible.name: shell.label("Installa aggiornamento verificato", "Install verified update")
                            function activate() { if (!updateService.busy) updateService.prepareInstall() }
                            Keys.onReturnPressed: activate()
                            Keys.onSpacePressed: activate()
                            Text {
                                anchors.centerIn: parent
                                text: shell.label("Installa aggiornamento", "Install update")
                                color: "#f1f3f8"; font.pixelSize: 12
                            }
                            MouseArea { anchors.fill: parent; enabled: !updateService.busy; cursorShape: Qt.PointingHandCursor; onClicked: parent.activate() }
                        }
                        Rectangle {
                            visible: updateService.downloading
                            width: parent.width; height: visible ? 31 : 0
                            radius: 6; color: "#263a56"
                            Text { anchors.centerIn: parent; text: shell.label("Annulla download", "Cancel download"); color: "#f1f3f8"; font.pixelSize: 12 }
                            MouseArea { anchors.fill: parent; onClicked: updateService.cancelDownload() }
                        }
                    }
                }

                Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: "#2e415c" }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 4
                    Text {
                        Layout.fillWidth: true
                        text: "Panacea 2026 — Maurizio Falconi (falker47)"
                        font.family: "Segoe UI"
                        font.pixelSize: 10
                        color: "#e4c579"
                        elide: Text.ElideRight
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: Qt.openUrlExternally("https://github.com/falker47") }
                    }
                    Text { text: "v2.0.2 QA"; color: "#9eafc8"; font.pixelSize: 10 }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: "#0b1525"
            ColumnLayout {
                anchors.fill: parent
                spacing: 0
                Item {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Repeater {
                        model: shell.tabs.length
                        Loader {
                            id: contentLoader
                            anchors.fill: parent
                            property int groupIndex: index
                            active: shell.visited[index]
                            visible: shell.currentTab === index
                            onLoaded: {
                                if (item) shell.loadedMask = shell.loadedMask | (1 << groupIndex)
                            }
                            sourceComponent: Component {
                                ParityPage {
                                    width: parent.width
                                    height: parent.height
                                    groupIndex: contentLoader.groupIndex
                                    language: shell.language
                                }
                            }
                        }
                    }
                }
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 30
                    color: "#0b1525"
                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 24
                        anchors.rightMargin: 24
                        Text {
                            text: maintenanceService.busy ? shell.label("Manutenzione in corso · non chiudere", "Maintenance running · do not close")
                                : maintenanceService.output.length > 0 ? maintenanceService.output.split("\n").slice(-1)[0]
                                : shell.label("Pronto · nessuna operazione in corso", "Ready · No operation running")
                            color: maintenanceService.busy ? "#e4b66d" : "#9eafc8"
                            font.pixelSize: 11
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                        Rectangle {
                            width: 115; height: 24; radius: 5
                            color: "#1b2b44"
                            border.color: activeFocus ? "#76b6e2" : "#2e415c"
                            activeFocusOnTab: !updateService.busy
                            Accessible.role: Accessible.Button
                            Accessible.name: shell.label("Controlla aggiornamenti", "Check updates")
                            function activate() { if (!updateService.busy) updateService.check() }
                            Keys.onReturnPressed: activate()
                            Keys.onSpacePressed: activate()
                            Text {
                                anchors.centerIn: parent
                                text: shell.label("Aggiornamenti", "Check updates")
                                color: "#f1f3f8"
                                font.pixelSize: 10
                            }
                            MouseArea {
                                anchors.fill: parent
                                enabled: !updateService.busy
                                cursorShape: Qt.PointingHandCursor
                                onClicked: parent.activate()
                            }
                        }
                        Rectangle {
                            width: 40; height: 24; radius: 5
                            color: "#263a56"
                            activeFocusOnTab: true
                            Accessible.role: Accessible.Button
                            Accessible.name: shell.label("Cambia lingua", "Switch language")
                            function activate() { shell.language = shell.language === "it" ? "en" : "it" }
                            Keys.onReturnPressed: activate()
                            Keys.onSpacePressed: activate()
                            Text {
                                anchors.centerIn: parent
                                text: shell.language.toUpperCase()
                                color: "#e4c579"
                                font.pixelSize: 11
                            }
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: parent.activate()
                            }
                        }
                        Text {
                            text: "QA"
                            color: "#e4c579"
                            font.pixelSize: 10
                            font.bold: true
                        }
                    }
                }
            }
        }
    }

    FocusScope {
        id: maintenanceDialog
        anchors.fill: parent
        visible: maintenanceService.awaitingConfirmation && !nativeConfirmationsEnabled
        onVisibleChanged: if (visible) cancelMaintenance.forceActiveFocus()
        Keys.onEscapePressed: maintenanceService.reject()
        Rectangle { anchors.fill: parent; color: "#cc07101d" }
        MouseArea { anchors.fill: parent }
        z: 100
        Rectangle {
            id: confirmationPanel
            anchors.centerIn: parent
            width: Math.min(parent.width - 48, 540)
            height: Math.min(parent.height - 48, Math.max(300, confirmationCopy.implicitHeight + 150))
            radius: 12
            color: "#1b2b44"
            border.color: "#e4c579"
            Column {
                anchors.fill: parent
                anchors.margins: 22
                spacing: 20
                Text { id: confirmationHeading; width: parent.width; wrapMode: Text.WordWrap; text: shell.label("Conferma operazione Windows", "Confirm Windows operation"); color: "#e4c579"; font.bold: true; font.pixelSize: 19 }
                Flickable {
                    width: parent.width
                    height: confirmationPanel.height - 44 - confirmationHeading.height - 40 - 38
                    contentWidth: width
                    contentHeight: confirmationCopy.implicitHeight
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    Text {
                        id: confirmationCopy
                        width: parent.width
                        text: maintenanceService.details
                        textFormat: Text.PlainText
                        color: "#f1f3f8"
                        wrapMode: Text.WordWrap
                        font.pixelSize: 13
                    }
                }
                Row {
                    id: confirmationActions
                    height: 38
                    spacing: 14
                    Rectangle {
                        id: cancelMaintenance
                        width: 145; height: 38; color: "#46556b"; radius: 6
                        activeFocusOnTab: true
                        border.color: activeFocus ? "#76b6e2" : "transparent"
                        Accessible.role: Accessible.Button
                        Accessible.name: shell.label("Annulla", "Cancel")
                        KeyNavigation.tab: confirmMaintenance
                        KeyNavigation.backtab: confirmMaintenance
                        Keys.onReturnPressed: maintenanceService.reject()
                        Keys.onSpacePressed: maintenanceService.reject()
                        Text { anchors.centerIn: parent; text: shell.label("Annulla", "Cancel"); color: "white" }
                        MouseArea { anchors.fill: parent; onClicked: maintenanceService.reject() }
                    }
                    Rectangle {
                        id: confirmMaintenance
                        width: 190; height: 38; color: "#8e5e3f"; radius: 6
                        activeFocusOnTab: true
                        border.color: activeFocus ? "#76b6e2" : "transparent"
                        Accessible.role: Accessible.Button
                        Accessible.name: shell.label("Confermo l'operazione", "Confirm operation")
                        KeyNavigation.tab: cancelMaintenance
                        KeyNavigation.backtab: cancelMaintenance
                        Keys.onReturnPressed: maintenanceService.confirm()
                        Keys.onSpacePressed: maintenanceService.confirm()
                        Text { anchors.centerIn: parent; text: shell.label("Confermo l'operazione", "Confirm operation"); color: "white" }
                        MouseArea { anchors.fill: parent; onClicked: maintenanceService.confirm() }
                    }
                }
            }
        }
    }

    Rectangle {
        anchors.fill: parent
        visible: updateService.pending && !nativeConfirmationsEnabled
        color: "#cc07101d"
        z: 110
        MouseArea { anchors.fill: parent }
        Rectangle {
            anchors.centerIn: parent
            width: Math.min(parent.width - 48, 540)
            height: 250
            radius: 12
            color: "#1b2b44"
            border.color: "#e4c579"
            Column {
                anchors.fill: parent
                anchors.margins: 22
                spacing: 17
                Text {
                    text: shell.label("Installa aggiornamento verificato","Install verified update")
                    color: "#e4c579"; font.bold: true; font.pixelSize: 19
                }
                Text {
                    width: parent.width
                    text: shell.label("Scaricare, verificare SHA-256 e installare Panacea ", "Download, verify SHA-256 and install Panacea ")
                          + updateService.availableVersion
                          + shell.label("? Il programma attuale rimarrà disponibile fino alla conferma del nuovo avvio.",
                                        "? The current program remains available until new startup is confirmed.")
                    color: "#f1f3f8"
                    wrapMode: Text.WordWrap
                    font.pixelSize: 13
                }
                Row {
                    spacing: 14
                    Rectangle {
                        width: 145; height: 38; color: "#46556b"; radius: 6
                        activeFocusOnTab: true
                        Accessible.role: Accessible.Button
                        Accessible.name: shell.label("Annulla aggiornamento","Cancel update")
                        function activate() { updateService.reject() }
                        Text { anchors.centerIn: parent; text: shell.label("Annulla","Cancel"); color: "white" }
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: parent.activate() }
                        Keys.onReturnPressed: activate()
                        Keys.onSpacePressed: activate()
                    }
                    Rectangle {
                        width: 210; height: 38; color: "#8e5e3f"; radius: 6
                        activeFocusOnTab: true
                        Accessible.role: Accessible.Button
                        Accessible.name: shell.label("Conferma aggiornamento","Confirm update")
                        function activate() { updateService.confirmInstall() }
                        Text { anchors.centerIn: parent; text: shell.label("Conferma installazione","Confirm installation"); color: "white" }
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: parent.activate() }
                        Keys.onReturnPressed: activate()
                        Keys.onSpacePressed: activate()
                    }
                }
            }
        }
    }
}
