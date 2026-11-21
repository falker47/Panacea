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
    readonly property var result: deepCleanupService.data
    property var choices: ({})
    function chosen(row) {
        return row.available && (choices[row.id] !== undefined ? choices[row.id] : row.default_selected)
    }
    readonly property var selected: (result.categories || []).filter(row => chosen(row)).map(row => row.id)
    function label(id) {
        const names = {
            wer_reports: t("Segnalazioni errori Windows", "Windows error reports"),
            thumbnail_cache: t("Cache miniature e icone", "Thumbnail and icon caches"),
            shader_cache: t("Cache shader DirectX", "DirectX shader cache"),
            delivery_optimization: t("Ottimizzazione recapito", "Delivery Optimization"),
            crash_dumps: t("Dump di arresto anomalo", "Crash dumps"),
            panacea_leftovers: t("Download Panacea scaduti", "Stale Panacea downloads")
        }
        return names[id] || id
    }
    function outcome(code) {
        const states = {completed: t("Completata", "Completed"), partial: t("Parziale", "Partial"),
            unavailable: t("Non disponibile", "Unavailable"), failed: t("Non riuscita", "Failed"),
            cancelled: t("Annullata", "Cancelled"), unknown: t("Esito sconosciuto", "Completion unknown"),
            stale: t("Anteprima scaduta", "Preview changed"), not_run: t("Non eseguita", "Not run")}
        return states[code] || code
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
                text: root.t("Pulizia approfondita", "Deep cleanup")
                font.pixelSize: Math.max(12, root.theme.fontTitle)
                font.bold: true
                Accessible.role: Accessible.Heading
            }
            ActionButton {
                text: root.t("Anteprima", "Preview")
                enabled: !deepCleanupService.busy
                onClicked: deepCleanupService.refresh()
            }
        }
        Caption {
            Layout.fillWidth: true
            color: root.theme.textMuted
            text: deepCleanupService.busy ? root.t("Operazione in corso…", "Working…") :
                  root.result.error ? root.t("Anteprima non disponibile.", "Preview unavailable.") :
                  root.t("I download di Windows Update restano al loro posto. Per i file di manutenzione usa DISM o Pulizia disco.",
                         "Windows Update downloads stay in place. For servicing files, use DISM component cleanup or Disk Cleanup.")
        }
        Repeater {
            model: root.result.categories || []
            delegate: ColumnLayout {
                required property var modelData
                Layout.fillWidth: true
                spacing: 2
                CheckBox {
                    id: choice
                    Layout.fillWidth: true
                    text: root.label(modelData.id) + " · " + (modelData.available ?
                          modelData.count + root.t(" file · ", " files · ") + root.sizeText(modelData.bytes) :
                          root.t("Non disponibile", "Unavailable"))
                    font.family: root.theme.fontFamily
                    font.pixelSize: Math.max(12, root.theme.fontBody)
                    palette.windowText: root.theme.text
                    palette.highlight: root.theme.focus
                    focusPolicy: Qt.StrongFocus
                    Accessible.role: Accessible.CheckBox
                    Accessible.name: text
                    checked: root.chosen(modelData)
                    enabled: modelData.available && !deepCleanupService.busy
                    onToggled: {
                        const next = Object.assign({}, root.choices)
                        next[modelData.id] = checked
                        root.choices = next
                    }
                }
                Caption {
                    Layout.leftMargin: root.theme.spacing * 3
                    Layout.fillWidth: true
                    color: root.theme.warning
                    visible: modelData.id === "crash_dumps"
                    text: root.t("Conserva i dump se devi diagnosticare un arresto anomalo.",
                                 "Keep dumps if you need to diagnose a crash.")
                }
                Caption {
                    Layout.leftMargin: root.theme.spacing * 3
                    Layout.fillWidth: true
                    visible: text.length > 0
                    font.pixelSize: Math.max(12, root.theme.fontSmall)
                    color: root.theme.textMuted
                    wrapMode: Text.WrapAnywhere
                    text: (modelData.samples || []).join("\n") +
                          (modelData.skipped ? "\n" + modelData.skipped + root.t(" ignorati", " skipped") : "")
                }
            }
        }
        ActionButton {
            visible: root.result.categories !== undefined
            enabled: root.selected.length > 0 && !deepCleanupService.busy
            text: root.t("Rivedi selezione", "Review selection") + " (" + root.selected.length + ")"
            onClicked: deepCleanupService.prepare(root.selected.join(","))
        }
        Repeater {
            model: deepCleanupService.outcomes
            delegate: Caption {
                required property var modelData
                Layout.fillWidth: true
                text: root.label(modelData.id) + " · " + root.outcome(modelData.status) +
                      (typeof modelData.count === "number" ? " · " + modelData.count + root.t(" file · ", " files · ") + root.sizeText(modelData.bytes) : "") +
                      (modelData.skipped ? " · " + modelData.skipped + root.t(" ignorati", " skipped") : "")
            }
        }
    }
}
