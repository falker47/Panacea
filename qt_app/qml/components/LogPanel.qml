import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Card {
    id: panel
    property string title: Theme.tr("controls.log.title")
    property string summary
    property string details
    property bool expanded: false
    Layout.fillWidth: true

    SectionHeader {
        Layout.fillWidth: true
        title: panel.title
        visible: title.length > 0
    }
    BodyText {
        Layout.fillWidth: true
        text: panel.summary
        visible: text.length > 0
    }
    RowLayout {
        Layout.fillWidth: true
        visible: panel.details.length > 0
        spacing: 8
        AppButton {
            objectName: "toggleLogDetails"
            text: Theme.tr(panel.expanded ? "controls.log.hide" : "controls.log.show")
            glyph: panel.expanded ? "chevron-up" : "chevron-down"
            variant: "ghost"
            checkable: true
            checked: panel.expanded
            onClicked: panel.expanded = !panel.expanded
        }
        Item { Layout.fillWidth: true }
        AppButton {
            objectName: "copyLog"
            visible: panel.expanded
            text: Theme.tr("controls.log.copy")
            glyph: "copy"
            variant: "ghost"
            onClicked: {
                const first = logText.selectionStart
                const last = logText.selectionEnd
                logText.selectAll()
                logText.copy()
                logText.select(first, last)
                Accessible.announce(Theme.tr("controls.log.copied"), Accessible.Polite)
            }
        }
    }
    ScrollView {
        id: scroller
        objectName: "logScroll"
        visible: panel.expanded && panel.details.length > 0
        Layout.fillWidth: true
        Layout.preferredHeight: Math.min(224, logText.implicitHeight)
        contentWidth: availableWidth
        clip: true
        focusPolicy: Qt.NoFocus
        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
        ScrollBar.vertical: ScrollBar {
            parent: scroller
            x: scroller.width - width
            y: scroller.topPadding
            height: scroller.availableHeight
            policy: ScrollBar.AsNeeded
            focusPolicy: Qt.NoFocus
            Accessible.name: Theme.tr("controls.log.details")
        }
        TextArea {
            id: logText
            objectName: "logDetails"
            width: scroller.availableWidth
            text: panel.details
            textFormat: TextEdit.PlainText
            wrapMode: TextEdit.Wrap
            readOnly: true
            selectByMouse: true
            tabStopDistance: 32
            padding: 12
            rightPadding: 24
            activeFocusOnTab: true
            Keys.onTabPressed: (event) => nextItemInFocusChain(true).forceActiveFocus(Qt.TabFocusReason)
            Keys.onBacktabPressed: (event) => nextItemInFocusChain(false).forceActiveFocus(Qt.BacktabFocusReason)
            font.family: Theme.fontMono
            font.pixelSize: Theme.fontBody
            color: Theme.text
            selectionColor: Theme.accent
            selectedTextColor: Theme.onAccent
            Accessible.name: Theme.tr("controls.log.details")
            background: Rectangle {
                radius: Theme.radiusS
                color: Theme.bg
                border.width: logText.activeFocus ? 2 : 1
                border.color: logText.activeFocus ? Theme.focus : Theme.border
            }
        }
    }
}
