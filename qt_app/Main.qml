import QtQuick
import QtQuick.Window
import QtQuick.Layouts

Window {
    id: shell
    width: 1120
    height: 740
    minimumWidth: 760
    minimumHeight: 480
    visible: true
    title: "Panacea 2.0.2 · Qt QA"
    color: "#0b1525"

    property string language: applicationLanguage
    property int currentTab: 0
    property var visited: [true, false, false, false, false]
    function label(it, en) { return language === "it" ? it : en }
    Component.onCompleted: maintenanceService.setLanguage(language)
    onLanguageChanged: maintenanceService.setLanguage(language)
    onCurrentTabChanged: {
        var visits = visited.slice()
        visits[currentTab] = true
        visited = visits
        if (currentTab === 2 && !readService.busy) readService.request("drives")
        if (currentTab === 3 && !readService.busy) readService.request("turbo_status")
    }
    onClosing: function(event) {
        if (maintenanceService.busy || updateService.installing) {
            event.accepted = false
            if (maintenanceService.busy) maintenanceService.cancel()
        }
    }

    readonly property var tabs: [
        { name: "Dashboard", detail: shell.label("Panoramica", "Overview"), icon: "layout-dashboard.png" },
        { name: "Cleaning", detail: shell.label("Spazio e pulizia", "Space & Cleanup"), icon: "brush-cleaning.png" },
        { name: "Tools", detail: shell.label("Diagnostica e riparazione", "Diagnostics & Repair"), icon: "wrench.png" },
        { name: "Turbo", detail: shell.label("Prestazioni e avvio", "Performance & Startup"), icon: "zap.png" },
        { name: "Resurrect", detail: shell.label("Manutenzione guidata", "Guided Maintenance"), icon: "shield-plus.png" }
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
                    Layout.fillWidth: true
                    Layout.preferredHeight: shell.height < 620 ? 65 : 112
                    Layout.bottomMargin: shell.height < 620 ? 0 : 11
                    spacing: 9
                    Image {
                        source: Qt.resolvedUrl("../assets/panacea_icon.png")
                        sourceSize.width: 148
                        sourceSize.height: 148
                        fillMode: Image.PreserveAspectFit
                        Layout.preferredWidth: 74
                        Layout.preferredHeight: 74
                        Accessible.role: Accessible.Graphic
                        Accessible.name: "Panacea"
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 0
                        Text {
                            text: "Panacea"
                            font.family: "Segoe UI"
                            font.pixelSize: 32
                            font.bold: true
                            color: "#f1f3f8"
                        }
                        Text {
                            text: "SYSTEM MAINTENANCE"
                            font.family: "Segoe UI Semibold"
                            font.pixelSize: 11
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
                        Layout.topMargin: shell.height < 620 ? 1 : 4
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
                                source: Qt.resolvedUrl("../assets/icons/lucide/png/" + modelData.icon)
                                fillMode: Image.PreserveAspectFit
                                sourceSize.width: 48
                                sourceSize.height: 48
                                Layout.preferredWidth: 29
                                Layout.preferredHeight: 29
                                opacity: shell.currentTab === index ? 1 : 0.73
                            }
                            Text {
                                text: modelData.detail
                                color: shell.currentTab === index ? "#f1f3f8" : "#9eafc8"
                                font.family: "Segoe UI"
                                font.pixelSize: 15
                                font.bold: shell.currentTab === index
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
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 58
                    color: "#101d30"
                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 25
                        anchors.rightMargin: 23
                        spacing: 10
                        Text {
                            text: shell.tabs[shell.currentTab].detail
                            font.family: "Segoe UI Semibold"
                            font.pixelSize: 16
                            font.bold: true
                            color: "#f1f3f8"
                            Layout.fillWidth: true
                        }
                        Rectangle {
                            width: 51; height: 28; radius: 6; color: "#263a56"
                            activeFocusOnTab: true
                            Accessible.role: Accessible.Button
                            Accessible.name: shell.label("Cambia lingua", "Switch language")
                            function activate() { shell.language = shell.language === "it" ? "en" : "it" }
                            Keys.onReturnPressed: activate()
                            Keys.onSpacePressed: activate()
                            Text { anchors.centerIn: parent; text: shell.language.toUpperCase(); color: "#e4c579"; font.pixelSize: 12 }
                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: parent.activate() }
                        }
                        Text {
                            text: "QA"
                            color: "#e4c579"
                            font.pixelSize: 11
                            font.bold: true
                        }
                    }
                }
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
                    Layout.preferredHeight: 35
                    color: "#101d30"
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
                    }
                }
            }
        }
    }

    Rectangle {
        anchors.fill: parent
        visible: maintenanceService.awaitingConfirmation
        color: "#cc07101d"
        MouseArea { anchors.fill: parent }
        z: 100
        Rectangle {
            anchors.centerIn: parent
            width: Math.min(parent.width - 48, 540)
            height: 300
            radius: 12
            color: "#1b2b44"
            border.color: "#e4c579"
            Column {
                anchors.fill: parent
                anchors.margins: 22
                spacing: 20
                Text { text: shell.label("Conferma operazione Windows", "Confirm Windows operation"); color: "#e4c579"; font.bold: true; font.pixelSize: 19 }
                Text {
                    width: parent.width
                    height: 170
                    text: maintenanceService.details
                    color: "#f1f3f8"
                    wrapMode: Text.WordWrap
                    font.pixelSize: 13
                }
                Row {
                    spacing: 14
                    Rectangle {
                        width: 145; height: 38; color: "#46556b"; radius: 6
                        Text { anchors.centerIn: parent; text: shell.label("Annulla", "Cancel"); color: "white" }
                        MouseArea { anchors.fill: parent; onClicked: maintenanceService.reject() }
                    }
                    Rectangle {
                        width: 190; height: 38; color: "#8e5e3f"; radius: 6
                        Text { anchors.centerIn: parent; text: shell.label("Confermo l'operazione", "Confirm operation"); color: "white" }
                        MouseArea { anchors.fill: parent; onClicked: maintenanceService.confirm() }
                    }
                }
            }
        }
    }

    Rectangle {
        anchors.fill: parent
        visible: updateService.pending
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
