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
    readonly property var result: startupService.data
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
                text: root.t("App all’avvio", "Startup apps")
                font.pixelSize: Math.max(12, root.theme.fontTitle)
                font.bold: true
                Accessible.role: Accessible.Heading
            }
            ActionButton {
                text: root.t("Carica elenco", "Load apps")
                enabled: !startupService.busy
                onClicked: startupService.refresh()
            }
        }
        Caption {
            Layout.fillWidth: true
            visible: text.length > 0
            color: root.theme.textMuted
            text: startupService.busy ? root.t("Lettura in corso…", "Reading…") :
                  root.result.error ? root.t("Elenco non disponibile.", "Inventory unavailable.") :
                  (root.result.issues || []).length ? root.t("Alcune origini non sono leggibili.", "Some sources could not be read.") :
                  root.result.apps !== undefined ? root.result.apps.length + root.t(" elementi", " entries") : ""
        }
        Repeater {
            model: root.result.apps || []
            delegate: RowLayout {
                required property var modelData
                Layout.fillWidth: true
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2
                    Caption {
                        Layout.fillWidth: true
                        font.bold: true
                        text: modelData.display_name
                    }
                    Caption {
                        Layout.fillWidth: true
                        color: root.theme.textMuted
                        text: (modelData.scope === "user" ? root.t("Questo utente", "Current user") : root.t("Tutti gli utenti", "All users")) +
                              " · " + modelData.location + " · " +
                              (modelData.enabled === true ? root.t("Abilitata", "Enabled") :
                               modelData.enabled === false ? root.t("Disabilitata", "Disabled") : root.t("Stato sconosciuto", "Unknown state"))
                    }
                    Caption {
                        Layout.fillWidth: true
                        text: [modelData.publisher, modelData.description].filter(Boolean).join(" · ")
                        visible: text.length > 0
                    }
                    Caption {
                        Layout.fillWidth: true
                        text: modelData.command
                        font.pixelSize: Math.max(12, root.theme.fontSmall)
                        color: root.theme.textMuted
                        wrapMode: Text.WrapAnywhere
                    }
                    Caption {
                        Layout.fillWidth: true
                        text: modelData.last_changed ? root.t("Modifica · ", "Changed · ") + modelData.last_changed : ""
                        visible: text.length > 0
                        font.pixelSize: Math.max(12, root.theme.fontSmall)
                    }
                }
                ActionButton {
                    enabled: !startupService.busy && typeof modelData.enabled === "boolean"
                    text: modelData.enabled === false ? root.t("Abilita", "Enable") : root.t("Disabilita", "Disable")
                    Accessible.name: text + " " + modelData.display_name
                    onClicked: startupService.setEnabled(modelData.id, !modelData.enabled)
                }
            }
        }
    }
}
