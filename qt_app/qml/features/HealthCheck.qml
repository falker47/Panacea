import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Basic

Item {
    id: root
    property string language: "en"
    property var theme: ({
        bg: "#0b1525", surface: "#13213a", surfaceAlt: "#1a2b47", border: "#2a3d5c",
        text: "#f1f3f8", textMuted: "#a9b6cc", accent: "#e4c579", onAccent: "#1a1408",
        info: "#76b6e2", success: "#5cc58a", warning: "#f0b44c", danger: "#ef6b6b", focus: "#76b6e2",
        radiusS: 6, radiusM: 10, spacing: 8, fontFamily: "Segoe UI Variable",
        fontSmall: 12, fontBody: 14, fontLabel: 16, fontTitle: 20, fontDisplay: 28, highContrast: false
    })
    signal navigateRequested(string section)
    implicitWidth: 520
    implicitHeight: content.implicitHeight + 2 * theme.spacing
    function t(it, en) { return language === "it" ? it : en }

    component Caption: Label {
        font.family: root.theme.fontFamily
        font.pixelSize: Math.max(12, root.theme.fontBody)
        color: root.theme.text
        textFormat: Text.PlainText
        wrapMode: Text.Wrap
    }
    component ActionButton: Button {
        font.family: root.theme.fontFamily
        font.pixelSize: Math.max(12, root.theme.fontBody)
        focusPolicy: Qt.StrongFocus
        Accessible.role: Accessible.Button
        Accessible.name: text
        palette.buttonText: root.theme.text
        background: Rectangle {
            color: parent.down ? root.theme.border : root.theme.surfaceAlt
            border.color: parent.visualFocus ? root.theme.focus : root.theme.border
            border.width: parent.visualFocus ? 2 : 1
            radius: root.theme.radiusS
        }
    }
    function sizeText(n) {
        if (n === undefined || n === null) return t("Non disponibile", "Unavailable")
        if (n >= 1073741824) return (n / 1073741824).toLocaleString(Qt.locale(language), "f", 1) + " GiB"
        if (n >= 1048576) return (n / 1048576).toLocaleString(Qt.locale(language), "f", 1) + " MiB"
        return Number(n).toLocaleString(Qt.locale(language), "f", 0) + " B"
    }
    readonly property var result: healthService.data
    property bool allChecks: false
    function label(id) {
        const names = {
            space: t("Spazio sull’unità di sistema", "System drive space"), reboot: t("Riavvio in sospeso", "Pending restart"),
            uptime: t("Tempo di attività", "Uptime"), updates: t("Windows Update", "Windows Update"),
            restore: t("Protezione sistema", "System protection"), startup: t("App all’avvio", "Startup apps"),
            reclaimable: t("File recuperabili", "Reclaimable files"), recycle: t("Cestino", "Recycle Bin"),
            guard: t("Blocco manutenzione", "Maintenance guard")
        }
        return names[id] || id
    }
    function evidence(row) {
        const e = row.evidence
        if (row.severity === "unknown") {
            const incomplete = t("Verifica incompleta", "Incomplete check")
            if (row.id === "startup" && typeof e.enabled === "number")
                return e.enabled + t(" abilitati rilevati · ", " observed enabled · ") + incomplete
            if (row.id === "reclaimable" && typeof e.bytes === "number")
                return sizeText(e.bytes) + " · " + incomplete
            return incomplete
        }
        switch (row.id) {
        case "space": return e.drive + " · " + sizeText(e.free_bytes) + t(" liberi su ", " free of ") + sizeText(e.total_bytes)
        case "reboot": return e.indicators.length ? e.indicators.join(", ") : t("Nessun indicatore rilevato", "No restart indicators detected")
        case "uptime": return e.days + t(" giorni dall’avvio", " days since boot")
        case "updates": return e.recommended + t(" consigliati · ", " recommended · ") + e.optional + t(" facoltativi", " optional")
        case "restore": return e.drive + " · " + (e.enabled ? t("Attiva", "Enabled") : t("Verifica Protezione sistema prima di creare un punto.", "Review System Protection before creating a restore point."))
        case "startup": return e.enabled + t(" elementi abilitati", " enabled entries")
        case "guard": return e.blocked ? t("Manutenzione bloccata", "Maintenance is blocked") : t("Disponibile", "Available")
        default: return sizeText(e.bytes)
        }
    }
    function recommendation(row) {
        const names = {
            storage_analysis: t("Analizza lo spazio", "Review storage"), windows_update: t("Apri Windows Update", "Open Windows Update"),
            restore_point: t("Opzioni di ripristino", "Review restore options"), startup_apps: t("Rivedi app", "Review apps"),
            deep_cleanup_preview: t("Vedi anteprima", "Preview cleanup"), recycle_empty: t("Rivedi Cestino", "Review Recycle Bin"),
            guard_status: t("Vedi cronologia", "Review history")
        }
        return names[row.action]
    }

    ColumnLayout {
        id: content
        x: root.theme.spacing
        y: root.theme.spacing
        width: Math.max(0, root.width - 2 * root.theme.spacing)
        spacing: root.theme.spacing
        RowLayout {
            Layout.fillWidth: true
            Caption {
                Layout.fillWidth: true
                text: root.t("Controllo integrità", "Health check")
                font.pixelSize: Math.max(12, root.theme.fontTitle)
                font.bold: true
                Accessible.role: Accessible.Heading
            }
            ActionButton {
                text: root.t("Esegui controllo", "Run check")
                enabled: !healthService.busy
                onClicked: healthService.refresh()
            }
        }
        Caption {
            Layout.fillWidth: true
            visible: text.length > 0
            color: root.theme.textMuted
            text: healthService.busy ? root.t("Verifica in corso…", "Checking…") :
                  root.result.error ? root.t("Controllo non disponibile.", "Health check unavailable.") : ""
        }
        RowLayout {
            Layout.fillWidth: true
            visible: root.result.score !== undefined
            Caption {
                Layout.fillWidth: true
                font.pixelSize: Math.max(12, root.theme.fontLabel)
                text: root.result.score === undefined ? "" : root.t("Punteggio ", "Score ") +
                      (root.result.unknown_weight ? root.result.score_min + "–" : "") + root.result.score + " / 100"
            }
            ActionButton {
                text: root.allChecks ? root.t("Solo da rivedere", "Show findings") : root.t("Tutti i controlli", "Show all checks")
                onClicked: root.allChecks = !root.allChecks
            }
        }
        Caption {
            Layout.fillWidth: true
            visible: root.result.score === 100 && !root.result.unknown_weight && !root.allChecks
            text: root.t("Nessun indicatore supera le soglie.", "No indicators crossed their thresholds.")
        }
        Repeater {
            model: (root.result.findings || []).filter(row => root.allChecks || row.severity !== "ok")
            delegate: RowLayout {
                required property var modelData
                Layout.fillWidth: true
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2
                    Caption {
                        Layout.fillWidth: true
                        font.bold: true
                        text: root.label(modelData.id) + (modelData.deduction ? "  −" + modelData.deduction : "")
                        color: modelData.deduction ? root.theme.warning : root.theme.text
                    }
                    Caption {
                        Layout.fillWidth: true
                        text: root.evidence(modelData)
                        color: root.theme.textMuted
                    }
                }
                ActionButton {
                    visible: modelData.severity === "warning"
                    text: root.recommendation(modelData) || ""
                    onClicked: {
                        if (modelData.action === "windows_update") healthService.windowsUpdate()
                        else root.navigateRequested(modelData.section)
                    }
                }
            }
        }
    }
}
