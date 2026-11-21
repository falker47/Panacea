import QtQuick
import QtQuick.Layouts
import "../components"

ColumnLayout {
    id: sequence
    required property var page
    required property string action
    required property var operations
    readonly property var result: maintenanceService.results[action] || ({})
    readonly property var reported: result.steps || []
    readonly property bool running: maintenanceService.busy && maintenanceService.lastAction === action
    readonly property string outcome: result.status || (running ? "running" : "")
    readonly property var rows: operations.map(function(key, index) {
        const row = reported[index]
        let state = "pending"
        if (row) state = row.success === true ? "success" : row.success === false ? "failed" : "unknown"
        else if (running && result.done === index) state = "running"
        else if (outcome === "cancelled" || outcome === "failed" || outcome === "partial") state = "skipped"
        else if (outcome === "unknown" || outcome === "completed") state = "unknown"
        return {title: Theme.tr("action." + key + ".title"), state: state,
                description: Theme.tr("pages.step." + key)}
    })
    spacing: Theme.spacing
    RowLayout {
        Layout.fillWidth: true
        SectionHeader { Layout.fillWidth: true; title: Theme.tr("pages.sequenceSteps") }
        StatusBadge {
            visible: !!sequence.outcome
            text: sequence.page.statusText(sequence.outcome)
            tone: sequence.page.toneFor(sequence.outcome)
        }
    }
    BodyText {
        visible: !!sequence.outcome
        Layout.fillWidth: true
        objectName: "sequenceProgress_" + sequence.action
        text: Theme.tr("pages.completedSteps", {done: sequence.page.number(sequence.reported.length, 0),
                                               count: sequence.page.number(sequence.operations.length, 0)})
        color: Theme.textMuted
    }
    ProgressSteps { Layout.fillWidth: true; objectName: "steps_" + sequence.action; steps: sequence.rows }
    LogPanel {
        Layout.fillWidth: true
        visible: details.length > 0
        title: Theme.tr("pages.stepMessages")
        summary: Theme.tr("pages.stepMessagesHint")
        details: sequence.reported.map(function(row, index) {
            if (!row.message || index >= sequence.rows.length) return ""
            return sequence.rows[index].title + "\n" + row.message
        }).filter(Boolean).join("\n\n")
    }
}
