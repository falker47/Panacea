import QtQuick
import QtQuick.Layouts
import "../components"

Card {
    id: card
    required property var page
    required property string metric
    required property string caption
    required property var reading
    property var samples: []
    property color ink: Theme.info
    readonly property real percent: {
        if (typeof reading !== "number" && (typeof reading !== "string" || !reading.endsWith("%"))) return -1
        const value = typeof reading === "number" ? reading : Number(reading.slice(0, -1))
        return isFinite(value) && value >= 0 && value <= 100 ? value : -1
    }
    objectName: "metric_" + metric
    Layout.fillWidth: true
    Layout.fillHeight: true
    Layout.minimumWidth: 0
    Layout.preferredWidth: 1
    RowLayout {
        Layout.fillWidth: true
        spacing: Theme.spacing
        Image {
            source: Theme.icon(card.metric === "ram" ? "memory" : card.metric, card.ink)
            sourceSize: Qt.size(20, 20)
            Layout.preferredWidth: 20
            Layout.preferredHeight: 20
            Accessible.ignored: true
        }
        BodyText {
            Layout.fillWidth: true
            text: Theme.tr("pages.metric." + card.metric)
            font.pixelSize: Theme.fontLabel
            font.weight: Font.DemiBold
        }
    }
    BodyText {
        Layout.fillWidth: true
        objectName: "value_" + card.metric
        text: card.percent < 0 ? Theme.tr("pages.noReading")
                               : Theme.tr("pages.percent", {value: card.page.number(card.percent, 1)})
        color: card.percent < 0 ? Theme.textMuted : Theme.text
        font.pixelSize: card.percent < 0 ? Theme.fontBody : Theme.fontDisplay
        font.weight: Font.DemiBold
        tabular: true
    }
    Canvas {
        id: chart
        objectName: "metric_graph_" + card.metric
        visible: card.metric !== "disk"
        Layout.fillWidth: true
        Layout.preferredHeight: 32
        readonly property var history: card.samples || []
        readonly property color line: card.ink
        readonly property color guide: Theme.border
        readonly property bool highContrast: Theme.highContrast
        onHistoryChanged: requestPaint()
        onLineChanged: requestPaint()
        onGuideChanged: requestPaint()
        onHighContrastChanged: requestPaint()
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        Accessible.role: Accessible.Graphic
        Accessible.name: Theme.tr("pages.sampleHistory", {count: card.page.number(history.length, 0)})
        onPaint: {
            const ctx = getContext("2d")
            ctx.clearRect(0, 0, width, height)
            ctx.strokeStyle = guide
            ctx.lineWidth = 1
            for (let level = 25; level <= 75; level += 25) {
                const y = Math.round(height * level / 100) + 0.5
                ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(width, y); ctx.stroke()
            }
            const points = history.slice(-60)
            if (!points.length) return
            // Reserve all sixty time slots. Only measured samples get a line or a fill.
            const firstX = (60 - points.length) * (width - 2) / 59 + 1
            ctx.beginPath()
            for (let i = 0; i < points.length; ++i) {
                const x = firstX + i * (width - 2) / 59
                const y = (1 - points[i] / 100) * (height - 4) + 2
                if (i === 0) ctx.moveTo(x, y)
                else ctx.lineTo(x, y)
                if (points.length === 1) { ctx.arc(x, y, 2, 0, Math.PI * 2); ctx.fillStyle = line; ctx.fill(); return }
            }
            ctx.strokeStyle = line
            ctx.lineWidth = 2
            ctx.stroke()
            if (!highContrast) {
                ctx.lineTo(width - 1, height)
                ctx.lineTo(firstX, height)
                ctx.closePath()
                ctx.save(); ctx.globalAlpha = 0.16; ctx.fillStyle = line; ctx.fill(); ctx.restore()
            }
        }
    }
    Item {
        visible: card.metric === "disk"
        Layout.fillWidth: true
        Layout.preferredHeight: 32
        Rectangle {
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width
            height: 8
            radius: 4
            color: Theme.surfaceAlt
            border.color: Theme.border
            Rectangle {
                width: parent.width * Math.max(0, card.percent) / 100
                height: parent.height
                radius: parent.radius
                color: card.ink
            }
        }
    }
    BodyText {
        Layout.fillWidth: true
        text: card.caption
        font.pixelSize: Theme.fontSmall
        color: Theme.textMuted
    }
}
