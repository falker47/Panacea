import QtQuick
import QtQuick.Window
import QtQuick.Layouts

Window {
    id: shell
    width: 1120
    height: 740
    minimumWidth: 850
    minimumHeight: 570
    visible: true
    title: "Panacea Qt · Candidato QA"
    property string language: applicationLanguage
    property string selectedDrive: ""
    function label(it, en) { return language === "it" ? it : en }
    Component.onCompleted: maintenanceService.setLanguage(language)
    onLanguageChanged: maintenanceService.setLanguage(language)
    onClosing: function(event) { if (maintenanceService.busy) { event.accepted = false; maintenanceService.cancel() } }
    color: "#0b1525"

    property int currentTab: 0
    property var visited: [true, false, false, false, false]
    readonly property var tabs: [
        { name: "Dashboard", detail: shell.label("Panoramica","Overview"), glyph: "◫" },
        { name: "Cleaning", detail: shell.label("Pulizia e app","Cleanup & apps"), glyph: "◇" },
        { name: "Tools", detail: shell.label("Strumenti e disco","Tools & disk"), glyph: "⌘" },
        { name: "Turbo", detail: shell.label("Turbo e avvio","Turbo & startup"), glyph: "⚡" },
        { name: "Resurrect", detail: shell.label("Ripristino","Resurrection"), glyph: "↻" }
    ]
    readonly property var pages: [
        { heading: shell.label("Sistema","System"), description: shell.label("Dashboard e controlli di sistema in sola lettura.","Dashboard and read-only system checks."), cards: [
            { title: shell.label("Processore","CPU"), subtitle: shell.label("Utilizzo CPU","CPU utilization"), metric: "cpu", badge: "LIVE", note: shell.label("Campionamento non distruttivo.","Read-only sampling.") },
            { title: shell.label("RAM","RAM"), subtitle: shell.label("Memoria utilizzata","Memory utilization"), metric: "ram", badge: "LIVE", note: shell.label("Campionamento non distruttivo.","Read-only sampling.") },
            { title: shell.label("Disco","Disk"), subtitle: shell.label("Spazio utilizzato","Disk utilization"), metric: "disk", badge: "LIVE", note: shell.label("Campionamento non distruttivo.","Read-only sampling.") },
            { title: shell.label("Dati hardware","Hardware"), subtitle: shell.label("Funzionalità collegata al backend esistente","Uses the existing backend"), value: shell.label("QA","QA"), badge: "QA", note: shell.label("Le operazioni richiedono conferma; consulta il log per i risultati.","Actions require confirmation; check the log for results.") }
        ] },
        { heading: shell.label("Pulizia e applicazioni","Cleanup & apps"), description: shell.label("Pulizia permanente solo dopo conferma esplicita.","Permanent cleanup only after confirmation."), cards: [
            { title: shell.label("Temporanei","Temporary files"), subtitle: shell.label("Funzionalità collegata al backend esistente","Uses the existing backend"), value: shell.label("QA","QA"), badge: "QA", note: shell.label("Le operazioni richiedono conferma; consulta il log per i risultati.","Actions require confirmation; check the log for results.") },
            { title: shell.label("Cache browser","Browser cache"), subtitle: shell.label("Funzionalità collegata al backend esistente","Uses the existing backend"), value: shell.label("QA","QA"), badge: "QA", note: shell.label("Le operazioni richiedono conferma; consulta il log per i risultati.","Actions require confirmation; check the log for results.") },
            { title: shell.label("Cestino","Recycle Bin"), subtitle: shell.label("Funzionalità collegata al backend esistente","Uses the existing backend"), value: shell.label("QA","QA"), badge: "QA", note: shell.label("Le operazioni richiedono conferma; consulta il log per i risultati.","Actions require confirmation; check the log for results.") },
            { title: shell.label("Applicazioni","Apps"), subtitle: shell.label("Funzionalità collegata al backend esistente","Uses the existing backend"), value: shell.label("QA","QA"), badge: "QA", note: shell.label("Le operazioni richiedono conferma; consulta il log per i risultati.","Actions require confirmation; check the log for results.") }
        ] },
        { heading: shell.label("Diagnostica e dischi","Tools & disks"), description: shell.label("Comandi SFC/DISM, riparazione rete e operazioni disco.","SFC/DISM, network repair and disk utilities."), cards: [
            { title: shell.label("SFC / DISM","SFC / DISM"), subtitle: shell.label("Funzionalità collegata al backend esistente","Uses the existing backend"), value: shell.label("QA","QA"), badge: "QA", note: shell.label("Le operazioni richiedono conferma; consulta il log per i risultati.","Actions require confirmation; check the log for results.") },
            { title: shell.label("Dischi","Drives"), subtitle: shell.label("Funzionalità collegata al backend esistente","Uses the existing backend"), value: shell.label("QA","QA"), badge: "QA", note: shell.label("Le operazioni richiedono conferma; consulta il log per i risultati.","Actions require confirmation; check the log for results.") },
            { title: shell.label("Ripristino","Restore points"), subtitle: shell.label("Funzionalità collegata al backend esistente","Uses the existing backend"), value: shell.label("QA","QA"), badge: "QA", note: shell.label("Le operazioni richiedono conferma; consulta il log per i risultati.","Actions require confirmation; check the log for results.") },
            { title: shell.label("Windows Update","Windows Update"), subtitle: shell.label("Funzionalità collegata al backend esistente","Uses the existing backend"), value: shell.label("QA","QA"), badge: "QA", note: shell.label("Le operazioni richiedono conferma; consulta il log per i risultati.","Actions require confirmation; check the log for results.") }
        ] },
        { heading: shell.label("Turbo e avvio","Turbo & startup"), description: shell.label("Controlli di alimentazione e servizi con snapshot originale.","Power and service controls with saved originals."), cards: [
            { title: shell.label("Energia","Power"), subtitle: shell.label("Funzionalità collegata al backend esistente","Uses the existing backend"), value: shell.label("QA","QA"), badge: "QA", note: shell.label("Le operazioni richiedono conferma; consulta il log per i risultati.","Actions require confirmation; check the log for results.") },
            { title: shell.label("Grafica","Visual effects"), subtitle: shell.label("Funzionalità collegata al backend esistente","Uses the existing backend"), value: shell.label("QA","QA"), badge: "QA", note: shell.label("Le operazioni richiedono conferma; consulta il log per i risultati.","Actions require confirmation; check the log for results.") },
            { title: shell.label("Servizi","Services"), subtitle: shell.label("Funzionalità collegata al backend esistente","Uses the existing backend"), value: shell.label("QA","QA"), badge: "QA", note: shell.label("Le operazioni richiedono conferma; consulta il log per i risultati.","Actions require confirmation; check the log for results.") },
            { title: shell.label("Avvio","Startup"), subtitle: shell.label("Funzionalità collegata al backend esistente","Uses the existing backend"), value: shell.label("QA","QA"), badge: "QA", note: shell.label("Le operazioni richiedono conferma; consulta il log per i risultati.","Actions require confirmation; check the log for results.") }
        ] },
        { heading: shell.label("Resurrection","Resurrection"), description: shell.label("Dieci passaggi con punto di ripristino obbligatorio.","Ten steps with a mandatory restore point."), cards: [
            { title: shell.label("Protezione","Protection"), subtitle: shell.label("Funzionalità collegata al backend esistente","Uses the existing backend"), value: shell.label("QA","QA"), badge: "QA", note: shell.label("Le operazioni richiedono conferma; consulta il log per i risultati.","Actions require confirmation; check the log for results.") },
            { title: shell.label("Pulizia","Cleanup"), subtitle: shell.label("Funzionalità collegata al backend esistente","Uses the existing backend"), value: shell.label("QA","QA"), badge: "QA", note: shell.label("Le operazioni richiedono conferma; consulta il log per i risultati.","Actions require confirmation; check the log for results.") },
            { title: shell.label("Diagnostica","Diagnostics"), subtitle: shell.label("Funzionalità collegata al backend esistente","Uses the existing backend"), value: shell.label("QA","QA"), badge: "QA", note: shell.label("Le operazioni richiedono conferma; consulta il log per i risultati.","Actions require confirmation; check the log for results.") },
            { title: shell.label("Risultato","Results"), subtitle: shell.label("Funzionalità collegata al backend esistente","Uses the existing backend"), value: shell.label("QA","QA"), badge: "QA", note: shell.label("Le operazioni richiedono conferma; consulta il log per i risultati.","Actions require confirmation; check the log for results.") }
        ] }
    ]

    onCurrentTabChanged: {
        if (!visited[currentTab]) {
            var flags = visited.slice()
            flags[currentTab] = true
            visited = flags
        }
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        Rectangle {
            Layout.preferredWidth: 254
            Layout.fillHeight: true
            color: "#0e192b"

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 20
                spacing: 14

                Column {
                    Layout.fillWidth: true
                    Layout.topMargin: 18
                    Layout.bottomMargin: 26
                    spacing: 5
                    Text {
                        text: "PANACEA"
                        color: "#e4c579"
                        font.family: "Segoe UI"
                        font.pixelSize: 26
                        font.bold: true
                        font.letterSpacing: 1.3
                    }
                    Text {
                        text: "QT QUICK · CANDIDATO QA"
                        color: "#9eafc8"
                        font.family: "Segoe UI"
                        font.pixelSize: 11
                        font.letterSpacing: 1.2
                    }
                }

                Repeater {
                    model: shell.tabs
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 52
                        radius: 8
                        color: shell.currentTab === index ? "#263a56" : "transparent"
                        border.color: shell.currentTab === index ? "#e4c579" : "transparent"
                        border.width: 1

                        Row {
                            anchors.left: parent.left
                            anchors.leftMargin: 15
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 13
                            Text {
                                width: 21
                                text: modelData.glyph
                                color: shell.currentTab === index ? "#e4c579" : "#9eafc8"
                                font.pixelSize: 19
                                font.family: "Segoe UI Symbol"
                            }
                            Text {
                                text: modelData.detail
                                color: shell.currentTab === index ? "#f1f3f8" : "#b1bfd4"
                                font.family: "Segoe UI"
                                font.pixelSize: 14
                                font.bold: shell.currentTab === index
                            }
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: shell.currentTab = index
                        }
                    }
                }

                Item { Layout.fillHeight: true }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 76
                    color: "#142138"
                    radius: 9
                    Column {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 6
                        Text {
                            text: shell.label("MIGRAZIONE IN TEST","MIGRATION UNDER TEST")
                            color: "#e4c579"
                            font.family: "Segoe UI"
                            font.bold: true
                            font.pixelSize: 11
                        }
                        Text {
                            text: "Azioni disponibili solo con conferma; amministratore richiesto."
                            color: "#9eafc8"
                            font.family: "Segoe UI"
                            font.pixelSize: 11
                            wrapMode: Text.WordWrap
                            width: parent.width
                        }
                    }
                }
                Text {
                    text: "falker47  ·  Qt Candidate"
                    color: "#7488a5"
                    font.family: "Segoe UI"
                    font.pixelSize: 10
                    Layout.bottomMargin: 5
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
                    Layout.preferredHeight: 70
                    color: "#101d30"
                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 29
                        anchors.rightMargin: 28
                        spacing: 10
                        Text {
                            text: shell.tabs[shell.currentTab].name
                            color: "#f1f3f8"
                            font.family: "Segoe UI"
                            font.pixelSize: 17
                            font.bold: true
                        }
                        Item { Layout.fillWidth: true }
                        Rectangle {
                            width: 65; height: 27; radius: 6; color: "#263a56"
                            Accessible.role: Accessible.Button
                            Accessible.name: "Switch language"
                            Text { anchors.centerIn: parent; text: shell.language.toUpperCase(); color: "#e4c579"; font.pixelSize: 12 }
                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: shell.language = shell.language === "it" ? "en" : "it" }
                        }
                        Rectangle {
                            width: 130
                            height: 26
                            radius: 13
                            color: "#27384c"
                            border.color: "#8a7550"
                            Text {
                                anchors.centerIn: parent
                                text: "MIGRATION QA"
                                color: "#e4c579"
                                font.family: "Segoe UI"
                                font.bold: true
                                font.pixelSize: 10
                            }
                        }
                    }
                }

                Item {
                    Layout.fillWidth: true
                    Layout.fillHeight: true

                    Repeater {
                        model: shell.pages.length
                        Loader {
                            id: pageLoader
                            anchors.fill: parent
                            property int pageIndex: index
                            active: shell.visited[index]
                            visible: shell.currentTab === index

                            sourceComponent: Component {
                                Flickable {
                                    id: pageScroll
                                    clip: true
                                    boundsBehavior: Flickable.StopAtBounds
                                    contentWidth: width
                                    contentHeight: pageContent.implicitHeight + 50
                                    property var pageData: shell.pages[pageLoader.pageIndex]

                                    Column {
                                        id: pageContent
                                        width: pageScroll.width
                                        spacing: 16
                                        y: 24

                                        Column {
                                            width: parent.width - 48
                                            x: 24
                                            spacing: 9
                                            Text {
                                                text: pageScroll.pageData.heading
                                                color: "#f1f3f8"
                                                font.family: "Segoe UI"
                                                font.pixelSize: 27
                                                font.bold: true
                                            }
                                            Text {
                                                text: pageScroll.pageData.description
                                                width: parent.width
                                                color: "#9eafc8"
                                                font.family: "Segoe UI"
                                                font.pixelSize: 12
                                                wrapMode: Text.WordWrap
                                            }
                                        }

                                        Rectangle {
                                            id: readPanel
                                            width: parent.width - 48
                                            x: 24
                                            height: 122
                                            color: "#1b2b44"
                                            radius: 10
                                            border.color: "#2e415c"
                                            readonly property var operations: ["hardware", "temp_preview", "drives", "turbo_status", "guard_status"]
                                            readonly property var captions: [
                                                 shell.label("Leggi informazioni hardware","Read hardware information"),
                                                 shell.label("Analizza file temporanei (nessuna eliminazione)","Preview temporary files (no deletion)"),
                                                 shell.label("Elenca unità locali","List local drives"),
                                                 shell.label("Leggi lo stato Turbo","Read Turbo status"),
                                                 shell.label("Verifica blocchi manutenzione","Check maintenance guard")
                                             ]
                                            Rectangle {
                                                id: readButton
                                                x: 15
                                                y: 12
                                                width: Math.min(parent.width - 30, 335)
                                                height: 36
                                                color: readService.busy ? "#334158" : "#765f33"
                                                radius: 6
                                                Text {
                                                    anchors.centerIn: parent
                                                    text: readPanel.captions[pageLoader.pageIndex]
                                                    color: "#f1f3f8"
                                                    font.family: "Segoe UI"
                                                    font.pixelSize: 12
                                                    font.bold: true
                                                }
                                                MouseArea {
                                                    anchors.fill: parent
                                                    enabled: !readService.busy
                                                    cursorShape: Qt.PointingHandCursor
                                                    onClicked: readService.request(readPanel.operations[pageLoader.pageIndex])
                                                }
                                            }
                                            Text {
                                                x: 15
                                                y: 55
                                                width: parent.width - 30
                                                height: 58
                                                text: readService.output
                                                color: "#b7c9db"
                                                font.family: "Segoe UI"
                                                font.pixelSize: 11
                                                wrapMode: Text.WordWrap
                                                maximumLineCount: 4
                                                elide: Text.ElideRight
                                            }
                                        }


                                        Rectangle {
                                            width: parent.width - 48
                                            x: 24
                                            height: visible ? 58 : 0
                                            visible: pageLoader.pageIndex === 2
                                            color: "#1b2b44"
                                            radius: 9
                                            Row {
                                                x: 14; y: 15; spacing: 9
                                                Text { text: shell.label("Unità:", "Drive:"); color: "#a1b3c9"; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
                                                Repeater {
                                                    model: readService.driveLetters
                                                    Rectangle {
                                                        width: 46; height: 28; radius: 5
                                                        color: shell.selectedDrive === modelData ? "#765f33" : "#263a56"
                                                        Accessible.role: Accessible.Button
                                                        Accessible.name: modelData
                                                        Text { anchors.centerIn: parent; text: modelData; color: "#f1f3f8"; font.pixelSize: 12 }
                                                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: shell.selectedDrive = modelData }
                                                    }
                                                }
                                                Text { text: shell.selectedDrive || shell.label("Leggi le unità sopra", "Read drives above"); color: "#e4c579"; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
                                            }
                                        }

                                        Rectangle {
                                            width: parent.width - 48
                                            x: 24
                                            height: visible ? actionColumn.implicitHeight + 28 : 0
                                            visible: maintenanceService.actionCards[pageLoader.pageIndex].length > 0
                                            radius: 10
                                            color: "#1b2b44"
                                            border.color: "#2e415c"
                                            Column {
                                                id: actionColumn
                                                x: 14
                                                y: 14
                                                width: parent.width - 28
                                                spacing: 8
                                                Text {
                                                    text: shell.label("Manutenzione solo con conferma. Non è una release.","Maintenance requires confirmation. Not a release.")
                                                    color: "#e4c579"
                                                    font.bold: true
                                                    font.pixelSize: 13
                                                }
                                                Flow {
                                                    width: parent.width
                                                    spacing: 8
                                                    Repeater {
                                                        model: maintenanceService.actionCards[pageLoader.pageIndex]
                                                        Rectangle {
                                                            width: 166
                                                            height: 34
                                                            radius: 6
                                                            color: maintenanceService.busy ? "#334158" : "#314b69"
                                                            activeFocusOnTab: true
                                                            Accessible.role: Accessible.Button
                                                            Accessible.name: modelData.title
                                                            function activate() {
                                                                if (!maintenanceService.busy && !readService.busy)
                                                                    maintenanceService.prepare(modelData.action, (modelData.action === "drive_optimize" || modelData.action === "chkdsk") ? shell.selectedDrive : "")
                                                            }
                                                            Keys.onReturnPressed: activate()
                                                            Keys.onSpacePressed: activate()
                                                            Text {
                                                                anchors.centerIn: parent
                                                                text: modelData.title
                                                                font.pixelSize: 11
                                                                color: "#f1f3f8"
                                                            }
                                                            MouseArea {
                                                                anchors.fill: parent
                                                                enabled: !maintenanceService.busy && !readService.busy
                                                                cursorShape: Qt.PointingHandCursor
                                                                onClicked: parent.activate()
                                                            }
                                                        }
                                                    }
                                                }
                                                Text {
                                                    width: parent.width
                                                    text: maintenanceService.output
                                                    color: "#b7c9db"
                                                    font.pixelSize: 11
                                                    wrapMode: Text.WrapAnywhere
                                                }
                                                Rectangle {
                                                    visible: maintenanceService.busy
                                                    width: 160
                                                    height: visible ? 32 : 0
                                                    color: "#6b4b39"
                                                    Text { anchors.centerIn: parent; text: shell.label("Richiedi annullamento","Request cancellation"); color: "white"; font.pixelSize: 11 }
                                                    MouseArea { anchors.fill: parent; onClicked: maintenanceService.cancel() }
                                                }
                                            }
                                        }

                                        Flow {
                                            id: cardsFlow
                                            width: parent.width - 48
                                            x: 24
                                            spacing: 12

                                            Repeater {
                                                model: pageScroll.pageData.cards
                                                Rectangle {
                                                    width: cardsFlow.width >= 660 ? Math.floor((cardsFlow.width - 12) / 2) : cardsFlow.width
                                                    height: 158
                                                    color: "#142138"
                                                    border.color: "#2e415c"
                                                    border.width: 1
                                                    radius: 11

                                                    Column {
                                                        anchors.fill: parent
                                                        anchors.margins: 17
                                                        spacing: 10

                                                        Row {
                                                            width: parent.width
                                                            spacing: 8
                                                            Text {
                                                                text: modelData.title
                                                                width: parent.width - marker.width - 12
                                                                color: "#f1f3f8"
                                                                elide: Text.ElideRight
                                                                font.family: "Segoe UI"
                                                                font.bold: true
                                                                font.pixelSize: 15
                                                            }
                                                            Text {
                                                                id: marker
                                                                text: modelData.badge
                                                                color: modelData.badge === "LIVE" ? "#78c8a8" : "#e4c579"
                                                                font.family: "Segoe UI"
                                                                font.pixelSize: 10
                                                                font.bold: true
                                                            }
                                                        }

                                                        Text {
                                                            text: modelData.subtitle
                                                            color: "#9eafc8"
                                                            width: parent.width
                                                            font.family: "Segoe UI"
                                                            font.pixelSize: 12
                                                            elide: Text.ElideRight
                                                        }
                                                        Text {
                                                            text: modelData.metric === "cpu" ? liveMetrics.cpu :
                                                                  modelData.metric === "ram" ? liveMetrics.ram :
                                                                  modelData.metric === "disk" ? liveMetrics.disk : modelData.value
                                                            color: modelData.metric ? "#76b6e2" : "#e4c579"
                                                            font.family: "Segoe UI"
                                                            font.pixelSize: 22
                                                            font.bold: true
                                                        }
                                                        Text {
                                                            text: modelData.note
                                                            width: parent.width
                                                            color: "#8498b2"
                                                            font.family: "Segoe UI"
                                                            font.pixelSize: 11
                                                            wrapMode: Text.WordWrap
                                                        }
                                                    }
                                                }
                                            }
                                        }

                                        Text {
                                            x: 24
                                            width: parent.width - 48
                                            text: "Candidato QA: conferma obbligatoria. Non sostituisce la versione stabile."
                                            color: "#72869f"
                                            font.family: "Segoe UI"
                                            font.pixelSize: 11
                                            wrapMode: Text.WordWrap
                                            topPadding: 8
                                            bottomPadding: 24
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 34
                    color: "#101d30"
                    Text {
                        anchors.left: parent.left
                        anchors.leftMargin: 23
                        anchors.verticalCenter: parent.verticalCenter
                        text: "PANACEA QT QA  ·  MANUTENZIONE CONFERMATA  ·  UPDATER DISABILITATO"
                        color: "#91a5be"
                        font.family: "Segoe UI"
                        font.pixelSize: 10
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
                Text { text: "Conferma operazione Windows"; color: "#e4c579"; font.bold: true; font.pixelSize: 19 }
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
                        Text { anchors.centerIn: parent; text: "Annulla"; color: "white" }
                        MouseArea { anchors.fill: parent; onClicked: maintenanceService.reject() }
                    }
                    Rectangle {
                        width: 190; height: 38; color: "#8e5e3f"; radius: 6
                        Text { anchors.centerIn: parent; text: "Confermo l'operazione"; color: "white" }
                        MouseArea { anchors.fill: parent; onClicked: maintenanceService.confirm() }
                    }
                }
            }
        }
    }
}
