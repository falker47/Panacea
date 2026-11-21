import QtQuick
import "../components"

ActionRow {
    id: row
    required property var page
    required property string actionId
    objectName: "action_" + actionId
    readonly property var result: maintenanceService.results[actionId] || ({})
    text: Theme.tr("action." + actionId + ".title")
    description: Theme.tr("action." + actionId + ".description")
    status: page.statusText(result.status)
    tone: page.toneFor(result.status)
    enabled: page.canPrepare(actionId)
    onClicked: page.prepareAction(actionId)
}
