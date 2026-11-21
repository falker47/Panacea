import QtQuick
import QtQuick.Layouts
import "../components"

ColumnLayout {
    id: settings
    required property var page
    spacing: Theme.spacing * 2
    Card {
        Layout.fillWidth: true
        SectionHeader { Layout.fillWidth: true; title: Theme.tr("pages.preferences") }
        RowLayout {
            Layout.fillWidth: true
            BodyText { Layout.fillWidth: true; text: Theme.tr("pages.language"); font.weight: Font.DemiBold }
            ChoiceBox {
                id: language
                objectName: "languageChoice"
                label: Theme.tr("pages.language")
                readonly property var choices: ["system", "it", "en"]
                model: [Theme.tr("pages.languageSystem"), Theme.tr("pages.languageItalian"), Theme.tr("pages.languageEnglish")]
                currentIndex: choices.indexOf(appSettings.languageChoice)
                Layout.preferredWidth: 192
                onActivated: index => {
                    appSettings.languageChoice = choices[index]
                    currentIndex = Qt.binding(function() { return language.choices.indexOf(appSettings.languageChoice) })
                }
            }
        }
        Toggle {
            Layout.fillWidth: true
            objectName: "autoCheck"
            text: Theme.tr("pages.autoCheck")
            description: Theme.tr("pages.autoCheckHint")
            checked: appSettings.autoCheck
            onToggled: {
                appSettings.autoCheck = checked
                checked = Qt.binding(function() { return appSettings.autoCheck })
            }
        }
        Toggle {
            Layout.fillWidth: true
            objectName: "reduceMotion"
            text: Theme.tr("pages.reduceMotion")
            description: Theme.tr("pages.reduceMotionHint")
            checked: appSettings.reduceMotion
            onToggled: {
                appSettings.reduceMotion = checked
                checked = Qt.binding(function() { return appSettings.reduceMotion })
            }
        }
        Toggle {
            Layout.fillWidth: true
            objectName: "sidebarCollapsed"
            text: Theme.tr("pages.collapseSidebar")
            description: Theme.tr("pages.collapseSidebarHint")
            checked: appSettings.sidebarCollapsed
            onToggled: {
                appSettings.sidebarCollapsed = checked
                checked = Qt.binding(function() { return appSettings.sidebarCollapsed })
            }
        }
    }
    Card {
        Layout.fillWidth: true
        SectionHeader { Layout.fillWidth: true; title: Theme.tr("pages.about") }
        BodyText {
            Layout.fillWidth: true; font.pixelSize: Theme.fontTitle; font.weight: Font.DemiBold
            text: Theme.tr("pages.productVersion", {version: updateService.currentVersion})
        }
        BodyText { Layout.fillWidth: true; text: Theme.tr("pages.license"); color: Theme.textMuted }
        RowLayout {
            Layout.fillWidth: true
            AppButton {
                text: Theme.tr("pages.project"); glyph: "info"
                onClicked: Qt.openUrlExternally("https://github.com/falker47/Panacea")
            }
            AppButton {
                text: Theme.tr("pages.reportIssue"); glyph: "info"
                onClicked: Qt.openUrlExternally("https://github.com/falker47/Panacea/issues")
            }
        }
        BodyText { Layout.fillWidth: true; text: Theme.tr("pages.thirdParty"); font.weight: Font.DemiBold }
        BodyText { Layout.fillWidth: true; text: Theme.tr("pages.attribution"); color: Theme.textMuted }
        AppButton {
            text: Theme.tr("pages.lucideLicense"); variant: "ghost"
            onClicked: Qt.openUrlExternally("https://github.com/falker47/Panacea/blob/main/assets/icons/lucide/LICENSE")
        }
    }
}
