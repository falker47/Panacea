import QtQuick
import QtQuick.Layouts
import "../components"

ColumnLayout {
    id: home
    required property var page
    readonly property var hardware: page.snapshots.hardware || ({})
    readonly property var updates: page.snapshots.windows_updates || ({})
    readonly property var details: liveMetrics.details || ({})
    readonly property bool hasDisk: capacity("disk") !== null
    readonly property bool spaceLow: hasDisk && details.disk[2] >= 90
    spacing: Theme.spacing * 2
    function hardwareText(value) {
        return value && !/^(Non disponibile|Unavailable|Unknown.*|N\/A)$/i.test(value)
               ? value : Theme.tr("pages.noReading")
    }
    function memoryModel() {
        const raw = hardware.ram_info || ""
        const match = /^(.*?) @ (.*?) \((\d+) modules?\)$/.exec(raw)
        if (!match) return hardwareText(raw)
        const unknown = Theme.tr("pages.noReading")
        const type = match[1] === "Mixed types" ? Theme.tr("pages.mixedTypes")
                     : match[1] === "Unknown type" ? unknown : match[1]
        const speed = match[2] === "Mixed speeds" ? Theme.tr("pages.mixedSpeeds")
                      : match[2] === "Unknown speed" ? unknown : match[2]
        return Theme.tr("pages.memoryModules", {type: type, speed: speed, count: page.number(Number(match[3]), 0)})
    }
    function capacity(key) {
        const data = details[key]
        return data && data.length >= 3 && typeof data[0] === "number" && typeof data[1] === "number"
               && typeof data[2] === "number" && data[0] > 0 && data[1] >= 0 && data[1] <= data[0]
               ? data : null
    }
    function capacityText(key) {
        const data = capacity(key)
        return data ? Theme.tr(key === "ram" ? "pages.ramCapacity" : "pages.diskCapacity",
                               {amount: page.number(key === "ram" ? data[0] - data[1] : data[1], 1),
                                total: page.number(data[0], 1)}) : Theme.tr("pages.capacityUnavailable")
    }
    function powerText() {
        const states = {"Charging": "charging", "Plugged In": "plugged", "On Battery": "battery"}
        const name = states[details.power]
        if (!name) return Theme.tr("pages.noReading")
        const label = Theme.tr("pages.power." + name)
        return typeof details.battery === "number" ? Theme.tr("pages.charge", {
            value: page.number(details.battery, 0), state: label
        }) : label
    }
    function uptimeText() {
        const parts = /^(\d+)d (\d+)h (\d+)m$/.exec(details.uptime || "")
        if (!parts) return Theme.tr("pages.noReading")
        return Theme.tr("pages.uptime", {
            days: page.number(Number(parts[1]), 0), hours: page.number(Number(parts[2]), 0),
            minutes: page.number(Number(parts[3]), 0)
        })
    }
    GridLayout {
        Layout.fillWidth: true
        columns: width < 560 ? 1 : 3
        columnSpacing: Theme.spacing
        rowSpacing: Theme.spacing
        MetricCard {
            page: home.page; metric: "cpu"; reading: liveMetrics.cpu
            samples: liveMetrics.cpuHistory; caption: home.hardwareText(home.hardware.cpu_name)
        }
        MetricCard {
            page: home.page; metric: "ram"; reading: liveMetrics.ram
            samples: liveMetrics.ramHistory; ink: Theme.accent; caption: home.capacityText("ram")
        }
        MetricCard {
            page: home.page; metric: "disk"; reading: liveMetrics.disk
            ink: home.spaceLow ? Theme.warning : Theme.info; caption: home.capacityText("disk")
        }
    }
    FeatureSlot {
        Layout.fillWidth: true
        name: "HealthCheck"
        onNavigateRequested: section => home.page.navigateRequested(section)
    }
    Card {
        Layout.fillWidth: true
        CatalogAction {
            Layout.fillWidth: true
            page: home.page; actionId: "quick_cleanup"; glyph: "cleanup"
            text: Theme.tr(home.spaceLow ? "pages.recommendCleanup" : "action.quick_cleanup.title")
            description: Theme.tr(home.spaceLow ? "pages.recommendCleanupHint" : "pages.quickDescription")
        }
    }
    GridLayout {
        Layout.fillWidth: true
        columns: width >= 810 ? 2 : 1
        columnSpacing: Theme.spacing * 2
        rowSpacing: Theme.spacing * 2
        Card {
            Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.preferredWidth: 1; Layout.alignment: Qt.AlignTop
            RowLayout {
                Layout.fillWidth: true
                SectionHeader { Layout.fillWidth: true; title: Theme.tr("pages.windowsUpdate") }
                IconButton {
                    text: Theme.tr("pages.refreshWindows")
                    glyph: "refresh-cw"
                    enabled: !home.page.occupied
                    onClicked: readService.request("windows_updates")
                }
            }
            StatusBadge {
                tone: !home.updates.verified ? "neutral" : home.updates.recommended > 0 ? "warning" : "success"
                text: !home.updates.verified ? Theme.tr("pages.updateUnverified")
                      : home.updates.recommended === 0 && home.updates.optional === 0 ? Theme.tr("pages.windowsCurrent")
                      : Theme.tr("pages.updateCount", {recommended: home.page.number(home.updates.recommended, 0),
                                                      optional: home.page.number(home.updates.optional, 0)})
            }
            CatalogAction { Layout.fillWidth: true; page: home.page; actionId: "windows_update"; glyph: "windows" }
            CatalogAction { Layout.fillWidth: true; page: home.page; actionId: "windows_optional"; glyph: "download" }
        }
        Card {
            Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.preferredWidth: 1; Layout.alignment: Qt.AlignTop
            RowLayout {
                Layout.fillWidth: true
                SectionHeader { Layout.fillWidth: true; title: Theme.tr("pages.device") }
                IconButton {
                    text: Theme.tr("pages.refreshHardware")
                    glyph: "refresh-cw"
                    enabled: !home.page.occupied
                    onClicked: readService.request("hardware")
                }
            }
            BodyText {
                Layout.fillWidth: true
                objectName: "systemVersion"
                text: home.hardwareText(home.hardware.os)
                font.pixelSize: Theme.fontTitle
                font.weight: Font.DemiBold
            }
            BodyText {
                Layout.fillWidth: true; color: Theme.textMuted
                text: Theme.tr("pages.deviceStatus", {power: home.powerText(), uptime: home.uptimeText()})
            }
            BodyText {
                Layout.fillWidth: true; color: Theme.textMuted
                text: Theme.tr("pages.deviceHardware", {memory: home.memoryModel(),
                                                        storage: home.hardwareText(home.hardware.disk_model)})
            }
            CatalogAction { Layout.fillWidth: true; page: home.page; actionId: "restore_point"; glyph: "restore" }
        }
    }
}
