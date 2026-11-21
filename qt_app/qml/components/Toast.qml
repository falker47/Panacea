import QtQuick
import QtQuick.Controls.Basic

Popup {
    id: toast
    property string text
    property string tone: "info"
    parent: Overlay.overlay
    x: parent ? (parent.width - width) / 2 : 0
    y: parent ? Math.max(0, parent.height - height - 24) : 0
    width: Math.min(implicitWidth, parent ? Math.max(0, parent.width - 32) : implicitWidth)
    padding: 12
    modal: false
    focus: false
    closePolicy: Popup.NoAutoClose
    function present(message, kind) {
        text = message
        tone = kind || "info"
        open()
        closeTimer.restart()
        status.Accessible.announce(text, Accessible.Polite)
    }
    onOpened: closeTimer.restart()
    Timer { id: closeTimer; interval: 5500; onTriggered: toast.close() }
    background: Rectangle {
        radius: Theme.radiusS
        color: Theme.surfaceAlt
        border.color: Theme.controlBorder
    }
    contentItem: StatusBadge {
        id: status
        text: toast.text
        tone: toast.tone
    }
}
