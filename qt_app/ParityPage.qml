import QtQuick
import QtQuick.Layouts

// Matches the eight V2 subviews inside the five established navigation groups.
// No backend command string is assembled in QML; all changes go through the
// allowlisted, single-use confirmation broker.
Item {
    id: view
    objectName: "parityPage_" + groupIndex
    property int groupIndex: 0
    property string language: "it"
    property string selectedDrive: ""
    property bool showIndividualCleaning: true
    property bool logExpanded: false
    readonly property bool occupied: maintenanceService.busy || readService.busy || updateService.busy
    readonly property var snapshots: readService.results
    readonly property var hardware: snapshots.hardware || ({})
    readonly property var temp: snapshots.temp_preview || ({})
    readonly property var turbo: snapshots.turbo_status || ({})
    readonly property var drives: snapshots.drives || ({})
    readonly property var guard: snapshots.guard_status || ({})
    readonly property var progressSteps: maintenanceService.steps
    function t(it, en) { return language === "it" ? it : en }
    function request(action, drive) {
        if (!occupied)
            maintenanceService.prepare(action, drive || "")
    }
    function showRead(action) {
        if (!occupied)
            readService.request(action)
    }
    function pairedPanelWidth(total, minimum) {
        return total >= 2 * minimum + 20 ? (total - 12) / 2 : total
    }
    function formatBytes(bytes) {
        if (typeof bytes !== "number" || bytes < 0) return "—"
        if (bytes >= 1073741824) return (bytes / 1073741824).toFixed(1) + " GiB"
        return (bytes / 1048576).toFixed(1) + " MiB"
    }
    function stateCaption(value) {
        if (value === true) return t("Attivo", "On")
        if (value === false) return t("Disattivo", "Off")
        return t("Non disponibile", "Unavailable")
    }
    function stepCaption(index) {
        if (progressSteps.length > index) {
            return progressSteps[index].success ? t("Completato", "Completed") : t("Non riuscito", "Failed")
        }
        if (maintenanceService.busy && maintenanceService.lastAction === "resurrection"
                && maintenanceService.progressDone === index)
            return t("In corso", "Running")
        return t("Non eseguito", "Not run")
    }

    component PButton: Rectangle {
        id: button
        property string caption: ""
        property bool primary: false
        property bool interactive: true
        signal pressed()
        implicitWidth: Math.max(90, captionLabel.implicitWidth + 26)
        width: implicitWidth
        height: 34
        radius: 6
        color: !interactive ? "#334158" : primary ? "#765f33" : "#1b2b44"
        border.width: 1
        border.color: activeFocus ? "#76b6e2" : primary ? "#e4c579" : "#2e415c"
        activeFocusOnTab: interactive
        Accessible.role: Accessible.Button
        Accessible.name: caption
        Accessible.description: interactive ? "" : "Unavailable while an operation is running"
        function activate() { if (interactive) pressed() }
        Keys.onReturnPressed: activate()
        Keys.onSpacePressed: activate()
        Text {
            id: captionLabel
            anchors.centerIn: parent
            text: button.caption
            color: button.interactive ? "#f1f3f8" : "#a0aaba"
            font.family: "Segoe UI"
            font.pixelSize: 12
            font.bold: button.primary
        }
        MouseArea {
            anchors.fill: parent
            enabled: button.interactive
            cursorShape: Qt.PointingHandCursor
            onClicked: button.activate()
        }
    }

    component PGroupHeader: Item {
        id: groupHeader
        property string caption: ""
        property string iconName: "dashboard"
        width: parent.width
        implicitHeight: Math.max(38, heading.implicitHeight)
        height: implicitHeight
        Image {
            id: headingIcon
            width: 38
            height: 38
            source: "image://panacea-nav/" + groupHeader.iconName + "/active"
            sourceSize.width: 96
            sourceSize.height: 96
            fillMode: Image.PreserveAspectFit
            smooth: true
            Accessible.role: Accessible.Graphic
            Accessible.name: groupHeader.caption
        }
        Text {
            id: heading
            anchors.left: headingIcon.right
            anchors.right: parent.right
            anchors.leftMargin: 9
            anchors.verticalCenter: parent.verticalCenter
            text: groupHeader.caption
            color: "#f1f3f8"
            font.family: "Segoe UI"
            font.pixelSize: 23
            font.bold: true
            wrapMode: Text.WordWrap
        }
    }

    // The original V2 paired subviews are bordered, independent panels.
    component PPanel: Rectangle {
        id: panelSurface
        default property alias panelContent: panelBody.data
        property alias spacing: panelBody.spacing
        width: parent.width
        implicitHeight: panelBody.implicitHeight + 28
        height: implicitHeight
        radius: 12
        color: "#1b2b44"
        border.width: 1
        border.color: "#2e415c"
        Column {
            id: panelBody
            x: 14
            y: 14
            width: Math.max(0, panelSurface.width - 28)
            spacing: 8
        }
    }

    component PRow: Rectangle {
        id: line
        property string heading: ""
        property string hint: ""
        property string action: ""
        property string buttonText: ""
        property string drive: ""
        property bool interactive: true
        signal invoke(string action, string drive)
        width: parent.width
        height: 70
        color: "#142138"
        radius: 6
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 12
            anchors.rightMargin: 12
            spacing: 10
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Text {
                    text: line.heading
                    Layout.fillWidth: true
                    color: "#f1f3f8"
                    font.family: "Segoe UI"
                    font.bold: true
                    font.pixelSize: 13
                    wrapMode: Text.WordWrap
                    maximumLineCount: 2
                }
                Text {
                    text: line.hint
                    Layout.fillWidth: true
                    color: "#9eafc8"
                    font.family: "Segoe UI"
                    font.pixelSize: 11
                    wrapMode: Text.WordWrap
                    maximumLineCount: 2
                    elide: Text.ElideRight
                }
            }
            PButton {
                caption: line.buttonText
                interactive: line.interactive
                onPressed: line.invoke(line.action, line.drive)
            }
        }
    }

    component PToggle: Rectangle {
        id: toggle
        property bool checked: false
        property bool interactive: true
        property string caption: ""
        signal changed(bool nextValue)
        width: 48
        height: 27
        radius: 14
        color: !interactive ? "#334158" : checked ? "#765f33" : "#30425a"
        border.width: 1
        border.color: activeFocus ? "#76b6e2" : checked ? "#e4c579" : "#59708a"
        activeFocusOnTab: interactive
        Accessible.role: Accessible.CheckBox
        Accessible.name: caption
        Accessible.checked: checked
        function activate() { if (interactive) changed(!checked) }
        Keys.onReturnPressed: activate()
        Keys.onSpacePressed: activate()
        Rectangle {
            x: toggle.checked ? parent.width - width - 4 : 4
            anchors.verticalCenter: parent.verticalCenter
            width: 19; height: 19; radius: 10
            color: toggle.interactive ? "#f1f3f8" : "#9eafc8"
            Behavior on x { NumberAnimation { duration: 130; easing.type: Easing.OutCubic } }
        }
        MouseArea {
            anchors.fill: parent
            enabled: toggle.interactive
            cursorShape: Qt.PointingHandCursor
            onClicked: toggle.activate()
        }
    }

    component PProgress: Rectangle {
        id: progress
        property real fraction: 0
        width: parent.width
        height: 9
        radius: 5
        color: "#283951"
        Rectangle {
            width: Math.max(0, Math.min(1, progress.fraction)) * parent.width
            height: parent.height
            radius: parent.radius
            color: "#e4c579"
            Behavior on width { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }
        }
    }

    component PMiniGraph: Canvas {
        id: spark
        property var points: []
        property color lineColor: "#76b6e2"
        width: parent.width
        height: 45
        onPointsChanged: requestPaint()
        onWidthChanged: requestPaint()
        onPaint: {
            var ctx = getContext("2d")
            ctx.clearRect(0, 0, width, height)
            if (!points || points.length < 2) return
            ctx.beginPath()
            ctx.lineWidth = 2
            ctx.strokeStyle = lineColor
            for (var i = 0; i < points.length; i++) {
                var x = i * (width - 2) / (points.length - 1) + 1
                var y = (height - 3) - Math.max(0, Math.min(100, points[i])) * (height - 6) / 100
                if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y)
            }
            ctx.stroke()
        }
    }

    Flickable {
        id: viewport
        anchors.fill: parent
        clip: true
        contentWidth: width
        contentHeight: content.implicitHeight + 42
        boundsBehavior: Flickable.StopAtBounds

        Column {
            id: content
            x: 22
            y: 23
            width: Math.max(250, viewport.width - 44)
            spacing: 15

            Loader {
                width: parent.width
                height: item ? item.implicitHeight : 0
                sourceComponent: view.groupIndex === 0 ? dashboardSection :
                                 view.groupIndex === 1 ? cleaningAndAppsSection :
                                 view.groupIndex === 2 ? toolsAndDiskSection :
                                 view.groupIndex === 3 ? turboAndStartupSection : resurrectionSection
            }

            Rectangle {
                width: parent.width
                implicitHeight: logColumn.implicitHeight + 20
                height: implicitHeight
                radius: 8
                color: "#142138"
                border.color: "#2e415c"
                Column {
                    id: logColumn
                    width: parent.width - 22
                    x: 11; y: 10; spacing: 9
                    PButton {
                        caption: view.logExpanded ? view.t("− Nascondi dettagli attività", "− Hide activity details")
                                                 : view.t("+ Dettagli attività", "+ Activity details")
                        onPressed: view.logExpanded = !view.logExpanded
                    }
                    Text {
                        visible: view.logExpanded
                        width: parent.width
                        text: maintenanceService.output + "\n" + readService.output
                        wrapMode: Text.WrapAnywhere
                        color: "#b7c9db"
                        font.family: "Consolas"
                        font.pixelSize: 11
                    }
                    PButton {
                        visible: maintenanceService.busy
                        height: visible ? 34 : 0
                        caption: view.t("Annulla dopo la fase corrente", "Cancel after current step")
                        interactive: maintenanceService.busy
                        onPressed: maintenanceService.cancel()
                    }
                }
            }

            Text {
                width: parent.width
                text: view.t("Candidato QA separato dalla versione stabile. Le modifiche richiedono conferma.",
                             "QA candidate separate from the stable version. Changes require confirmation.")
                color: "#8296b0"
                font.pixelSize: 11
                wrapMode: Text.WordWrap
            }
        }
    }

    Component {
        id: dashboardSection
        Column {
            width: parent.width
            spacing: 13
            PGroupHeader { caption: view.t("Panoramica", "Overview"); iconName: "dashboard" }
            Flow {
                id: summaryFlow
                width: parent.width
                spacing: 12
                Rectangle {
                    width: summaryFlow.width >= 670 ? (summaryFlow.width - 12) / 2 : summaryFlow.width
                    height: 128; radius: 8; color: "#142138"; border.color: "#2e415c"
                    Column {
                        anchors.fill: parent; anchors.margins: 14; spacing: 9
                        Row {
                            width: parent.width
                            spacing: 9
                            Image {
                                source: "image://panacea-nav/windows/detail"
                                sourceSize.width: 96
                                sourceSize.height: 96
                                width: 39; height: 39
                                fillMode: Image.PreserveAspectFit
                                smooth: true
                                Accessible.role: Accessible.Graphic
                                Accessible.name: "Windows"
                            }
                            Text {
                                text: view.hardware.os || view.t("Caricamento dettagli Windows…", "Loading Windows details…")
                                width: parent.width - 48
                                font.pixelSize: 17; font.bold: true; color: "#f1f3f8"
                                elide: Text.ElideRight
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }
                        Text {
                            text: view.hardware.cpu_name || view.t("Dati hardware non ancora letti", "Hardware data not yet read")
                            width: parent.width; color: "#9eafc8"; font.pixelSize: 12; elide: Text.ElideRight
                        }
                        PButton {
                            caption: view.t("Leggi hardware", "Read hardware")
                            interactive: !view.occupied
                            onPressed: view.showRead("hardware")
                        }
                    }
                }
                Rectangle {
                    width: summaryFlow.width >= 670 ? (summaryFlow.width - 12) / 2 : summaryFlow.width
                    height: 128; radius: 8; color: "#1b2b44"; border.color: "#2e415c"
                    Column {
                        anchors.fill: parent; anchors.margins: 14; spacing: 9
                        Row {
                            spacing: 8
                            Image {
                                source: "image://panacea-nav/updates/detail"
                                sourceSize.width: 96
                                sourceSize.height: 96
                                width: 46; height: 46
                                fillMode: Image.PreserveAspectFit
                                smooth: true
                            }
                            Text {
                                text: "Windows Update"
                                color: "#f1f3f8"; font.bold: true; font.pixelSize: 16
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }
                        Text {
                            text: view.t("Aggiornamenti gestiti da Windows", "Updates are managed by Windows")
                            color: "#9eafc8"; font.pixelSize: 12
                        }
                        PButton {
                            caption: view.t("Visualizza", "View")
                            interactive: !view.occupied
                            onPressed: view.request("windows_update")
                        }
                    }
                }
            }
            Flow {
                id: metricFlow
                width: parent.width
                spacing: 10
                Repeater {
                    model: [
                        { id: "cpu", icon: "cpu", title: "CPU", value: liveMetrics.cpu, series: liveMetrics.cpuHistory, accent: "#76b6e2", detail: view.hardware.cpu_name || "—" },
                        { id: "ram", icon: "memory", title: view.t("Memoria (RAM)", "Memory (RAM)"), value: liveMetrics.ram, series: liveMetrics.ramHistory, accent: "#e4c579", detail: view.hardware.ram_info || "—" },
                        { id: "disk", icon: "drive", title: view.t("Disco di sistema", "System drive"), value: liveMetrics.disk, series: liveMetrics.diskHistory, accent: "#e4c579", detail: view.hardware.disk_model || "—" }
                    ]
                    Rectangle {
                        width: metricFlow.width >= 660 ? (metricFlow.width - 20) / 3 :
                               metricFlow.width >= 410 ? (metricFlow.width - 10) / 2 : metricFlow.width
                        height: 188
                        radius: 8; color: "#142138"; border.color: "#2e415c"
                        Column {
                            anchors.fill: parent; anchors.margins: 13; spacing: 8
                            Row {
                                spacing: 6
                                Image {
                                    source: "image://panacea-nav/" + modelData.icon + "/detail"
                                    sourceSize.width: 96
                                    sourceSize.height: 96
                                    width: 22; height: 22
                                    fillMode: Image.PreserveAspectFit
                                    smooth: true
                                }
                                Text {
                                    text: modelData.title
                                    color: "#f1f3f8"; font.bold: true; font.pixelSize: 13
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }
                            Text { text: modelData.value; color: "#f1f3f8"; font.bold: true; font.pixelSize: 25 }
                            PMiniGraph {
                                visible: modelData.id !== "disk"
                                width: parent.width
                                height: visible ? 45 : 0
                                points: modelData.series
                                lineColor: modelData.accent
                            }
                            PProgress {
                                visible: modelData.id === "disk"
                                width: parent.width
                                height: visible ? 12 : 0
                                fraction: modelData.id === "disk" ?
                                          Math.max(0, Math.min(1, (parseFloat(modelData.value) || 0) / 100)) : 0
                            }
                            Text {
                                text: modelData.detail
                                width: parent.width; color: "#9eafc8"; font.pixelSize: 11
                                elide: Text.ElideRight
                            }
                        }
                    }
                }
            }
            Flow {
                id: actionFlow
                width: parent.width
                spacing: 10
                Rectangle {
                    width: actionFlow.width >= 570 ? (actionFlow.width - 10) / 2 : actionFlow.width
                    height: 102; radius: 8; color: "#1b2b44"; border.color: "#2e415c"
                    RowLayout {
                        anchors.fill: parent; anchors.margins: 13
                        Image {
                            source: "image://panacea-nav/scan/detail"
                            sourceSize.width: 96
                            sourceSize.height: 96
                            Layout.preferredWidth: 40
                            Layout.preferredHeight: 40
                            fillMode: Image.PreserveAspectFit
                            smooth: true
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            Text { text: view.t("File temporanei","Temporary files"); color: "#f1f3f8"; font.pixelSize: 14; font.bold: true }
                            Text {
                                text: view.temp.no_files_deleted ? view.temp.count + " · " + view.formatBytes(view.temp.bytes)
                                      : view.t("Analisi senza eliminazione","Preview without deletion")
                                Layout.fillWidth: true; color: "#9eafc8"; font.pixelSize: 11
                                wrapMode: Text.WordWrap
                            }
                        }
                        PButton { caption: view.t("Analizza","Analyze"); interactive: !view.occupied; onPressed: view.showRead("temp_preview") }
                    }
                }
                Rectangle {
                    width: actionFlow.width >= 570 ? (actionFlow.width - 10) / 2 : actionFlow.width
                    height: 102; radius: 8; color: "#1b2b44"; border.color: "#2e415c"
                    RowLayout {
                        anchors.fill: parent; anchors.margins: 13
                        Image {
                            source: "image://panacea-nav/restore/detail"
                            sourceSize.width: 96
                            sourceSize.height: 96
                            Layout.preferredWidth: 40
                            Layout.preferredHeight: 40
                            fillMode: Image.PreserveAspectFit
                            smooth: true
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            Text { text: view.t("Punto di ripristino","Restore point"); color: "#f1f3f8"; font.pixelSize: 14; font.bold: true }
                            Text {
                                text: view.t("Creazione con conferma","Confirmation required")
                                color: "#9eafc8"; font.pixelSize: 11; Layout.fillWidth: true
                                wrapMode: Text.WordWrap
                            }
                        }
                        PButton { caption: view.t("Crea","Create"); interactive: !view.occupied; onPressed: view.request("restore_point") }
                    }
                }
            }
        }
    }

    Component {
        id: cleaningAndAppsSection
        Column {
            width: parent.width
            spacing: 12
            PGroupHeader { caption: view.t("Spazio e pulizia", "Space & Cleanup"); iconName: "clean" }
            Rectangle { width: parent.width; height: 1; color: "#2e415c" }
            Flow {
                id: pair
                width: parent.width
                spacing: 12
                PPanel {
                    width: view.pairedPanelWidth(pair.width, 300)
                    spacing: 8
                    Text { text: view.t("Pulizia", "Cleanup"); color: "#f1f3f8"; font.bold: true; font.pixelSize: 19 }
                    Text {
                        text: view.t("File protetti esclusi. I risultati restano nel log.",
                                     "Protected files are skipped. Results remain in the log.")
                        width: parent.width; color: "#9eafc8"; font.pixelSize: 11; wrapMode: Text.WordWrap
                    }
                    Rectangle {
                        width: parent.width; height: 115; radius: 8; color: "#142138"; border.color: "#2e415c"
                        Column {
                            anchors.fill: parent; anchors.margins: 12; spacing: 9
                            PButton { caption: view.t("Avvia pulizia rapida", "Run quick cleanup"); primary: true; interactive: !view.occupied; onPressed: view.request("quick_cleanup") }
                            Text {
                                text: maintenanceService.lastAction === "quick_cleanup" ?
                                      maintenanceService.resultStatus :
                                      view.t("Temporanei, cestino e manutenzione DISM", "Temporary files, Recycle Bin and DISM")
                                width: parent.width; color: "#9eafc8"; font.pixelSize: 11; wrapMode: Text.WordWrap
                            }
                            PProgress { width: parent.width; fraction: maintenanceService.lastAction === "quick_cleanup" && maintenanceService.progressTotal > 0 ? maintenanceService.progressDone / maintenanceService.progressTotal : 0 }
                        }
                    }
                    PButton {
                        caption: view.showIndividualCleaning ? view.t("Nascondi strumenti individuali", "Hide individual tools") : view.t("Mostra strumenti individuali", "Show individual tools")
                        onPressed: view.showIndividualCleaning = !view.showIndividualCleaning
                    }
                    Column {
                        visible: view.showIndividualCleaning
                        width: parent.width
                        spacing: 5
                        PRow { heading: view.t("File temporanei","Temporary files"); hint: view.t("Eliminazione permanente dei file idonei","Permanently delete eligible files"); action:"temp_clean"; buttonText:view.t("Pulisci","Clean"); interactive:!view.occupied; onInvoke: view.request(action,drive) }
                        PRow { heading: view.t("Cache browser","Browser caches"); hint:"Chrome, Edge, Firefox"; action:"browser_clean"; buttonText:view.t("Pulisci","Clean"); interactive:!view.occupied; onInvoke: view.request(action,drive) }
                        PRow { heading: view.t("Cestino","Recycle Bin"); hint: view.t("Svuotamento irreversibile","Irreversible deletion"); action:"recycle_empty"; buttonText:view.t("Svuota","Empty"); interactive:!view.occupied; onInvoke: view.request(action,drive) }
                        PRow { heading: view.t("Archivio componenti","Component store"); hint:"DISM StartComponentCleanup"; action:"component_cleanup"; buttonText:view.t("Esegui","Run"); interactive:!view.occupied; onInvoke: view.request(action,drive) }
                        PRow { heading: view.t("Pulizia disco","Disk Cleanup"); hint: view.t("Strumento nativo di Windows","Native Windows utility"); action:"open_cleanmgr"; buttonText:view.t("Apri","Open"); interactive:!view.occupied; onInvoke: view.request(action,drive) }
                        PButton { caption: view.t("Analizza temporanei (sola lettura)", "Preview temporary files (read-only)"); interactive:!view.occupied; onPressed:view.showRead("temp_preview") }
                        Text {
                            text: view.temp.no_files_deleted ? view.temp.count + " " + view.t("file", "files") + " · " + view.formatBytes(view.temp.bytes) + " · " + view.temp.skipped + " " + view.t("saltati", "skipped") + " · " + view.temp.errors + " " + view.t("errori", "errors") : ""
                            width: parent.width; wrapMode:Text.WordWrap; color:"#9eafc8"; font.pixelSize:11
                        }
                    }
                }
                PPanel {
                    width: view.pairedPanelWidth(pair.width, 300)
                    spacing: 8
                    Text { text: view.t("Applicazioni installate","Installed apps"); font.pixelSize: 19; font.bold: true; color: "#f1f3f8" }
                    Text {
                        text: view.t("Gestisci o disinstalla programmi dalle impostazioni Windows.",
                                     "Manage or uninstall programs in Windows.")
                        width: parent.width; wrapMode:Text.WordWrap; color:"#9eafc8"; font.pixelSize:11
                    }
                    PRow { heading:view.t("Gestione applicazioni","Apps settings"); hint:view.t("Impostazioni Windows","Windows Settings"); action:"apps_settings"; buttonText:view.t("Apri","Open"); interactive:!view.occupied; onInvoke:view.request(action,drive) }
                    PRow { heading:view.t("Programmi classici","Classic programs"); hint:view.t("Programmi e funzionalità","Programs and Features"); action:"appwiz"; buttonText:view.t("Apri","Open"); interactive:!view.occupied; onInvoke:view.request(action,drive) }
                }
            }
        }
    }

    Component {
        id: toolsAndDiskSection
        Column {
            width: parent.width
            spacing: 12
            PGroupHeader { caption: view.t("Diagnostica e riparazione", "Diagnostics & Repair"); iconName: "tools" }
            Rectangle { width: parent.width; height: 1; color: "#2e415c" }
            Flow {
                id: pair
                width: parent.width; spacing: 12
                PPanel {
                    width: view.pairedPanelWidth(pair.width, 305)
                    spacing: 7
                    Text { text: view.t("Strumenti di riparazione","Repair tools"); color:"#f1f3f8"; font.pixelSize:19; font.bold:true }
                    Text { text: view.t("INTEGRITÀ WINDOWS","WINDOWS INTEGRITY"); color:"#e4c579"; font.pixelSize:10; font.bold:true }
                    PRow { heading:view.t("Scansione file di sistema","System file scan"); hint:"SFC /scannow"; action:"sfc"; buttonText:view.t("Analizza","Scan"); interactive:!view.occupied; onInvoke:view.request(action,drive) }
                    PRow { heading:view.t("Salute immagine","Image health"); hint:"DISM CheckHealth"; action:"dism_check"; buttonText:view.t("Verifica","Check"); interactive:!view.occupied; onInvoke:view.request(action,drive) }
                    PRow { heading:view.t("Riparazione immagine","Repair image"); hint:"DISM RestoreHealth"; action:"dism_restore"; buttonText:view.t("Ripara","Repair"); interactive:!view.occupied; onInvoke:view.request(action,drive) }
                    Text { text: view.t("RETE","NETWORK"); color:"#e4c579"; font.pixelSize:10; font.bold:true }
                    PRow { heading:view.t("Svuota DNS","Flush DNS"); hint:view.t("Cancella la cache DNS","Clear cached DNS records"); action:"dns_flush"; buttonText:view.t("Svuota","Flush"); interactive:!view.occupied; onInvoke:view.request(action,drive) }
                    PRow { heading:view.t("Ripristina Winsock","Reset Winsock"); hint:view.t("Potrebbe richiedere riavvio","A restart may be required"); action:"winsock_reset"; buttonText:view.t("Ripristina","Reset"); interactive:!view.occupied; onInvoke:view.request(action,drive) }
                    PRow { heading:view.t("Punto di ripristino","Restore point"); hint:view.t("Crea e verifica","Create and verify"); action:"restore_point"; buttonText:view.t("Crea","Create"); interactive:!view.occupied; onInvoke:view.request(action,drive) }
                    PRow { heading:view.t("Rapporto batteria","Battery report"); hint:view.t("Esporta rapporto HTML","Save an HTML report"); action:"battery_report"; buttonText:view.t("Crea","Create"); interactive:!view.occupied; onInvoke:view.request(action,drive) }
                }
                PPanel {
                    width: view.pairedPanelWidth(pair.width, 305)
                    spacing: 8
                    Text { text: view.t("Ottimizzazione dischi","Drive optimization"); color:"#f1f3f8"; font.pixelSize:19; font.bold:true }
                    Text {
                        text: view.t("Windows sceglie TRIM o deframmentazione in base all'unità.",
                                     "Windows selects TRIM or defragmentation according to drive type.")
                        width: parent.width; wrapMode:Text.WordWrap; color:"#9eafc8"; font.pixelSize:11
                    }
                    Rectangle {
                        width: parent.width; height: 105; radius:8; color:"#142138"; border.color:"#2e415c"
                        Column {
                            anchors.fill:parent; anchors.margins:11; spacing:9
                            Row {
                                spacing:8
                                PButton { caption:view.t("Aggiorna unità", "Refresh drives"); interactive:!view.occupied; onPressed:view.showRead("drives") }
                                Text { text: view.selectedDrive || "—"; color:"#e4c579"; font.pixelSize:13; anchors.verticalCenter:parent.verticalCenter }
                            }
                            Flow {
                                width: parent.width; spacing:6
                                Repeater {
                                    model:readService.driveLetters
                                    PButton {
                                        caption:modelData
                                        primary:view.selectedDrive === modelData
                                        interactive:!view.occupied
                                        onPressed:view.selectedDrive = modelData
                                    }
                                }
                            }
                            Text {
                                text:view.selectedDrive ? view.t("Unità selezionata: ","Selected drive: ") + view.selectedDrive :
                                                         view.t("Seleziona un'unità disponibile", "Select an available drive")
                                color:"#9eafc8"; font.pixelSize:11
                            }
                        }
                    }
                    Repeater {
                        model: view.drives.drives || []
                        Rectangle {
                            width: parent.width
                            height: 86
                            radius: 7
                            color: "#142138"
                            border.color: "#2e415c"
                            Column {
                                anchors.fill: parent
                                anchors.margins: 11
                                spacing: 7
                                RowLayout {
                                    width: parent.width
                                    Text { text: modelData.letter; color: "#f1f3f8"; font.pixelSize: 13; font.bold: true }
                                    Text {
                                        text: modelData.available ?
                                              view.formatBytes(modelData.free_bytes) + " / " + view.formatBytes(modelData.total_bytes) :
                                              view.t("Unità non disponibile", "Drive unavailable")
                                        color: "#9eafc8"
                                        font.pixelSize: 11
                                        Layout.fillWidth: true
                                        horizontalAlignment: Text.AlignRight
                                    }
                                }
                                PProgress {
                                    width: parent.width
                                    fraction: typeof modelData.used_percent === "number" ? modelData.used_percent / 100 : 0
                                }
                                Text {
                                    width: parent.width
                                    color: modelData.available ? "#9eafc8" : "#e4b66d"
                                    font.pixelSize: 10
                                    elide: Text.ElideRight
                                    text: modelData.available ?
                                          view.t("Spazio utilizzato: ", "Used space: ") + modelData.used_percent + "%" :
                                          (modelData.error || view.t("Informazioni non disponibili", "Unavailable"))
                                }
                            }
                        }
                    }
                    PRow { heading:view.t("Ottimizza unità","Optimize drive"); hint:view.t("TRIM / defrag secondo Windows","Windows TRIM / defrag"); action:"drive_optimize"; drive:view.selectedDrive; buttonText:view.t("Ottimizza","Optimize"); interactive:!view.occupied && readService.driveLetters.indexOf(view.selectedDrive) !== -1; onInvoke:view.request(action,drive) }
                    PRow { heading:view.t("Integrità volume","Disk health scan"); hint:"CHKDSK /scan /perf"; action:"chkdsk"; drive:view.selectedDrive; buttonText:view.t("Analizza","Scan"); interactive:!view.occupied && readService.driveLetters.indexOf(view.selectedDrive) !== -1; onInvoke:view.request(action,drive) }
                    PRow { heading:view.t("Ottimizzazione Windows","Windows drive optimizer"); hint:view.t("Interfaccia nativa Windows","Native Windows utility"); action:"open_defrag"; buttonText:view.t("Apri","Open"); interactive:!view.occupied; onInvoke:view.request(action,drive) }
                    PRow { heading:"Windows Update"; hint:view.t("Apri aggiornamenti","Open updates"); action:"windows_update"; buttonText:view.t("Apri","Open"); interactive:!view.occupied; onInvoke:view.request(action,drive) }
                    PRow { heading:view.t("Aggiornamenti facoltativi","Optional updates"); hint:view.t("Impostazioni Windows","Windows Settings"); action:"windows_optional"; buttonText:view.t("Apri","Open"); interactive:!view.occupied; onInvoke:view.request(action,drive) }
                }
            }
        }
    }

    Component {
        id: turboAndStartupSection
        Column {
            width: parent.width; spacing: 12
            PGroupHeader { caption: view.t("Prestazioni e avvio", "Performance & Startup"); iconName: "turbo" }
            Rectangle { width:parent.width; height:1; color:"#2e415c" }
            Flow {
                id: pair
                width: parent.width; spacing:12
                PPanel {
                    width: view.pairedPanelWidth(pair.width, 320)
                    spacing: 8
                    Text { text:view.t("Impostazioni Turbo","Performance settings"); color:"#f1f3f8"; font.bold:true; font.pixelSize:19 }
                    Rectangle {
                        width:parent.width; height:151; color:"#142138"; border.color:"#2e415c"; radius:8
                        Column {
                            anchors.fill:parent; anchors.margins:12; spacing:9
                            RowLayout {
                                width:parent.width
                                Text { text:view.t("Tutte le impostazioni","All settings"); color:"#f1f3f8"; font.bold:true; font.pixelSize:14; Layout.fillWidth:true }
                                Text { text:view.stateCaption(view.turbo.master); color:"#9eafc8"; font.pixelSize:11 }
                                PToggle {
                                    caption:view.t("Turbo completo","All settings")
                                    checked:view.turbo.master === true
                                    interactive: !view.occupied && typeof view.turbo.master === "boolean"
                                    onChanged: view.request(nextValue ? "turbo_on" : "turbo_off")
                                }
                            }
                            Text {
                                text: typeof view.turbo.saved_count === "number" ?
                                      (view.turbo.saved_count > 0 ?
                                       view.t(view.turbo.saved_count + " impostazioni originali disponibili.",
                                              view.turbo.saved_count + " saved original settings available.") :
                                       view.t("Nessun originale da ripristinare.", "No originals available to restore.")) :
                                      view.t("Verifica lo stato degli originali salvati.",
                                             "Check the saved-originals state.")
                                width:parent.width; wrapMode:Text.WordWrap; color:"#9eafc8"; font.pixelSize:11
                            }
                            Row { spacing:8
                                PButton { caption:view.t("Ripristina salvati","Restore originals"); interactive:!view.occupied && view.turbo.restore_available === true; onPressed:view.request("turbo_off") }
                                PButton { caption:view.t("Aggiorna stato","Refresh state"); interactive:!view.occupied; onPressed:view.showRead("turbo_status") }
                            }
                        }
                    }
                    Repeater {
                        model:[
                            {key:"power", name:view.t("Alte prestazioni","High performance"), hint:view.t("Aumenta consumi e calore","More power and heat"), on:"power_on", off:"power_off"},
                            {key:"visual",name:view.t("Effetti visivi","Visual effects"), hint:view.t("Riduce le animazioni","Reduce animations"),on:"visual_on",off:"visual_off"},
                            {key:"sysmain",name:"SysMain",hint:view.t("Pausa precaricamento","Pause preloading"),on:"sysmain_on",off:"sysmain_off"},
                            {key:"wsearch",name:"Windows Search",hint:view.t("Pausa indicizzazione","Pause indexing"),on:"wsearch_on",off:"wsearch_off"},
                            {key:"spooler",name:"Print Spooler",hint:view.t("La stampa viene sospesa","Printing is unavailable"),on:"spooler_on",off:"spooler_off"}
                        ]
                        Rectangle {
                            width:parent.width; height:73; radius:6; color:"#142138"
                            RowLayout {
                                anchors.fill:parent; anchors.margins:11; spacing:10
                                ColumnLayout {
                                    Layout.fillWidth:true; spacing:3
                                    Text { text:modelData.name; color:"#f1f3f8"; font.pixelSize:13; font.bold:true }
                                    Text { text:modelData.hint; color:"#9eafc8"; font.pixelSize:11; Layout.fillWidth:true; wrapMode:Text.WordWrap }
                                }
                                Text { text:view.stateCaption(view.turbo.states ? view.turbo.states[modelData.key] : null); font.pixelSize:10; color:"#9eafc8" }
                                PToggle {
                                    caption:modelData.name
                                    checked:view.turbo.states && view.turbo.states[modelData.key] === true
                                    interactive:!view.occupied && view.turbo.states && typeof view.turbo.states[modelData.key] === "boolean"
                                    onChanged: view.request(nextValue ? modelData.on : modelData.off)
                                }
                            }
                        }
                    }
                    Text {
                        text:view.turbo.states ? view.t("Stato di lettura aggiornabile manualmente.", "State can be refreshed manually.")
                            : view.t("Leggi lo stato prima di usare gli interruttori.", "Read state before using toggles.")
                        width:parent.width; color:"#9eafc8"; font.pixelSize:11; wrapMode:Text.WordWrap
                    }
                }
                PPanel {
                    width: view.pairedPanelWidth(pair.width, 320)
                    spacing: 9
                    Text { text:view.t("Applicazioni all'avvio","Startup apps"); color:"#f1f3f8"; font.bold:true; font.pixelSize:19 }
                    Text {
                        text:view.t("Disabilita applicazioni non necessarie all'accesso a Windows.",
                                     "Disable unnecessary apps at sign-in.")
                        color:"#9eafc8"; width:parent.width; wrapMode:Text.WordWrap; font.pixelSize:11
                    }
                    PRow { heading:view.t("Impostazioni di avvio","Startup settings"); hint:view.t("Gestisci app all'accesso","Manage sign-in apps"); action:"startup_settings"; buttonText:view.t("Apri","Open"); interactive:!view.occupied; onInvoke:view.request(action,drive) }
                }
            }
        }
    }

    Component {
        id: resurrectionSection
        Column {
            width:parent.width; spacing:12
            PGroupHeader { caption: view.t("Manutenzione guidata", "Guided Maintenance"); iconName: "resurrect" }
            Text { text:view.t("10 fasi · Punto di ripristino verificato obbligatorio", "10 steps · Verified restore point required"); color:"#9eafc8"; font.pixelSize:12 }
            Rectangle {
                width:parent.width; height:146; radius:8; color:"#142138"; border.color:"#2e415c"
                Column {
                    anchors.fill:parent; anchors.margins:14; spacing:10
                    Text {
                        text:maintenanceService.lastAction === "resurrection" ? maintenanceService.resultStatus : view.t("Pronto · Nessuna fase eseguita","Ready · No steps run")
                        color:"#f1f3f8"; font.pixelSize:16; font.bold:true
                    }
                    Text { text:maintenanceService.progressDone + " / 10 " + view.t("fasi","steps"); color:"#e4c579"; font.pixelSize:12 }
                    PProgress { width:parent.width; fraction:maintenanceService.progressDone / 10 }
                    Row {
                        spacing:9
                        PButton { caption:view.t("Avvia sequenza","Start sequence"); primary:true; interactive:!view.occupied; onPressed:view.request("resurrection") }
                        PButton { caption:view.t("Annulla dopo la fase","Cancel after step"); interactive:maintenanceService.busy && maintenanceService.lastAction === "resurrection"; onPressed:maintenanceService.cancel() }
                    }
                }
            }
            Rectangle {
                width:parent.width; height:118; radius:8; color:"#242b37"; border.color:"#8d6d40"
                Column {
                    anchors.fill:parent; anchors.margins:13; spacing:8
                    Text { text:view.t("Prima di iniziare", "Before you start"); color:"#e4b66d"; font.bold:true; font.pixelSize:13 }
                    Text {
                        width:parent.width
                        text:view.t("La sequenza verifica prima un nuovo punto di ripristino. Cache browser, temporanei e Cestino vengono poi eliminati definitivamente e non sono recuperabili dal punto di ripristino. La rete potrebbe interrompersi. L'annullamento avviene tra le fasi.",
                                    "A new restore point is verified first. Browser caches, temporary files and the Recycle Bin are then permanently deleted and cannot be recovered by a restore point. Network service may be interrupted. Cancellation occurs between steps.")
                        color:"#f1f3f8"; wrapMode:Text.WordWrap; font.pixelSize:12
                    }
                }
            }
            PButton { caption:view.t("Verifica blocco manutenzione", "Check maintenance guard"); interactive:!view.occupied; onPressed:view.showRead("guard_status") }
            Text {
                text:view.guard.message || ""
                width:parent.width; color:view.guard.blocked ? "#e4b66d" : "#9eafc8"; font.pixelSize:11; wrapMode:Text.WordWrap
            }
            Flow {
                id: stepGrid
                width:parent.width; spacing:8
                Repeater {
                    model:[
                        view.t("Punto di ripristino", "Restore point"),
                        view.t("Cache browser", "Browser caches"),
                        view.t("File temporanei", "Temporary files"),
                        view.t("Cestino", "Recycle Bin"),
                        "DNS",
                        view.t("Reset di rete", "Network reset"),
                        view.t("Ottimizzazione unità", "Drive optimization"),
                        view.t("Scansione disco", "Disk health scan"),
                        view.t("Integrità immagine", "Windows image health"),
                        view.t("Scansione file sistema", "System file scan")
                    ]
                    Rectangle {
                        width:stepGrid.width >= 640 ? (stepGrid.width - 8) / 2 : stepGrid.width
                        height:55; radius:7; color:"#142138"; border.color:"#2e415c"
                        RowLayout {
                            anchors.fill:parent; anchors.margins:10; spacing:9
                            Rectangle {
                                width:25; height:25; radius:13; color:"#263a56"
                                Text { anchors.centerIn:parent; text:(index+1); color:"#e4c579"; font.pixelSize:12; font.bold:true }
                            }
                            Text { text:modelData; Layout.fillWidth:true; color:"#f1f3f8"; font.pixelSize:12; wrapMode:Text.WordWrap }
                            Text { text:view.stepCaption(index); color:index < maintenanceService.progressDone ? "#78c8a8" : "#9eafc8"; font.pixelSize:10 }
                        }
                    }
                }
            }
        }
    }
}
