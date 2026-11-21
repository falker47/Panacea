import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Button {
    id: control
    property string variant: "secondary"
    property string glyph: icon.name
    property bool loading: false
    readonly property bool iconOnly: display === AbstractButton.IconOnly
    readonly property color ink: !enabled ? Theme.textMuted
            : variant === "primary" ? Theme.onAccent
            : variant === "danger" && !Theme.highContrast ? Theme.onAccent : Theme.text
    readonly property color fill: !enabled ? Theme.surfaceAlt
            : variant === "primary" ? Theme.accent
            : variant === "danger" && !Theme.highContrast ? Theme.danger
            : variant === "ghost" ? Theme.bg : Theme.surfaceAlt

    enabled: !loading
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus
    leftPadding: iconOnly ? 8 : 16
    rightPadding: leftPadding
    topPadding: 8
    bottomPadding: 8
    implicitWidth: Math.max(40, implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(36, implicitContentHeight + topPadding + bottomPadding)
    font.family: Theme.fontFamily
    font.pixelSize: Theme.fontBody
    font.weight: Font.DemiBold
    Accessible.name: text
    Accessible.description: loading ? Theme.tr("controls.loading") : ""
    Accessible.onPressAction: if (control.enabled && !control.loading) control.click()
    Keys.onPressed: function(event) {
        if (event.key !== Qt.Key_Return && event.key !== Qt.Key_Enter) return
        event.accepted = true
        if (!event.isAutoRepeat && control.enabled && !control.loading) control.click()
    }

    background: Rectangle {
        radius: Theme.radiusS
        color: {
            if (control.down) return Theme.wash(control.ink, 0.15, control.fill)
            if (control.hovered && control.enabled) return Theme.wash(control.ink, 0.08, control.fill)
            return control.variant === "ghost" && control.enabled ? "transparent" : control.fill
        }
        border.width: Theme.highContrast || control.variant === "secondary" ? 1 : 0
        border.color: control.variant === "danger" ? Theme.danger : Theme.controlBorder
        FocusRing { control: control }
    }

    contentItem: RowLayout {
        spacing: (control.glyph || control.loading) && !control.iconOnly ? 8 : 0
        Item { Layout.fillWidth: true; implicitWidth: 0 }
        Image {
            objectName: "buttonGlyph"
            visible: control.loading || control.glyph.length > 0
            Layout.preferredWidth: 18
            Layout.preferredHeight: 18
            source: Theme.icon(control.loading ? "updates" : control.glyph, control.ink)
            fillMode: Image.PreserveAspectFit
            Accessible.ignored: true
            RotationAnimator on rotation {
                from: 0
                to: 360
                duration: 1200
                loops: Animation.Infinite
                running: control.loading && !Theme.reducedMotion && control.visible
            }
        }
        BodyText {
            visible: !control.iconOnly
            text: control.text
            font: control.font
            color: control.ink
            horizontalAlignment: Text.AlignHCenter
            Accessible.ignored: true
        }
        Item { Layout.fillWidth: true; implicitWidth: 0 }
    }
}
