import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Basic as Basic

Item {
    id: root
    property string language: "en"
    property var theme: ({
        bg: "#0b1525", surface: "#13213a", surfaceAlt: "#1a2b47", border: "#2a3d5c",
        text: "#f1f3f8", textMuted: "#a9b6cc", accent: "#e4c579", onAccent: "#1a1408",
        info: "#76b6e2", success: "#5cc58a", warning: "#f0b44c", danger: "#ef6b6b", focus: "#76b6e2",
        radiusS: 6, radiusM: 10, spacing: 8, fontFamily: "Segoe UI Variable", fontSmall: 12,
        fontBody: 14, fontLabel: 16, fontTitle: 20, fontDisplay: 28, highContrast: false
    })
    signal navigateRequested(string section)
    function t(it, en) { return language === "it" ? it : en }

    component BodyText: Text {
        color: root.theme.text
        font.family: root.theme.fontFamily
        font.pixelSize: Math.max(12, root.theme.fontBody)
        textFormat: Text.PlainText
        wrapMode: Text.Wrap
    }
    component ActionButton: Basic.Button {
        id: button
        focusPolicy: Qt.StrongFocus
        Accessible.role: Accessible.Button
        Accessible.name: text
        font.family: root.theme.fontFamily
        font.pixelSize: Math.max(12, root.theme.fontBody)
        leftPadding: 12
        rightPadding: 12
        topPadding: 7
        bottomPadding: 7
        contentItem: BodyText {
            text: button.text
            color: button.enabled ? root.theme.text : root.theme.textMuted
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
        background: Rectangle {
            radius: root.theme.radiusS
            color: button.down || button.checked ? root.theme.border : root.theme.surfaceAlt
            border.color: button.visualFocus ? root.theme.focus : root.theme.border
            border.width: button.visualFocus ? 2 : 1
        }
    }

    property int offset: 0
    property string filter: ""
    property string expanded: ""
    property bool preview: false
    readonly property var page: historyService.pageData
    readonly property var filters: ["", "completed", "partial", "failed", "unknown", "cancelled", "confirmed"]
    implicitWidth: 560
    implicitHeight: column.implicitHeight
    function statusText(code) {
        switch (code) {
        case "": return t("Tutti gli esiti", "All outcomes")
        case "completed": return t("Completata", "Completed")
        case "partial": return t("Parziale", "Partial")
        case "failed": return t("Non riuscita", "Failed")
        case "unknown": return t("Esito incerto", "Unverified")
        case "cancelled": return t("Annullata", "Cancelled")
        case "confirmed": return t("Confermata", "Confirmed")
        default: return code
        }
    }
    function titleFor(code) {
        const labels = {
            temp_clean: t("File temporanei", "Temporary files"), browser_clean: t("Cache del browser", "Browser caches"),
            quick_cleanup: t("Pulizia rapida", "Quick cleanup"), recycle_empty: t("Svuota cestino", "Empty Recycle Bin"),
            sfc: t("Controllo file di sistema", "System file check"), dism_check: t("Verifica immagine Windows", "Windows image check"),
            dism_restore: t("Riparazione immagine Windows", "Windows image repair"), component_cleanup: t("Archivio componenti", "Component cleanup"),
            restore_point: t("Punto di ripristino", "Restore point"), resurrection: t("Manutenzione guidata", "Guided maintenance"),
            archive_guard: t("Archiviazione dei registri", "Recovery archive"), verify_guard: t("Verifica registri", "Recovery verification"),
            dns_flush: t("Svuota cache DNS", "Flush DNS"), winsock_reset: t("Ripristino Winsock", "Winsock reset"),
            drive_optimize: t("Ottimizzazione unità", "Drive optimization"), chkdsk: t("Controllo disco", "Disk check"),
            appwiz: t("Programmi installati", "Installed programs"), battery_report: t("Rapporto batteria", "Battery report"),
            open_cleanmgr: t("Pulizia disco", "Disk Cleanup"), open_defrag: t("Ottimizza unità", "Optimize Drives"),
            apps_settings: t("Impostazioni app", "App settings"), startup_settings: t("App di avvio", "Startup apps"),
            windows_update: "Windows Update", windows_optional: t("Aggiornamenti facoltativi", "Optional updates")
        }
        if (labels[code]) return labels[code]
        const parts = code.split("_")
        const switches = {turbo: "Turbo", power: t("Energia", "Power"), visual: t("Effetti visivi", "Visual effects"),
                          sysmain: "SysMain", wsearch: "Windows Search", spooler: t("Spooler di stampa", "Print spooler")}
        if (parts.length === 2 && switches[parts[0]])
            return switches[parts[0]] + " · " + (parts[1] === "on" ? t("Attiva", "Enable") : t("Disattiva", "Disable"))
        return code.replace(/_/g, " ")
    }
    function when(value) {
        return Qt.formatDateTime(new Date(value), "yyyy-MM-dd HH:mm:ss")
    }
    function details(row) {
        let lines = [t("Inizio", "Started") + "  " + when(row.started), t("Fine", "Finished") + "  " + when(row.finished)]
        const labels = {count: t("Elementi", "Items"), bytes: "Byte", skipped: t("Ignorati", "Skipped"),
                        errors: t("Errori", "Errors"), total: t("Passaggi", "Steps")}
        for (const key in labels) if (row[key] !== undefined) lines.push(labels[key] + "  " + row[key])
        if (row.restart_required) lines.push(t("Richiede il riavvio di Windows", "Windows restart required"))
        if (row.error_code) lines.push(t("Codice errore", "Error code") + "  " + row.error_code)
        lines.push("Panacea " + row.app_version + "  ·  ID " + row.id)
        return lines.join("\n")
    }
    function load(start, choice) {
        offset = start
        filter = choice
        expanded = ""
        historyService.loadPage(start, choice)
    }
    function feedback(code) {
        switch (code) {
        case "exported": return t("Archivio salvato in Download.", "Archive saved to Downloads.")
        case "exported_no_explorer": return t("Archivio salvato in Download. Esplora file non si è aperto.", "Archive saved to Downloads. Explorer could not open.")
        case "storage_unavailable": return t("Impossibile accedere ai dati di Panacea. Verifica di nuovo.", "Panacea could not access its data. Verify again.")
        case "state_changed": return t("Lo stato è cambiato. Controlla i dati prima di confermare.", "The state changed. Review it before confirming.")
        default: return ""
        }
    }

    Component.onCompleted: load(0, "")
    ColumnLayout {
        id: column
        width: parent.width
        spacing: root.theme.spacing
        BodyText {
            Layout.fillWidth: true
            text: root.t("Cronologia operazioni", "Operation history")
            font.pixelSize: Math.max(12, root.theme.fontTitle)
            font.bold: true
        }
        Flow {
            Layout.fillWidth: true
            spacing: root.theme.spacing
            Basic.ComboBox {
                id: filterBox
                objectName: "historyFilter"
                font.family: root.theme.fontFamily
                font.pixelSize: Math.max(12, root.theme.fontBody)
                focusPolicy: Qt.StrongFocus
                Accessible.role: Accessible.ComboBox
                Accessible.name: root.t("Filtra per esito", "Filter by outcome")
                model: root.filters.map(code => root.statusText(code))
                currentIndex: root.filters.indexOf(root.filter)
                enabled: !historyService.busy
                onActivated: index => root.load(0, root.filters[index])
            }
            ActionButton {
                text: root.t("Aggiorna", "Refresh")
                enabled: !historyService.busy
                onClicked: root.load(0, root.filter)
            }
            ActionButton {
                text: root.t("Esporta diagnostica", "Export diagnostics")
                onClicked: root.preview = !root.preview
            }
        }
        BodyText {
            Layout.fillWidth: true
            visible: root.preview
            text: root.t("File inclusi", "Included files") + "\n" + reliabilityService.diagnosticFiles.join(", ")
        }
        ActionButton {
            visible: root.preview
            enabled: !reliabilityService.busy
            text: root.t("Salva ZIP in Download", "Save ZIP to Downloads")
            onClicked: { root.preview = false; reliabilityService.exportDiagnostics() }
        }
        BodyText {
            Layout.fillWidth: true
            text: root.feedback(reliabilityService.notice)
            visible: text.length > 0
        }
        BodyText {
            Layout.fillWidth: true
            visible: root.page.unavailable || root.page.corrupt > 0
            color: root.theme.warning
            text: root.page.unavailable ? root.t("Cronologia non disponibile.", "History is unavailable.")
                  : root.t("Righe danneggiate ignorate", "Damaged records skipped") + "  " + root.page.corrupt
        }
        BodyText {
            Layout.fillWidth: true
            visible: !root.page.unavailable && !root.page.items.length
            color: root.theme.textMuted
            text: historyService.busy ? root.t("Caricamento…", "Loading…")
                  : root.filter ? root.t("Nessuna operazione con questo esito.", "No operations match this outcome.")
                                : root.t("Le operazioni completate o interrotte appariranno qui.", "Completed and interrupted operations will appear here.")
        }
        Repeater {
            model: root.page.items
            delegate: Rectangle {
                id: entry
                required property var modelData
                Layout.fillWidth: true
                implicitHeight: rowColumn.implicitHeight + 2 * root.theme.spacing
                color: root.theme.surface
                radius: root.theme.radiusS
                border.color: root.theme.border
                ColumnLayout {
                    id: rowColumn
                    x: root.theme.spacing
                    y: root.theme.spacing
                    width: Math.max(0, parent.width - 2 * x)
                    spacing: root.theme.spacing
                    RowLayout {
                        Layout.fillWidth: true
                        BodyText {
                            Layout.fillWidth: true
                            font.bold: true
                            text: root.titleFor(entry.modelData.action)
                        }
                        Rectangle {
                            color: root.theme.surfaceAlt
                            radius: root.theme.radiusS
                            implicitWidth: badge.implicitWidth + 14
                            implicitHeight: badge.implicitHeight + 6
                            BodyText {
                                id: badge
                                anchors.centerIn: parent
                                font.pixelSize: Math.max(12, root.theme.fontSmall)
                                color: entry.modelData.success ? root.theme.success : entry.modelData.status === "failed" ? root.theme.danger : root.theme.warning
                                text: root.statusText(entry.modelData.status)
                            }
                        }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        BodyText {
                            Layout.fillWidth: true
                            color: root.theme.textMuted
                            text: root.when(entry.modelData.finished)
                        }
                        ActionButton {
                            objectName: "historyDetails"
                            text: root.expanded === entry.modelData.id ? root.t("Chiudi", "Close") : root.t("Dettagli", "Details")
                            Accessible.name: text + " · " + root.titleFor(entry.modelData.action)
                            onClicked: root.expanded = root.expanded === entry.modelData.id ? "" : entry.modelData.id
                        }
                    }
                    BodyText {
                        Layout.fillWidth: true
                        visible: root.expanded === entry.modelData.id
                        text: visible ? root.details(entry.modelData) : ""
                    }
                }
            }
        }
        Flow {
            Layout.fillWidth: true
            visible: root.offset > 0 || root.page.has_more
            spacing: root.theme.spacing
            ActionButton {
                text: root.t("Precedenti", "Previous page")
                enabled: root.offset > 0 && !historyService.busy
                onClicked: root.load(Math.max(0, root.offset - 20), root.filter)
            }
            ActionButton {
                text: root.t("Successive", "Next page")
                enabled: root.page.has_more && !historyService.busy
                onClicked: root.load(root.offset + 20, root.filter)
            }
        }
    }
}
