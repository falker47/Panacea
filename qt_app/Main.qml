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
    title: "Panacea Qt · Migrazione in verifica"
    color: "#0b1525"

    property int currentTab: 0
    property var visited: [true, false, false, false, false]
    readonly property var tabs: [
        { name: "Dashboard", detail: "Panoramica", glyph: "◫" },
        { name: "Cleaning", detail: "Pulizia", glyph: "◇" },
        { name: "Tools", detail: "Diagnostica", glyph: "⌘" },
        { name: "Turbo", detail: "Prestazioni", glyph: "⚡" },
        { name: "Resurrect", detail: "Ripristino", glyph: "↻" }
    ]
    readonly property var pages: [
        {
            heading: "Stato del sistema",
            description: "Metriche reali in lettura, stesso backend di Panacea. Nessuna operazione di manutenzione.",
            cards: [
                { title: "Processore", subtitle: "Utilizzo CPU corrente", metric: "cpu", badge: "LIVE", note: "Campionamento Windows in thread separato." },
                { title: "Memoria", subtitle: "RAM utilizzata", metric: "ram", badge: "LIVE", note: "Dato dal modulo originale di monitoraggio." },
                { title: "Disco", subtitle: "Spazio utilizzato sul volume di sistema", metric: "disk", badge: "LIVE", note: "La lettura non modifica il disco." },
                { title: "Protezione", subtitle: "Modalità esperimento", value: "Sola lettura", badge: "LAB", note: "Aggiornamenti disabilitati; manutenzione con conferma e controllo privilegi." },
                { title: "Pulizia", subtitle: "Navigazione verso strumenti di pulizia", value: "Anteprima UI", badge: "LAB", note: "Nessuna cancellazione di file." },
                { title: "Diagnostica", subtitle: "Strumenti nativi di Windows", value: "Anteprima UI", badge: "LAB", note: "Nessun processo di riparazione avviabile." }
            ]
        },
        {
            heading: "Pulizia e spazio",
            description: "Disposizione grafica di prova. I controlli sono intenzionalmente inattivi.",
            cards: [
                { title: "File temporanei", subtitle: "Cartelle temporanee di Windows", value: "Non eseguito", badge: "INATTIVO", note: "Analisi e pulizia non sono collegate." },
                { title: "Cache browser", subtitle: "Chrome, Edge e Firefox", value: "Non eseguito", badge: "INATTIVO", note: "Nessun file viene letto o eliminato." },
                { title: "Cestino", subtitle: "Rimozione elementi eliminati", value: "Non eseguito", badge: "INATTIVO", note: "Il contenuto del Cestino non viene toccato." },
                { title: "Pulizia rapida", subtitle: "Operazioni di manutenzione", value: "Anteprima", badge: "LAB", note: "Il prototipo valuta solo navigazione e densità dei componenti." },
                { title: "Archiviazione", subtitle: "Strumenti nativi di Windows", value: "Non collegato", badge: "INATTIVO", note: "Nessun comando esterno." },
                { title: "Log attività", subtitle: "Dettagli delle operazioni", value: "Nessuna attività", badge: "LAB", note: "Pannello destinato a una successiva migrazione." }
            ]
        },
        {
            heading: "Diagnostica e riparazione",
            description: "Vista densa per confrontare tempi di creazione, scorrimento e ridimensionamento.",
            cards: [
                { title: "Controllo file di sistema", subtitle: "sfc /scannow", value: "Non disponibile", badge: "INATTIVO", note: "Il backend di manutenzione non è collegato." },
                { title: "Integrità Windows", subtitle: "DISM CheckHealth", value: "Non disponibile", badge: "INATTIVO", note: "Nessun processo elevato." },
                { title: "Ripristino immagine", subtitle: "DISM RestoreHealth", value: "Non disponibile", badge: "INATTIVO", note: "Nessun comando avviabile." },
                { title: "DNS", subtitle: "Svuotamento cache di rete", value: "Non disponibile", badge: "INATTIVO", note: "La configurazione di rete resta invariata." },
                { title: "Winsock", subtitle: "Ripristino rete", value: "Non disponibile", badge: "INATTIVO", note: "Non vengono modificati adattatori o socket." },
                { title: "Unità", subtitle: "Ottimizzazione disco", value: "Non disponibile", badge: "INATTIVO", note: "Non viene avviato defrag." },
                { title: "Punto di ripristino", subtitle: "Protezione del sistema", value: "Non disponibile", badge: "INATTIVO", note: "Nessun punto viene creato." },
                { title: "Rapporto batteria", subtitle: "Diagnostica alimentazione", value: "Non disponibile", badge: "INATTIVO", note: "Nessun documento viene generato." }
            ]
        },
        {
            heading: "Prestazioni e avvio",
            description: "Controlli grafici di valutazione, senza modifiche a servizi o registro.",
            cards: [
                { title: "Piano di alimentazione", subtitle: "Profilo energetico", value: "Non collegato", badge: "INATTIVO", note: "Nessuna modifica al piano attivo." },
                { title: "Effetti visivi", subtitle: "Preferenze di Windows", value: "Non collegato", badge: "INATTIVO", note: "Nessuna scrittura nel registro." },
                { title: "SysMain", subtitle: "Servizio Windows", value: "Non collegato", badge: "INATTIVO", note: "Servizio invariato." },
                { title: "Windows Search", subtitle: "Servizio di indicizzazione", value: "Non collegato", badge: "INATTIVO", note: "Servizio invariato." },
                { title: "Spooler", subtitle: "Servizio di stampa", value: "Non collegato", badge: "INATTIVO", note: "Servizio invariato." },
                { title: "Ripristina originali", subtitle: "Impostazioni salvate", value: "Non collegato", badge: "INATTIVO", note: "Il prototipo non salva né modifica configurazioni." }
            ]
        },
        {
            heading: "Ripristino guidato",
            description: "Dieci fasi rappresentative per misurare una schermata complessa, senza eseguire operazioni.",
            cards: [
                { title: "01 · Punto di ripristino", subtitle: "Checkpoint obbligatorio", value: "Non avviato", badge: "SIMULATO", note: "Nessun punto reale creato." },
                { title: "02 · Cache browser", subtitle: "Pulizia dati temporanei", value: "Non avviato", badge: "SIMULATO", note: "Solo composizione visuale." },
                { title: "03 · File temporanei", subtitle: "Pulizia cartelle", value: "Non avviato", badge: "SIMULATO", note: "Nessuna rimozione." },
                { title: "04 · Cestino", subtitle: "Rimozione elementi", value: "Non avviato", badge: "SIMULATO", note: "Nessuna rimozione." },
                { title: "05 · DNS", subtitle: "Reset cache", value: "Non avviato", badge: "SIMULATO", note: "Nessuna modifica." },
                { title: "06 · Winsock", subtitle: "Ripristino rete", value: "Non avviato", badge: "SIMULATO", note: "Nessuna modifica." },
                { title: "07 · Unità", subtitle: "Ottimizzazione guidata", value: "Non avviato", badge: "SIMULATO", note: "Nessuna modifica." },
                { title: "08 · Disco", subtitle: "Verifica unità", value: "Non avviato", badge: "SIMULATO", note: "Nessun comando." },
                { title: "09 · Immagine Windows", subtitle: "Controllo DISM", value: "Non avviato", badge: "SIMULATO", note: "Nessun comando." },
                { title: "10 · File di sistema", subtitle: "Verifica SFC", value: "Non avviato", badge: "SIMULATO", note: "Nessun comando." }
            ]
        }
    ]


    readonly property var maintenanceActions: [
        [],
        [{title:"Pulisci temporanei",action:"temp_clean"},{title:"Cache browser",action:"browser_clean"},{title:"Svuota cestino",action:"recycle_empty"},{title:"Pulizia rapida",action:"quick_cleanup"},{title:"Pulizia Windows",action:"open_cleanmgr"}],
        [{title:"SFC",action:"sfc"},{title:"DISM verifica",action:"dism_check"},{title:"DISM ripara",action:"dism_restore"},{title:"Flush DNS",action:"dns_flush"},{title:"Reset Winsock",action:"winsock_reset"},{title:"Punto ripristino",action:"restore_point"},{title:"Rapporto batteria",action:"battery_report"},{title:"Gestione app",action:"appwiz"},{title:"Windows Update",action:"windows_update"},{title:"Ottimizza dischi",action:"open_defrag"}],
        [{title:"Turbo ON",action:"turbo_on"},{title:"Turbo OFF",action:"turbo_off"},{title:"Piano ON",action:"power_on"},{title:"Piano OFF",action:"power_off"},{title:"Effetti ON",action:"visual_on"},{title:"Effetti OFF",action:"visual_off"},{title:"SysMain ON",action:"sysmain_on"},{title:"SysMain OFF",action:"sysmain_off"},{title:"Search ON",action:"wsearch_on"},{title:"Search OFF",action:"wsearch_off"},{title:"Spooler ON",action:"spooler_on"},{title:"Spooler OFF",action:"spooler_off"},{title:"App avvio",action:"startup_settings"}],
        [{title:"Avvia Resurrection",action:"resurrection"}]
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
                        text: "QT QUICK · MIGRAZIONE"
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
                            text: "MIGRAZIONE IN TEST"
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
                    text: "falker47  ·  Prototype"
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
                                                "Leggi informazioni hardware",
                                                "Analizza file temporanei (nessuna eliminazione)",
                                                "Elenca unità locali",
                                                "Leggi lo stato Turbo",
                                                "Verifica blocchi manutenzione"
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
                                                maximumLineCount: 3
                                                elide: Text.ElideRight
                                            }
                                        }


                                        Rectangle {
                                            width: parent.width - 48
                                            x: 24
                                            height: actionColumn.implicitHeight + 28
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
                                                    text: "Manutenzione (richiede conferma e privilegi Windows)"
                                                    color: "#e4c579"
                                                    font.bold: true
                                                    font.pixelSize: 13
                                                }
                                                Flow {
                                                    width: parent.width
                                                    spacing: 8
                                                    Repeater {
                                                        model: shell.maintenanceActions[pageLoader.pageIndex]
                                                        Rectangle {
                                                            width: 166
                                                            height: 34
                                                            radius: 6
                                                            color: maintenanceService.busy ? "#334158" : "#314b69"
                                                            Text {
                                                                anchors.centerIn: parent
                                                                text: modelData.title
                                                                font.pixelSize: 11
                                                                color: "#f1f3f8"
                                                            }
                                                            MouseArea {
                                                                anchors.fill: parent
                                                                enabled: !maintenanceService.busy
                                                                onClicked: maintenanceService.prepare(modelData.action, modelData.drive || "")
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
                                                    Text { anchors.centerIn: parent; text: "Richiedi annullamento"; color: "white"; font.pixelSize: 11 }
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
