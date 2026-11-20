import QtQuick
import QtQuick.Controls.Basic as Basic
import QtQuick.Layouts
import "components"

Basic.Popup {
    id: palette
    objectName: "commandPalette"
    parent: Basic.Overlay.overlay
    modal: true
    focus: true
    anchors.centerIn: parent
    width: Math.min(584, parent.width - 48)
    height: Math.min(440, parent.height - 48)
    padding: 16
    closePolicy: Basic.Popup.CloseOnEscape | Basic.Popup.CloseOnPressOutside
    signal chosen(string section, string action)
    readonly property var matches: {
        const needle = query.text.trim().toLocaleLowerCase()
        if (!needle) return paletteEntries
        function rank(entry) {
            const titles = entry.titles.map(title => title.toLocaleLowerCase())
            if (titles.includes(needle)) return 0
            if (titles.some(title => title.startsWith(needle))) return 1
            if (titles.some(title => title.includes(needle))) return 2
            return 3
        }
        return paletteEntries.filter(entry => entry.keywords.toLocaleLowerCase().includes(needle))
                             .sort((a, b) => rank(a) - rank(b))
    }
    onOpened: {
        query.clear()
        list.currentIndex = 0
        query.forceActiveFocus(Qt.ShortcutFocusReason)
    }
    function choose(index) {
        if (index < 0 || index >= matches.length)
            return
        const entry = matches[index]
        close()
        chosen(entry.section, entry.action)
    }
    background: Rectangle {
        color: Theme.surface
        border.color: Theme.controlBorder
        radius: Theme.radiusM
    }
    contentItem: ColumnLayout {
        spacing: Theme.spacing
        Basic.TextField {
            id: query
            objectName: "paletteSearch"
            Layout.fillWidth: true
            Layout.preferredHeight: 44
            leftPadding: 12
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontLabel
            color: Theme.text
            selectionColor: Theme.accent
            selectedTextColor: Theme.onAccent
            placeholderTextColor: Theme.textMuted
            placeholderText: Theme.tr("palette.search")
            Accessible.name: placeholderText
            selectByMouse: true
            background: Rectangle {
                radius: Theme.radiusS
                color: Theme.bg
                border.color: query.activeFocus ? Theme.focus : Theme.controlBorder
                border.width: query.activeFocus ? 2 : 1
            }
            onTextChanged: list.currentIndex = palette.matches.length ? 0 : -1
            onAccepted: palette.choose(list.currentIndex)
            Keys.onDownPressed: list.currentIndex = Math.min(list.count-1, list.currentIndex+1)
            Keys.onUpPressed: list.currentIndex = Math.max(0, list.currentIndex-1)
        }
        BodyText {
            visible: !list.count
            text: Theme.tr("palette.empty")
            Layout.alignment: Qt.AlignHCenter
        }
        ListView {
            id: list
            objectName: "paletteList"
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: palette.matches
            currentIndex: 0
            keyNavigationEnabled: true
            boundsBehavior: Flickable.StopAtBounds
            Basic.ScrollBar.vertical: Basic.ScrollBar { interactive: false }
            Keys.onReturnPressed: palette.choose(currentIndex)
            delegate: Basic.ItemDelegate {
                id: result
                required property var modelData
                required property int index
                width: ListView.view.width
                height: 42
                activeFocusOnTab: false
                text: Theme.tr(modelData.titleKey)
                Accessible.name: text
                background: Rectangle {
                    color: result.ListView.isCurrentItem || result.hovered ? Theme.surfaceAlt : Theme.surface
                    radius: Theme.radiusS
                    border.width: result.visualFocus ? 2 : 0
                    border.color: Theme.focus
                }
                contentItem: RowLayout {
                    spacing: 12
                    Image {
                        source: Theme.icon(result.modelData.section, Theme.textMuted)
                        sourceSize.width: 18
                        sourceSize.height: 18
                        Layout.preferredWidth: 18
                        Layout.preferredHeight: 18
                    }
                    BodyText { Layout.fillWidth: true; text: result.text; elide: Text.ElideRight; maximumLineCount: 1 }
                    BodyText {
                        visible: !!result.modelData.action
                        text: Theme.tr("nav." + result.modelData.section)
                        font.pixelSize: Theme.fontSmall
                        color: Theme.textMuted
                    }
                }
                onClicked: palette.choose(index)
            }
        }
    }
}
