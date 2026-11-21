import QtQuick
import QtQuick.Layouts

ColumnLayout {
    id: progress
    property var steps: []
    readonly property var tones: ({
        pending: "neutral", running: "info", success: "success", failed: "danger",
        cancelled: "warning", skipped: "neutral", partial: "warning", unknown: "warning"
    })
    Layout.fillWidth: true
    spacing: 8
    Repeater {
        model: progress.steps
        RowLayout {
            id: step
            required property int index
            required property var modelData
            readonly property string phase: modelData.state in progress.tones ? modelData.state : "pending"
            objectName: "progressStep_" + index
            Layout.fillWidth: true
            spacing: 12
            BodyText {
                Layout.alignment: Qt.AlignTop
                Layout.preferredWidth: 24
                text: (step.index + 1).toString()
                tabular: true
                font.weight: Font.DemiBold
                color: Theme.textMuted
                Accessible.ignored: true
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4
                BodyText {
                    Layout.fillWidth: true
                    text: step.modelData.title
                    font.weight: Font.DemiBold
                }
                BodyText {
                    Layout.fillWidth: true
                    visible: text.length > 0
                    text: step.modelData.description || ""
                    color: Theme.textMuted
                }
            }
            StatusBadge {
                Layout.alignment: Qt.AlignTop
                text: Theme.tr("controls.step." + step.phase)
                tone: progress.tones[step.phase]
                glyph: step.phase === "running" ? "activity" : Theme.toneGlyph(tone)
            }
        }
    }
}
