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

    readonly property var stateInfo: reliabilityService.guardState
    readonly property string code: stateInfo.code || "clear"
    property string nonce: ""
    property bool preview: false
    visible: code !== "clear" || reliabilityService.previousCrash
    implicitHeight: visible ? content.implicitHeight + 2 * theme.spacing : 0
    implicitWidth: 560
    function explanation() {
        switch (code) {
        case "unknown_completion_same_boot":
            return t("L’ultimo comando potrebbe essere ancora attivo. Riavvia Windows e verifica di nuovo.", "The last command may still be running. Restart Windows, then verify again.")
        case "unknown_completion_previous_boot":
            return t("Panacea ha verificato un riavvio di Windows. Verifica di nuovo per archiviare i dati precedenti.", "Panacea verified a later Windows boot. Verify again to retire the earlier records.")
        case "interrupted_journal":
            return t("Il registro contiene un’operazione interrotta. Riavvia Windows e verifica di nuovo, oppure esamina l’archiviazione.", "The journal contains an interrupted operation. Restart Windows and verify again, or review the archive option.")
        case "unverifiable_storage":
            return t("Panacea non riesce a verificare il registro. Controlla l’accesso alla cartella dei dati e verifica di nuovo.", "Panacea cannot verify its records. Check access to its data folder, then verify again.")
        case "busy_other_instance":
            return t("Un’altra istanza sta eseguendo la manutenzione. Attendi che finisca, poi verifica di nuovo.", "Another instance is running maintenance. Wait for it to finish, then verify again.")
        default: return ""
        }
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

    Rectangle {
        anchors.fill: parent
        radius: root.theme.radiusM
        color: root.theme.surface
        border.color: root.theme.warning
    }
    ColumnLayout {
        id: content
        x: 2 * root.theme.spacing
        y: root.theme.spacing
        width: Math.max(0, parent.width - 2 * x)
        spacing: root.theme.spacing
        BodyText {
            Layout.fillWidth: true
            font.bold: true
            font.pixelSize: Math.max(12, root.theme.fontLabel)
            text: root.code === "clear" ? root.t("Arresto imprevisto", "Unexpected shutdown")
                                        : root.t("Recupero manutenzione", "Maintenance recovery")
        }
        BodyText {
            Layout.fillWidth: true
            visible: root.code !== "clear"
            text: root.explanation()
        }
        BodyText {
            Layout.fillWidth: true
            visible: reliabilityService.previousCrash
            text: root.t("Panacea ha registrato un errore nella sessione precedente. Puoi esportare la diagnostica.",
                         "Panacea recorded a crash in the previous session. You can export diagnostics.")
        }
        Flow {
            Layout.fillWidth: true
            spacing: root.theme.spacing
            ActionButton {
                visible: root.code !== "clear"
                text: root.t("Verifica di nuovo", "Verify again")
                enabled: !reliabilityService.busy
                onClicked: reliabilityService.verifyAgain()
            }
            ActionButton {
                visible: root.code === "interrupted_journal" || root.code === "unverifiable_storage"
                text: root.t("Archivia e sblocca", "Archive and unblock")
                enabled: !reliabilityService.busy && !root.nonce
                onClicked: { root.preview = false; root.nonce = reliabilityService.prepareArchive() }
            }
            ActionButton {
                text: root.t("Esporta diagnostica", "Export diagnostics")
                enabled: !reliabilityService.busy
                onClicked: { reliabilityService.cancelArchive(); root.nonce = ""; root.preview = !root.preview }
            }
            ActionButton {
                visible: reliabilityService.previousCrash
                text: root.t("Ignora avviso di arresto", "Dismiss crash notice")
                onClicked: reliabilityService.dismissCrash()
            }
        }
        BodyText {
            Layout.fillWidth: true
            visible: root.nonce.length > 0
            color: root.theme.warning
            text: root.t("Un comando precedente potrebbe essere ancora attivo. Ripetere la manutenzione potrebbe danneggiare Windows. I registri di Panacea verranno conservati e il blocco rimosso. Confermi?",
                         "An earlier command may still be running. Repeating maintenance could damage Windows. Panacea will preserve its records and release the block. Continue?")
        }
        Flow {
            Layout.fillWidth: true
            visible: root.nonce.length > 0
            spacing: root.theme.spacing
            ActionButton {
                text: root.t("Annulla", "Cancel")
                onClicked: { reliabilityService.cancelArchive(); root.nonce = "" }
            }
            ActionButton {
                objectName: "confirmArchive"
                text: root.t("Conferma archiviazione", "Confirm archive")
                onClicked: { reliabilityService.confirmArchive(root.nonce); root.nonce = "" }
            }
        }
        BodyText {
            Layout.fillWidth: true
            visible: root.preview
            text: root.t("File inclusi in Download", "Files included in Downloads") + "\n"
                  + reliabilityService.diagnosticFiles.join(", ")
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
    }
    onCodeChanged: { if (nonce) { reliabilityService.cancelArchive(); nonce = "" } }
    Component.onDestruction: { if (nonce && typeof reliabilityService !== "undefined" && reliabilityService) reliabilityService.cancelArchive() }
}
