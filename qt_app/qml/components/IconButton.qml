import QtQuick
import QtQuick.Controls.Basic

AppButton {
    id: control
    display: AbstractButton.IconOnly
    variant: "ghost"
    implicitWidth: 40
    implicitHeight: 40
    ToolTip.delay: 500
    ToolTip.visible: hovered && text.length > 0
    ToolTip.text: text
}
