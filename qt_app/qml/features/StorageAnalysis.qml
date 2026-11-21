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
    readonly property var result: storageService.data
    readonly property string selection: scope.currentIndex > 0 ? scope.currentText : "profile"
    Component.onCompleted: storageService.loadDrives()
    function status(code) {
        const states = {completed: t("Completata", "Complete"), partial: t("Parziale", "Partial"),
            cancelled: t("Annullata", "Cancelled"), entry_limit: t("Limite di elementi raggiunto", "Entry limit reached"),
            time_limit: t("Limite di tempo raggiunto", "Time limit reached"), unavailable: t("Non disponibile", "Unavailable")}
        return states[code] || ""
    }
    ColumnLayout {
        id: content
        x: root.theme.spacing
        y: root.theme.spacing
        width: Math.max(0, root.width - 2 * root.theme.spacing)
        spacing: root.theme.spacing
        Caption {
            Layout.fillWidth: true
            text: root.t("Analisi spazio", "Storage analysis")
            font.pixelSize: Math.max(12, root.theme.fontTitle)
            font.bold: true
            Accessible.role: Accessible.Heading
        }
        RowLayout {
            Layout.fillWidth: true
            ComboBox {
                id: scope
                Layout.fillWidth: true
                model: [root.t("Profilo utente", "User profile")].concat(storageService.drives)
                enabled: !storageService.busy
                focusPolicy: Qt.StrongFocus
                Accessible.role: Accessible.ComboBox
                Accessible.name: root.t("Posizione da analizzare", "Location to scan")
                font.family: root.theme.fontFamily
                font.pixelSize: Math.max(12, root.theme.fontBody)
                palette.button: root.theme.surfaceAlt
                palette.buttonText: root.theme.text
                palette.highlight: root.theme.focus
                contentItem: Caption {
                    text: scope.displayText
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                    wrapMode: Text.NoWrap
                }
            }
            ActionButton {
                enabled: !storageService.busy
                text: root.t("Analizza", "Scan")
                onClicked: storageService.scan(root.selection, false)
            }
            ActionButton {
                visible: storageService.busy || root.result.selection === root.selection
                text: storageService.busy ? root.t("Annulla", "Cancel") : root.t("Ripeti", "Rescan")
                onClicked: {
                    if (storageService.busy) storageService.cancel()
                    else storageService.scan(root.selection, true)
                }
            }
        }
        Caption {
            Layout.fillWidth: true
            color: root.theme.textMuted
            text: storageService.busy ? root.t("Elementi esaminati · ", "Entries scanned · ") + storageService.visited :
                  root.result.status ? root.status(root.result.status) + " · " + (root.result.entries || 0) + root.t(" esaminati", " scanned") +
                  (root.result.cached ? root.t(" · dalla cache di sessione", " · session cache") : "") +
                  (root.result.skipped ? " · " + root.result.skipped + root.t(" illeggibili", " unreadable") : "") +
                  (root.result.reparse_points ? " · " + root.result.reparse_points + root.t(" collegamenti esclusi", " links excluded") : "") :
                  root.t("Sola lettura · massimo 100.000 elementi o 15 secondi.", "Read-only · up to 100,000 entries or 15 seconds.")
        }
        Caption {
            visible: storageService.openError
            text: root.t("Elemento non disponibile. Ripeti l’analisi.", "Item unavailable. Run the scan again.")
            color: root.theme.warning
        }
        Repeater {
            model: root.result.selection === root.selection ? ["folders", "files"] : []
            delegate: ColumnLayout {
                required property string modelData
                Layout.fillWidth: true
                Caption {
                    Layout.fillWidth: true
                    font.bold: true
                    text: modelData === "folders" ? root.t("Cartelle più grandi · livelli 1–3", "Largest folders · levels 1–3") :
                                                   root.t("File da 100 MB in su", "Files of 100 MB or more")
                }
                Repeater {
                    model: root.result[modelData] || []
                    delegate: RowLayout {
                        required property var modelData
                        Layout.fillWidth: true
                        Caption {
                            Layout.fillWidth: true
                            wrapMode: Text.WrapAnywhere
                            text: modelData.path + " · " + root.sizeText(modelData.bytes)
                        }
                        ActionButton {
                            text: root.t("Mostra in Esplora file", "Show in Explorer")
                            enabled: !storageService.busy && root.result.status !== "cancelled"
                            Accessible.name: text + " " + modelData.path
                            onClicked: storageService.openItem(modelData.path)
                        }
                    }
                }
            }
        }
    }
}
