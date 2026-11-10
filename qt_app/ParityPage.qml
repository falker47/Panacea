import QtQuick
import QtQuick.Layouts

// Matches the eight V2 subviews inside the five established navigation groups.
// No backend command string is assembled in QML; all changes go through the
// allowlisted, single-use confirmation broker.
Item {
    id: view
    objectName: "parityPage_" + groupIndex
    property int groupIndex: 0
    property string language: "it"
    property string selectedDrive: ""
    property bool showDriveChoices: false
    property bool showExtraDriveTools: false
    property bool showIndividualCleaning: false
    readonly property bool occupied: maintenanceService.busy || readService.busy || updateService.busy
    readonly property var snapshots: readService.results
    readonly property var hardware: snapshots.hardware || ({})
    readonly property var temp: snapshots.temp_preview || ({})
    readonly property var turbo: snapshots.turbo_status || ({})
    readonly property var drives: snapshots.drives || ({})
    readonly property var driveChoices: (drives.drives || []).map(function(row) { return row.letter })
    readonly property var guard: snapshots.guard_status || ({})
    readonly property var resurrectionResult: maintenanceService.results.resurrection || ({})
    readonly property var progressSteps: resurrectionResult.steps || (maintenanceService.lastAction === "resurrection" ? maintenanceService.steps : [])
    Component.onCompleted: {
        if (groupIndex === 2 && driveChoices.length)
            selectedDrive = driveChoices[0]
    }
    readonly property real dashboardStretch: Math.min(320, Math.max(0, (viewport.height - 14 - 510) * 1.05))
    Connections {
        target: readService
        function onChanged() {
            if (view.groupIndex !== 2) return
            var letters = view.driveChoices
            if (!letters.length) {
                view.selectedDrive = ""
                view.showDriveChoices = false
            } else if (letters.indexOf(view.selectedDrive) === -1)
                view.selectedDrive = letters[0]
        }
    }
    function t(it, en) { return readService.localizedCopy(it, en, language) }
    function request(action, drive) {
        if (!occupied)
            maintenanceService.prepare(action, drive || "")
    }
    function showRead(action) {
        if (!occupied)
            readService.request(action)
    }
    function pairedPanelWidth(total, minimum) {
        // CTk tests the canvas before the page's 18px of horizontal gutters.
        var canvasWidth = total + 18
        return canvasWidth >= 2 * minimum + 20 ? (total - 20) / 2 : total
    }
    function formatBytes(bytes) {
        if (typeof bytes !== "number" || bytes < 0) return "—"
        if (bytes >= 1073741824) return (bytes / 1073741824).toFixed(1) + " GB"
        return (bytes / 1048576).toFixed(1) + " MB"
    }
    function stateCaption(value) {
        if (value === true) return t("Attivo", "Active")
        if (value === false) return t("Inattivo", "Inactive")
        return t("Sconosciuto", "Unknown")
    }
    readonly property var metricDetails: liveMetrics.details || ({})
    function metricCapacity(key) {
        var values = metricDetails[key]
        return values && values.length === 3 && typeof values[0] === "number"
               && typeof values[1] === "number" ? values : null
    }
    function ramCapacityText() {
        var values = metricCapacity("ram")
        return values ? t((values[0] - values[1]).toFixed(1) + " GB usati / " + values[0].toFixed(1) + " GB",
                          (values[0] - values[1]).toFixed(1) + " GB used / " + values[0].toFixed(1) + " GB") : t("Memoria non disponibile", "Memory unavailable")
    }
    function diskCapacityText() {
        var values = metricCapacity("disk")
        return values ? t(values[1].toFixed(1) + " GB liberi / ",
                          values[1].toFixed(1) + " GB free / ")
                        + values[0].toFixed(1) + " GB" : t("Disco non disponibile", "Drive unavailable")
    }
    function diskAccent() {
        var d = metricCapacity("disk")
        return !d ? "#9eafc8" : d[2] >= 95 ? "#ee939a" : d[2] >= 85 ? "#e4b66d" : "#e4c579"
    }
    function powerCaption() {
        var state = metricDetails.power || "Unknown"
        var label = state === "Charging" ? t("In carica", "Charging") :
                    state === "Plugged In" ? t("Collegato", "Plugged In") :
                    state === "On Battery" ? t("A batteria", "On battery") :
                    t("Non disponibile", "Unavailable")
        return typeof metricDetails.battery === "number" ? metricDetails.battery + "% · " + label : label
    }
    function diskStateText() {
        var d = metricCapacity("disk")
        return !d ? t("Spazio non disponibile", "Space unavailable") :
               d[2] >= 90 ? t("Spazio libero insufficiente", "Low free space") :
               t("Spazio disponibile", "Space available")
    }
    function updateCaption() {
        var u = snapshots.windows_updates
        if (!u) return t("Verifica in corso…", "Checking…")
        if (!u.verified) return t("Stato non verificato", "Status unverified")
        if (u.recommended === 0 && u.optional === 0) return t("Aggiornato", "Up to date")
        return u.recommended + t(" consigliati · ", " recommended · ") + u.optional + t(" facoltativi", " optional")
    }
    function statusCaption(state) {
        var names = {running:t("In corso", "Running"), completed:t("Completato", "Completed"),
                     partial:t("Parziale", "Partial"), failed:t("Non riuscito", "Failed"),
                     cancelled:t("Annullato", "Cancelled"), unknown:t("Completamento da verificare", "Completion unverified")}
        return names[state] || state
    }
    function restartCaption() {
        var match = /^(\d+)d (\d+)h (\d+)m$/.exec(metricDetails.uptime || "")
        if (!match) return t("Ultimo riavvio · Non disponibile", "Last restart · Unavailable")
        var days = Number(match[1]), hours = Number(match[2]), minutes = Number(match[3])
        var elapsed = days > 0 ? days + t(" g ", "d ") + hours + " h" :
                      hours > 0 ? hours + " h " + minutes + " min" : minutes + " min"
        return t("Ultimo riavvio · ", "Last restart · ") + elapsed + t(" fa", " ago")
    }
    function stepCaption(index) {
        if (progressSteps.length > index) {
            return progressSteps[index].success ? t("Completato", "Completed") : t("Non riuscito", "Failed")
        }
        if (maintenanceService.busy && maintenanceService.lastAction === "resurrection"
                && resurrectionResult.done === index)
            return t("In corso", "Running")
        if (resurrectionResult.status === "cancelled" || resurrectionResult.status === "failed")
            return t("Non eseguito", "Not run")
        return t("Non avviato", "Not started")
    }
    function stepDisplay(index, fallback) {
        var names = {1:t("Cache browser", "Browser cache"), 2:t("File temporanei", "Temp files"),
                     6:t("Ottimizza unità", "Optimize drive"), 7:t("Analisi disco", "Disk scan"),
                     8:t("Integrità immagine", "Image health"), 9:t("File di sistema", "System files")}
        return names[index] || fallback
    }

    component PButton: Rectangle {
        id: button
        property string caption: ""
        property bool primary: false
        property bool interactive: true
        property bool leftAligned: false
        signal pressed()
        implicitWidth: Math.max(90, captionLabel.implicitWidth + 26)
        width: implicitWidth
        height: 34
        radius: 6
        color: interactive && buttonPointer.containsMouse ? (primary ? "#957745" : "#304561") : primary ? "#765f33" : "#1b2b44"
        border.width: 1
        border.color: activeFocus ? "#76b6e2" : primary ? "#e4c579" : "#2e415c"
        activeFocusOnTab: interactive
        Accessible.role: Accessible.Button
        Accessible.name: caption
        Accessible.description: interactive ? "" : "Unavailable while an operation is running"
        function activate() { if (interactive) pressed() }
        Keys.onReturnPressed: activate()
        Keys.onSpacePressed: activate()
        Text {
            id: captionLabel
            anchors.fill: parent
            anchors.leftMargin: 12
            anchors.rightMargin: 12
            horizontalAlignment: button.leftAligned ? Text.AlignLeft : Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            text: button.caption
            color: button.interactive ? "#f1f3f8" : "#999999"
            font.family: "Segoe UI"
            font.pixelSize: 12
            font.bold: false
        }
        MouseArea {
            id: buttonPointer
            anchors.fill: parent
            hoverEnabled: true
            enabled: button.interactive
            cursorShape: Qt.PointingHandCursor
            onClicked: button.activate()
        }
    }

    component PGroupHeader: Item {
        id: groupHeader
        property string caption: ""
        property string iconName: "dashboard"
        property string subtitle: ""
        x: view.groupIndex === 0 ? 8 : 4
        width: parent.width - x
        implicitHeight: subtitle.length ? heading.height + headerSubtitle.height : Math.max(38, heading.implicitHeight)
        height: implicitHeight
        Image {
            id: headingIcon
            y: groupHeader.subtitle.length ? 13 : 0
            width: 38
            height: 38
            source: "image://panacea-nav/" + groupHeader.iconName + "/active"
            sourceSize.width: 96
            sourceSize.height: 96
            fillMode: Image.PreserveAspectFit
            smooth: true
            Accessible.role: Accessible.Graphic
            Accessible.name: groupHeader.caption
        }
        Text {
            id: heading
            anchors.left: headingIcon.right
            anchors.right: parent.right
            anchors.leftMargin: 9
            height: groupHeader.subtitle.length ? Math.max(36, implicitHeight) : implicitHeight
            verticalAlignment: Text.AlignVCenter
            y: groupHeader.subtitle.length ? 0 : (parent.height - height) / 2
            text: groupHeader.caption
            color: "#f1f3f8"
            font.family: "Segoe UI"
            font.pixelSize: 23
            font.bold: true
            wrapMode: Text.WordWrap
        }
        Text {
            id: headerSubtitle
            x: heading.x
            y: heading.y + heading.height
            height: Math.max(28, implicitHeight)
            verticalAlignment: Text.AlignVCenter
            width: heading.width
            visible: groupHeader.subtitle.length > 0
            text: groupHeader.subtitle
            color: "#9eafc8"
            font.family: "Segoe UI"
            font.pixelSize: 12
            wrapMode: Text.WordWrap
        }
    }

    // The original V2 paired subviews are bordered, independent panels.
    component PPanel: Rectangle {
        id: panelSurface
        property string viewName: ""
        objectName: "legacyView_" + viewName
        default property alias panelContent: panelBody.data
        property alias spacing: panelBody.spacing
        width: parent.width
        implicitHeight: panelBody.implicitHeight + 28
        height: implicitHeight
        radius: 12
        color: "#1b2b44"
        border.width: 1
        border.color: "#2e415c"
        Column {
            id: panelBody
            x: 14
            y: 14
            width: Math.max(0, panelSurface.width - 28)
            spacing: 8
        }
    }

    component PSectionTitle: Text {
        x: 8
        width: parent.width - 16
        color: "#f1f3f8"
        font.family: "Segoe UI"
        font.pixelSize: 21
        font.bold: true
        wrapMode: Text.WordWrap
    }

    component PSectionHint: Text {
        x: 8
        width: parent.width - 16
        height: Math.max(implicitHeight, width < 400 ? 43 : 18)
        color: "#9eafc8"
        font.family: "Segoe UI"
        font.pixelSize: 11
        wrapMode: Text.WordWrap
    }

    component PShortcut: Rectangle {
        id: shortcut
        property string caption: ""
        property string iconName: "apps"
        property bool primary: false
        property bool interactive: true
        signal triggered()
        width: parent.width
        height: 46
        radius: 6
        color: shortcut.interactive && shortcutPointer.containsMouse ? (primary ? "#957745" : "#304561") : primary ? "#765f33" : "#1b2b44"
        border.color: activeFocus ? "#76b6e2" : primary ? "#e4c579" : "#2e415c"
        activeFocusOnTab: interactive
        Accessible.role: Accessible.Button
        Accessible.name: caption
        function activate() { if (interactive) triggered() }
        Keys.onReturnPressed: activate()
        Keys.onSpacePressed: activate()
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 12
            anchors.rightMargin: 12
            spacing: 10
            Image {
                source: "image://panacea-nav/" + shortcut.iconName + "/detail"
                sourceSize.width: 96
                sourceSize.height: 96
                Layout.preferredWidth: 23
                Layout.preferredHeight: 23
                fillMode: Image.PreserveAspectFit
                smooth: true
            }
            Text {
                text: shortcut.caption
                Layout.fillWidth: true
                color: shortcut.interactive ? "#f1f3f8" : "#999999"
                font.family: "Segoe UI"
                font.pixelSize: shortcut.primary ? 12 : 13
                font.weight: shortcut.primary ? Font.Normal : Font.DemiBold
                wrapMode: Text.WordWrap
            }
        }
        MouseArea {
            id: shortcutPointer
            anchors.fill: parent
            hoverEnabled: true
            enabled: shortcut.interactive
            cursorShape: Qt.PointingHandCursor
            onClicked: shortcut.activate()
        }
    }

    component PSectionLog: Rectangle {
        id: sectionLog
        objectName: "sectionLog_" + scope
        property string caption: ""
        property bool expanded: false
        property string scope: ""
        property bool operationWasRunning: false
        property bool readWasRunning: false
        function revealOutput() {
            expanded = true
            Qt.callLater(function() {
                var target = sectionLog.mapToItem(viewport.contentItem, 0, 0).y - 16
                viewport.contentY = Math.max(0, Math.min(Math.max(0, viewport.contentHeight - viewport.height), target))
            })
        }
        Component.onCompleted: {
            operationWasRunning = maintenanceService.busy && maintenanceService.activeSection === scope
            readWasRunning = readService.busy && scope === "cleaning" && readService.lastAction === "temp_preview"
            if (operationWasRunning || readWasRunning) revealOutput()
        }
        Connections {
            target: maintenanceService
            function onChanged() {
                var running = maintenanceService.busy && maintenanceService.activeSection === sectionLog.scope
                if (running && !sectionLog.operationWasRunning) sectionLog.revealOutput()
                sectionLog.operationWasRunning = running
            }
        }
        Connections {
            target: readService
            function onChanged() {
                var running = readService.busy && sectionLog.scope === "cleaning" && readService.lastAction === "temp_preview"
                if (running && !sectionLog.readWasRunning) sectionLog.revealOutput()
                sectionLog.readWasRunning = running
            }
        }
        width: parent.width
        height: sectionLogContent.implicitHeight + 8
        radius: 8
        color: "#142138"
        border.color: "#2e415c"
        Column {
            id: sectionLogContent
            x: 6
            y: 4
            width: parent.width - 12
            spacing: 6
            PButton {
                width: parent.width
                height: 26
                leftAligned: true
                caption: (sectionLog.expanded ? "− " : "+ ") + sectionLog.caption
                onPressed: sectionLog.expanded = !sectionLog.expanded
            }
            Flickable {
                id: logViewport
                width: parent.width
                height: sectionLog.expanded ? 160 : 0
                visible: sectionLog.expanded
                clip: true
                contentWidth: width
                contentHeight: logText.implicitHeight
                boundsBehavior: Flickable.StopAtBounds
                activeFocusOnTab: sectionLog.expanded
                Keys.onPressed: function(event) {
                    if (event.key === Qt.Key_PageDown) contentY = Math.max(0, Math.min(contentHeight - height, contentY + height))
                    else if (event.key === Qt.Key_PageUp) contentY = Math.max(0, contentY - height)
                    else if (event.key === Qt.Key_Home) contentY = 0
                    else if (event.key === Qt.Key_End) contentY = Math.max(0, contentHeight - height)
                    else return
                    event.accepted = true
                }
                TextEdit {
                    id: logText
                    width: logViewport.width
                    text: sectionLog.expanded ? (maintenanceService.sectionLogs[sectionLog.scope] || "") + "\n" + (readService.sectionLogs[sectionLog.scope] || "") : ""
                    readOnly: true
                    selectByMouse: true
                    wrapMode: TextEdit.WrapAnywhere
                    textFormat: TextEdit.PlainText
                    color: "#b7c9db"
                    font.family: "Consolas"
                    font.pixelSize: 11
                }
            }
            PButton {
                width: parent.width
                visible: sectionLog.expanded && maintenanceService.busy && maintenanceService.activeSection === sectionLog.scope
                height: visible ? 34 : 0
                caption: view.t("Annulla dopo la fase", "Cancel after current step")
                interactive: maintenanceService.busy
                onPressed: maintenanceService.cancel()
            }
        }
    }

    component PRow: Rectangle {
        id: line
        property string heading: ""
        property string hint: ""
        property string action: ""
        property string buttonText: ""
        property string drive: ""
        property bool interactive: true
        property int collapseWidth: 305
        property int buttonWidth: 105
        signal invoke(string action, string drive)
        width: parent.width
        implicitHeight: Math.max(64, rowContent.implicitHeight + 20)
        height: implicitHeight
        color: "transparent"
        border.width: 0
        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: 1
            color: "#2e415c"
            opacity: 0.7
        }
        GridLayout {
            id: rowContent
            columns: line.width - 24 < line.collapseWidth ? 1 : 2
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            anchors.leftMargin: 12
            anchors.rightMargin: 12
            columnSpacing: 10
            rowSpacing: 5
            ColumnLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: 2
                Text {
                    text: line.heading
                    Layout.fillWidth: true
                    Layout.minimumHeight: line.collapseWidth === 225 ? 26 : 19
                    color: "#f1f3f8"
                    font.family: "Segoe UI"
                    font.bold: true
                    font.pixelSize: 13
                    wrapMode: Text.WordWrap
                    maximumLineCount: 0
                }
                Text {
                    text: line.hint
                    Layout.fillWidth: true
                    Layout.minimumHeight: line.collapseWidth === 225 ? 26 : 16
                    color: "#9eafc8"
                    font.family: "Segoe UI"
                    font.pixelSize: 11
                    wrapMode: Text.WordWrap
                    maximumLineCount: 0
                }
            }
            PButton {
                caption: line.buttonText
                Layout.preferredWidth: line.buttonWidth
                interactive: line.interactive
                onPressed: line.invoke(line.action, line.drive)
            }
        }
    }

    component PToggle: Rectangle {
        id: toggle
        property bool checked: false
        property bool interactive: true
        property string caption: ""
        signal changed(bool nextValue)
        width: 36
        height: 18
        radius: 9
        color: "transparent"
        border.width: activeFocus ? 1 : 0
        border.color: "#76b6e2"
        activeFocusOnTab: interactive
        Accessible.role: Accessible.CheckBox
        Accessible.name: caption
        Accessible.checked: checked
        function activate() { if (interactive) changed(!checked) }
        Keys.onReturnPressed: activate()
        Keys.onSpacePressed: activate()
        Rectangle {
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width; height: parent.height - 6; radius: 6
            color: toggle.checked ? "#e4c579" : "#4a4d50"
        }
        Rectangle {
            x: toggle.checked ? parent.width - width : 0
            anchors.verticalCenter: parent.verticalCenter
            width: 18; height: 18; radius: 7
            color: toggle.interactive && togglePointer.containsMouse ? "#ffffff" : "#d5d9de"
            Behavior on x { NumberAnimation { duration: 130; easing.type: Easing.OutCubic } }
        }
        MouseArea {
            id: togglePointer
            anchors.fill: parent
            hoverEnabled: true
            enabled: toggle.interactive
            cursorShape: Qt.PointingHandCursor
            onClicked: toggle.activate()
        }
    }

    component PProgress: Rectangle {
        id: progress
        property real fraction: 0
        property color progressColor: "#e4c579"
        width: parent.width
        height: 9
        radius: 5
        color: "#283951"
        Rectangle {
            width: Math.max(0, Math.min(1, progress.fraction)) * parent.width
            height: parent.height
            radius: parent.radius
            color: progress.progressColor
            Behavior on width { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }
        }
    }

    component PMiniGraph: Canvas {
        id: spark
        property var points: []
        property color lineColor: "#76b6e2"
        property bool goldFill: false
        readonly property real pixelRatio: Screen.devicePixelRatio || 1
        width: parent.width
        // Tk's embedded canvas remains 50 physical pixels at scaled DPI.
        height: 50 / pixelRatio
        onPointsChanged: requestPaint()
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        onPaint: {
            var ctx = getContext("2d")
            ctx.clearRect(0, 0, width, height)

            // The original Tk graph has 60 positions, initially at 0%, and
            // subtle dotted 25/50/75% guides. Do not stretch 3 samples over
            // the entire x-axis and imply a history that was not measured.
            ctx.beginPath()
            ctx.strokeStyle = "#2e415c"
            ctx.lineWidth = 1 / pixelRatio
            for (var level = 25; level <= 75; level += 25) {
                var gy = height * (1 - level / 100)
                for (var gx = 0; gx < width; gx += 6 / pixelRatio) {
                    ctx.moveTo(gx, gy)
                    ctx.lineTo(Math.min(width, gx + 2 / pixelRatio), gy)
                }
            }
            ctx.stroke()

            var length = points ? Math.min(60, points.length) : 0
            if (length === 0) return
            var coords = []
            for (var i = 0; i < 60; i++) {
                var source = i < 60 - length ? 0 : points[points.length - 60 + i]
                var y = height * (1 - Math.max(0, Math.min(100, Number(source))) / 100)
                coords.push([i * (width - 1) / 59, y])
            }

            ctx.beginPath()
            ctx.moveTo(coords[0][0], coords[0][1])
            for (var p = 1; p < coords.length; p++)
                ctx.lineTo(coords[p][0], coords[p][1])
            ctx.lineTo(width - 1, height)
            ctx.lineTo(0, height)
            ctx.closePath()
            ctx.fillStyle = goldFill ? "#3b342b" : "#24364c"
            ctx.fill()

            ctx.beginPath()
            ctx.moveTo(coords[0][0], coords[0][1])
            // Match the legacy smoothed line; the area polygon stays linear.
            for (var j = 1; j < coords.length - 1; j++)
                ctx.quadraticCurveTo(coords[j][0], coords[j][1],
                                     (coords[j][0] + coords[j + 1][0]) / 2,
                                     (coords[j][1] + coords[j + 1][1]) / 2)
            ctx.lineTo(coords[coords.length - 1][0], coords[coords.length - 1][1])
            ctx.lineWidth = 2 / pixelRatio
            ctx.strokeStyle = lineColor
            ctx.stroke()
        }
    }

    Column {
        id: groupChrome
        x: 31; y: 23; width: parent.width - 64
        visible: view.groupIndex >= 1 && view.groupIndex <= 3
        spacing: 13
        PGroupHeader {
            caption: view.groupIndex === 1 ? view.t("Spazio e pulizia", "Space & Cleanup") :
                     view.groupIndex === 2 ? view.t("Diagnostica e riparazione", "Diagnostics & Repair") :
                     view.t("Prestazioni e avvio", "Performance & Startup")
            iconName: view.groupIndex === 1 ? "clean" : view.groupIndex === 2 ? "tools" : "turbo"
        }
        Rectangle { width: parent.width; height: 1; color: "#2e415c" }
    }

    Flickable {
        id: viewport
        objectName: "pageViewport"
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.top: groupChrome.visible ? groupChrome.bottom : parent.top
        anchors.topMargin: groupChrome.visible ? 10 : 0
        clip: true
        contentWidth: width
        contentHeight: content.implicitHeight + 42
        boundsBehavior: Flickable.StopAtBounds
        activeFocusOnTab: true
        Keys.onPressed: function(event) {
            if (event.key === Qt.Key_PageDown) contentY = Math.min(Math.max(0, contentHeight - height), contentY + height)
            else if (event.key === Qt.Key_PageUp) contentY = Math.max(0, contentY - height)
            else if (event.key === Qt.Key_Home) contentY = 0
            else if (event.key === Qt.Key_End) contentY = Math.max(0, contentHeight - height)
            else return
            event.accepted = true
        }

        Column {
            id: content
            x: view.groupIndex === 0 ? 24 : view.groupIndex === 4 ? 32 : 31
            y: view.groupIndex === 0 ? 16 : view.groupIndex === 4 ? 12 : 10
            width: Math.max(250, viewport.width - (view.groupIndex === 0 ? 58 : 64))
            spacing: 15

            Loader {
                width: parent.width
                height: item ? item.implicitHeight : 0
                sourceComponent: view.groupIndex === 0 ? dashboardSection :
                                 view.groupIndex === 1 ? cleaningAndAppsSection :
                                 view.groupIndex === 2 ? toolsAndDiskSection :
                                 view.groupIndex === 3 ? turboAndStartupSection : resurrectionSection
            }

            // QA identity is shown in the app shell, not repeated on every V2 screen.
        }
    }

    Item {
        id: pageScrollbar
        objectName: "pageScrollbar"
        anchors.right: parent.right
        anchors.rightMargin: 4
        anchors.top: viewport.top
        anchors.bottom: viewport.bottom
        anchors.topMargin: 4
        anchors.bottomMargin: 4
        width: 16
        Accessible.role: Accessible.ScrollBar
        Accessible.name: view.t("Scorri contenuto", "Scroll content")
        readonly property real maximum: Math.max(0, viewport.contentHeight - viewport.height)
        function setPosition(position, offset) {
            var travel = height - scrollThumb.height
            viewport.contentY = travel > 0 ? Math.max(0, Math.min(1, (position - offset) / travel)) * maximum : 0
        }
        Rectangle {
            id: scrollThumb
            objectName: "pageScrollThumb"
            x: 4; width: 8; radius: 4; color: "#707070"
            height: Math.max(24, Math.min(parent.height, parent.height * viewport.height / Math.max(1, viewport.contentHeight)))
            y: pageScrollbar.maximum > 0 ? Math.max(0, Math.min(1, viewport.contentY / pageScrollbar.maximum)) * (parent.height - height) : 0
        }
        MouseArea {
            anchors.fill: parent
            property real grabOffset: 0
            onPressed: function(mouse) {
                grabOffset = mouse.y >= scrollThumb.y && mouse.y <= scrollThumb.y + scrollThumb.height ? mouse.y - scrollThumb.y : scrollThumb.height / 2
                pageScrollbar.setPosition(mouse.y, grabOffset)
                viewport.forceActiveFocus()
            }
            onPositionChanged: function(mouse) { if (pressed) pageScrollbar.setPosition(mouse.y, grabOffset) }
            onWheel: function(wheel) {
                viewport.contentY = Math.max(0, Math.min(pageScrollbar.maximum, viewport.contentY - wheel.angleDelta.y / 3))
                wheel.accepted = true
            }
        }
    }

    Component {
        id: dashboardSection
        Column {
            width: parent.width
            spacing: 13
            PGroupHeader { caption: view.t("Panoramica", "Overview"); iconName: "dashboard"; height: viewport.height < 520 ? 33 : implicitHeight }
            Rectangle {
                id: overviewCard
                width: parent.width
                height: summaryFlow.implicitHeight + 14
                radius: 8
                color: "#142138"
                border.color: "#2e415c"
                Flow {
                    id: summaryFlow
                    x: 10
                    y: 7
                    width: parent.width - 20
                    spacing: 8
                    // V2 uses a uniform two-column summary at every scale.
                    readonly property bool paired: true
                    readonly property real cardHeight: Math.max(viewport.height < 520 ? 117 : 143, 108 + Math.round(view.dashboardStretch * .28))
                Rectangle {
                    width: summaryFlow.paired ? (summaryFlow.width - 8) / 2 : summaryFlow.width
                    height: summaryFlow.cardHeight; radius: 8; color: "transparent"; border.width: 0
                    Column {
                        anchors.fill: parent; anchors.margins: 14; spacing: 9
                        Row {
                            width: parent.width
                            spacing: 9
                            Image {
                                source: "image://panacea-nav/windows/detail"
                                sourceSize.width: 96
                                sourceSize.height: 96
                                width: 39; height: 39
                                fillMode: Image.PreserveAspectFit
                                smooth: true
                                Accessible.role: Accessible.Graphic
                                Accessible.name: "Windows"
                            }
                            Text {
                                objectName: "dashboardSystemTitle"
                                text: view.hardware.os || (view.hardware.error ? view.t("Dettagli Windows non disponibili", "Windows details unavailable") : view.t("Caricamento dettagli Windows…", "Loading Windows details…"))
                                textFormat: Text.PlainText
                                width: parent.width - 48
                                // The narrow 150% viewport must still show the OS version.
                                font.pixelSize: parent.width < 165 ? 16 : 20
                                font.bold: true; color: "#f1f3f8"
                                elide: Text.ElideRight
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }
                        Row {
                            width: parent.width
                            height: 34
                            spacing: 8
                            Image {
                                source: typeof view.metricDetails.battery === "number"
                                    ? "image://panacea-nav/battery-" +
                                      Math.max(0, Math.min(100, Math.round(view.metricDetails.battery / 5) * 5)) +
                                      "-" + (view.metricDetails.power === "Charging" ? "charging" :
                                             view.metricDetails.power === "Plugged In" ? "plugged" : "unplugged") +
                                      "/detail"
                                    : "image://panacea-nav/battery/detail"
                                sourceSize.width: 96; sourceSize.height: 96
                                width: 34; height: 34
                                fillMode: Image.PreserveAspectFit
                                smooth: true
                            }
                            Text {
                                text: view.powerCaption()
                                width: parent.width - 42
                                wrapMode: Text.WordWrap
                                color: view.metricDetails.power === "Charging" ? "#e4c579" : "#f1f3f8"
                                font.pixelSize: 12; font.bold: true
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }
                        Text {
                            text: view.restartCaption()
                            width: parent.width
                            color: "#9eafc8"
                            font.pixelSize: 12
                            elide: Text.ElideRight
                        }
                        Text {
                            visible: Number((view.metricDetails.uptime || "").split("d")[0]) >= 7
                            text: view.t("Riavvio consigliato", "Restart recommended")
                            color: "#e4b66d"; font.pixelSize: 11
                        }
                    }
                }
                Rectangle {
                    id: windowsUpdateCard
                    objectName: "windowsUpdateCard"
                    width: summaryFlow.paired ? (summaryFlow.width - 8) / 2 : summaryFlow.width
                    height: summaryFlow.cardHeight; radius: 8; color: "#1b2b44"; border.width: 0
                    readonly property bool compact: width < 260
                    GridLayout {
                        anchors.fill: parent; anchors.margins: 12
                        columns: 3
                        columnSpacing: 8
                        rowSpacing: 2
                        Image {
                            source: "image://panacea-nav/updates/detail"
                            sourceSize.width: 96
                            sourceSize.height: 96
                            Layout.row: 0
                            Layout.column: 0
                            Layout.rowSpan: windowsUpdateCard.compact ? 1 : 2
                            Layout.alignment: Qt.AlignVCenter
                            Layout.preferredWidth: windowsUpdateCard.compact ? 32 : 46
                            Layout.preferredHeight: windowsUpdateCard.compact ? 32 : 46
                            fillMode: Image.PreserveAspectFit
                            smooth: true
                        }
                        Text {
                            text: "Windows Update"
                            Layout.row: 0
                            Layout.column: 1
                            Layout.columnSpan: windowsUpdateCard.compact ? 2 : 1
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            wrapMode: Text.NoWrap
                            elide: Text.ElideRight
                            color: "#f1f3f8"; font.bold: true
                            font.pixelSize: windowsUpdateCard.compact ? 14 : 16
                        }
                        Text {
                            text: view.updateCaption()
                            Layout.row: 1
                            Layout.column: windowsUpdateCard.compact ? 0 : 1
                            Layout.columnSpan: windowsUpdateCard.compact ? 2 : 1
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            wrapMode: Text.NoWrap
                            elide: Text.ElideRight
                            color: view.snapshots.windows_updates && view.snapshots.windows_updates.verified ?
                                   (view.snapshots.windows_updates.recommended + view.snapshots.windows_updates.optional > 0 ? "#e4b66d" : "#78c8a8") : "#9eafc8"
                            font.pixelSize: windowsUpdateCard.compact ? 11 : 12
                        }
                        PButton {
                            caption: view.t("Apri", "View")
                            Layout.row: windowsUpdateCard.compact ? 1 : 0
                            Layout.column: 2
                            Layout.rowSpan: windowsUpdateCard.compact ? 1 : 2
                            Layout.alignment: Qt.AlignVCenter
                            Layout.preferredWidth: windowsUpdateCard.compact ? 64 : 73
                            height: windowsUpdateCard.compact ? 32 : 36
                            interactive: !view.occupied
                            onPressed: view.request("windows_update")
                        }
                    }
                }
                }
            }
            GridLayout {
                id: metricFlow
                width: parent.width
                height: implicitHeight
                columnSpacing: 10
                rowSpacing: 10
                uniformCellWidths: true
                uniformCellHeights: true
                // Match V2's fixed uniform metric grid; text wraps within cards.
                columns: 3
                readonly property real cardMinimumHeight: (viewport.height < 520 ? 196 : 183) + Math.round(view.dashboardStretch * .41)
                Repeater {
                    // Stable model: keep the Canvas and progress bar delegates alive on metric refresh.
                    model: ["cpu", "ram", "disk"]
                    Rectangle {
                        id: metricCard
                        objectName: "metricCard_" + metricId
                        readonly property string metricId: modelData
                        readonly property string metricIcon: metricId === "ram" ? "memory" : metricId === "disk" ? "drive" : "cpu"
                        readonly property string metricTitle: metricId === "ram" ? view.t("Memoria (RAM)", "Memory (RAM)")
                                                          : metricId === "disk" ? view.t("Unità di sistema", "System drive") : "CPU"
                        readonly property string metricValue: metricId === "ram" ? liveMetrics.ram : metricId === "disk" ? liveMetrics.disk : liveMetrics.cpu
                        readonly property var metricSeries: metricId === "ram" ? liveMetrics.ramHistory : metricId === "disk" ? liveMetrics.diskHistory : liveMetrics.cpuHistory
                        readonly property color metricAccent: metricId === "ram" ? "#e4c579" : metricId === "disk" ? view.diskAccent() : "#76b6e2"
                        readonly property string metricDetail: metricId === "ram" ? view.ramCapacityText() : metricId === "disk" ? view.diskCapacityText() : (view.hardware.cpu_name || "—")
                        readonly property string metricExtra: metricId === "ram" ? (view.hardware.ram_info || "") : metricId === "disk" ? (view.hardware.disk_model || "") : ""
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.minimumWidth: 0
                        Layout.preferredWidth: 0
                        implicitHeight: Math.max(metricFlow.cardMinimumHeight, metricContent.implicitHeight + 26)
                        radius: 8; color: "#142138"; border.color: "#2e415c"
                        Column {
                            id: metricContent
                            anchors.fill: parent; anchors.margins: 13; spacing: 8
                            Row {
                                width: parent.width
                                spacing: 6
                                Image {
                                    source: "image://panacea-nav/" + metricCard.metricIcon + "/detail"
                                    sourceSize.width: 96
                                    sourceSize.height: 96
                                    width: 22; height: 22
                                    fillMode: Image.PreserveAspectFit
                                    smooth: true
                                }
                                Text {
                                    text: metricCard.metricTitle
                                    width: parent.width - 28
                                    wrapMode: Text.WordWrap
                                    color: "#f1f3f8"; font.bold: true; font.pixelSize: 13
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }
                            Text { text: /%$/.test(metricCard.metricValue) ? metricCard.metricValue : "—"; color: metricCard.metricId === "disk" ? view.diskAccent() : metricCard.metricId === "ram" && parseFloat(metricCard.metricValue) >= 90 ? "#e4b66d" : "#f1f3f8"; font.bold: true; font.pixelSize: 25 }
                            PMiniGraph {
                                objectName: "metric_graph_" + metricCard.metricId
                                visible: metricCard.metricId !== "disk"
                                width: parent.width
                                height: visible ? 50 / pixelRatio : 0
                                points: metricCard.metricSeries
                                lineColor: metricCard.metricAccent
                                goldFill: metricCard.metricId === "ram"
                            }
                            PProgress {
                                visible: metricCard.metricId === "disk"
                                width: parent.width
                                height: visible ? 12 : 0
                                progressColor: view.diskAccent()
                                fraction: metricCard.metricId === "disk" ?
                                          Math.max(0, Math.min(1, (parseFloat(metricCard.metricValue) || 0) / 100)) : 0
                            }
                            Text {
                                text: metricCard.metricDetail
                                textFormat: Text.PlainText
                                width: parent.width; color: "#9eafc8"; font.pixelSize: 12
                                wrapMode: Text.WordWrap
                            }
                            Text {
                                visible: metricCard.metricId === "disk"
                                text: visible ? view.diskStateText() : ""
                                width: parent.width; color: view.diskAccent(); font.pixelSize: 11
                                wrapMode: Text.WordWrap
                            }
                            Text {
                                text: metricCard.metricExtra || ""
                                textFormat: Text.PlainText
                                width: parent.width
                                color: "#9eafc8"
                                font.pixelSize: 11
                                visible: text.length > 0
                                wrapMode: Text.WordWrap
                            }
                        }
                    }
                }
            }
            Flow {
                id: actionFlow
                width: parent.width
                spacing: 10
                Rectangle {
                    id: scanActionCard
                    width: (actionFlow.width - 10) / 2
                    readonly property bool compact: width < 230
                    height: Math.max(92 + Math.round(view.dashboardStretch * .27), scanContent.implicitHeight + 26, restoreContent.implicitHeight + 26); radius: 8; color: "#1b2b44"; border.color: "#2e415c"
                    RowLayout {
                        id: scanContent
                        anchors.fill: parent
                        anchors.margins: scanActionCard.compact ? 8 : 13
                        spacing: scanActionCard.compact ? 4 : 8
                        Image {
                            source: "image://panacea-nav/scan/detail"
                            sourceSize.width: 96
                            sourceSize.height: 96
                            Layout.preferredWidth: scanActionCard.compact ? 28 : 46
                            Layout.preferredHeight: scanActionCard.compact ? 28 : 46
                            fillMode: Image.PreserveAspectFit
                            smooth: true
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            Text { text: view.t("File temporanei","Temporary files"); Layout.fillWidth: true; wrapMode: Text.WordWrap; color: "#f1f3f8"; font.pixelSize: 14; font.bold: true }
                            Text {
                                text: view.temp.error ? view.t("Analisi non riuscita · Nessun file eliminato", "Analysis failed · No files deleted") : view.temp.no_files_deleted ? view.temp.count + " · " + view.formatBytes(view.temp.bytes)
                                      : view.t("Analisi facoltativa · Nessun file eliminato","Analysis optional · No files deleted")
                                Layout.fillWidth: true; color: "#9eafc8"; font.pixelSize: 11
                                wrapMode: Text.WordWrap
                            }
                        }
                        PButton { Layout.preferredWidth:scanActionCard.compact ? 68 : 85; caption: view.t("Analizza","Analyze"); interactive: !view.occupied; onPressed: view.showRead("temp_preview") }
                    }
                }
                Rectangle {
                    id: restoreActionCard
                    width: (actionFlow.width - 10) / 2
                    readonly property bool compact: width < 230
                    height: Math.max(92 + Math.round(view.dashboardStretch * .27), scanContent.implicitHeight + 26, restoreContent.implicitHeight + 26); radius: 8; color: "#1b2b44"; border.color: "#2e415c"
                    RowLayout {
                        id: restoreContent
                        anchors.fill: parent
                        anchors.margins: restoreActionCard.compact ? 8 : 13
                        spacing: restoreActionCard.compact ? 4 : 8
                        Image {
                            source: "image://panacea-nav/restore/detail"
                            sourceSize.width: 96
                            sourceSize.height: 96
                            Layout.preferredWidth: restoreActionCard.compact ? 28 : 46
                            Layout.preferredHeight: restoreActionCard.compact ? 28 : 46
                            fillMode: Image.PreserveAspectFit
                            smooth: true
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            Text { text: view.t("Punto di ripristino","Restore point"); Layout.fillWidth: true; wrapMode: Text.WordWrap; color: "#f1f3f8"; font.pixelSize: 14; font.bold: true }
                            Text {
                                text: view.t("Crea un punto di ripristino · conferma richiesta","Create a restore point · confirmation required")
                                color: "#9eafc8"; font.pixelSize: 11; Layout.fillWidth: true
                                wrapMode: Text.WordWrap
                            }
                        }
                        PButton { Layout.preferredWidth:restoreActionCard.compact ? 68 : 85; caption: view.t("Crea","Create"); interactive: !view.occupied; onPressed: view.request("restore_point") }
                    }
                }
            }
        }
    }

    Component {
        id: cleaningAndAppsSection
        Column {
            width: parent.width
            spacing: 16
            Flow {
                id: pair
                width: parent.width
                spacing: 20
                PPanel {
                    viewName: "cleaning"
                    width: view.pairedPanelWidth(pair.width, 300)
                    spacing: 8
                    PSectionTitle { text: view.t("Pulizia", "Cleanup") }
                    PSectionHint {
                        text: view.t("Pulizia rapida o strumenti singoli. I file protetti vengono ignorati.",
                                     "Quick cleanup or individual tools. Protected files are skipped.")
                    }
                    Rectangle {
                        width: parent.width
                        height: quickContent.implicitHeight + 24
                        radius: 8
                        color: "#142138"
                        border.color: "#2e415c"
                        Column {
                            id: quickContent
                            x: 12
                            y: 12
                            width: parent.width - 24
                            spacing: 8
                            PShortcut {
                                width: Math.min(170, parent.width)
                                x: (parent.width - width) / 2
                                height: 42
                                primary: true
                                iconName: "clean"
                                caption: view.t("Avvia pulizia rapida", "Run quick cleanup")
                                interactive: !view.occupied
                                onTriggered: view.request("quick_cleanup")
                            }
                            Text {
                                visible: maintenanceService.lastAction === "quick_cleanup" &&
                                         maintenanceService.resultStatus.length > 0
                                width: parent.width
                                text: visible ? maintenanceService.resultStatus : ""
                                color: "#9eafc8"
                                font.pixelSize: 11
                                wrapMode: Text.WordWrap
                            }
                            PProgress {
                                width: parent.width
                                visible: maintenanceService.lastAction === "quick_cleanup"
                                height: visible ? 7 : 0
                                fraction: maintenanceService.progressTotal > 0 ?
                                          maintenanceService.progressDone / maintenanceService.progressTotal : 0
                            }
                        }
                    }
                    PShortcut {
                        caption: view.showIndividualCleaning ?
                                 view.t("Nascondi strumenti individuali", "Hide individual tools") :
                                 view.t("Mostra strumenti individuali", "Show individual tools")
                        iconName: "tools"
                        height: 40
                        onTriggered: view.showIndividualCleaning = !view.showIndividualCleaning
                    }
                    Column {
                        visible: view.showIndividualCleaning
                        width: parent.width
                        spacing: 5
                        PRow { heading: view.t("File temporanei","Temporary files"); hint: view.t("Eliminazione permanente dei file idonei","Permanently delete eligible files"); action:"temp_clean"; buttonText:view.t("Pulisci","Clean"); interactive:!view.occupied; onInvoke: view.request(action,drive) }
                        PRow { heading: view.t("Cache browser","Browser caches"); hint:"Chrome, Edge, Firefox"; action:"browser_clean"; buttonText:view.t("Pulisci","Clean"); interactive:!view.occupied; onInvoke: view.request(action,drive) }
                        PRow { heading: view.t("Cestino","Recycle Bin"); hint: view.t("Svuotamento irreversibile","Irreversible deletion"); action:"recycle_empty"; buttonText:view.t("Svuota","Empty"); interactive:!view.occupied; onInvoke: view.request(action,drive) }
                        PRow { heading: view.t("Archivio componenti","Component store"); hint:"DISM StartComponentCleanup"; action:"component_cleanup"; buttonText:view.t("Esegui","Run"); interactive:!view.occupied; onInvoke: view.request(action,drive) }
                        PRow { heading: view.t("Pulizia disco","Disk Cleanup"); hint: view.t("Strumento nativo di Windows","Native Windows utility"); action:"open_cleanmgr"; buttonText:view.t("Apri","Open"); interactive:!view.occupied; onInvoke: view.request(action,drive) }
                        PButton { caption: view.t("Analizza temporanei (sola lettura)", "Preview temporary files (read-only)"); interactive:!view.occupied; onPressed:view.showRead("temp_preview") }
                        Text {
                            text: view.temp.no_files_deleted ? view.temp.count + " " + view.t("file", "files") + " · " + view.formatBytes(view.temp.bytes) + " · " + view.temp.skipped + " " + view.t("saltati", "skipped") + " · " + view.temp.errors + " " + view.t("errori", "errors") : ""
                            width: parent.width; wrapMode:Text.WordWrap; color:"#9eafc8"; font.pixelSize:11
                        }
                    }
                    PSectionLog { scope: "cleaning"; caption: view.t("Dettagli pulizia", "Cleanup details") }
                }
                PPanel {
                    viewName: "apps"
                    width: view.pairedPanelWidth(pair.width, 300)
                    spacing: 8
                    PSectionTitle { text: view.t("Applicazioni installate","Installed apps") }
                    PSectionHint {
                        text: view.t("Gestisci o disinstalla programmi dalle impostazioni Windows.",
                                     "Manage or uninstall programs in Windows.")
                    }
                    Rectangle {
                        width: parent.width
                        height: appLinks.implicitHeight + 28
                        radius: 8
                        color: "#142138"
                        border.color: "#2e415c"
                        Column {
                            id: appLinks
                            x: 14
                            y: 14
                            width: parent.width - 28
                            spacing: 8
                            PShortcut { caption: view.t("Impostazioni applicazioni", "Apps settings"); iconName: "apps"; interactive: !view.occupied; onTriggered: view.request("apps_settings") }
                            PShortcut { caption: view.t("Programmi classici", "Classic programs"); iconName: "tools"; interactive: !view.occupied; onTriggered: view.request("appwiz") }
                        }
                    }
                }
            }
        }
    }

    Component {
        id: toolsAndDiskSection
        Column {
            width: parent.width
            spacing: 16
            Flow {
                id: pair
                width: parent.width; spacing: 20
                PPanel {
                    viewName: "tools"
                    width: view.pairedPanelWidth(pair.width, 305)
                    spacing: 7
                    PSectionTitle { text: view.t("Strumenti di riparazione","Repair tools") }
                    PSectionHint {
                        text: view.t("Verifica l'integrità o ripara problemi di Windows e della rete.",
                                     "Check integrity or repair Windows and network issues.")
                    }
                    Text { text: view.t("INTEGRITÀ WINDOWS","WINDOWS INTEGRITY"); color:"#e4c579"; font.pixelSize:10; font.bold:true }
                    Rectangle {
                        width: parent.width; height: integrityRows.implicitHeight
                        radius: 8; color: "#142138"; border.color: "#2e415c"
                        Column {
                            id: integrityRows
                            width: parent.width
                            PRow { collapseWidth:225; buttonWidth:91; heading:view.t("Scansione file di sistema","System file scan"); hint:view.t("Verifica e ripara i file protetti.","Verify and repair protected files."); action:"sfc"; buttonText:view.t("Analizza","Scan"); interactive:!view.occupied; onInvoke:view.request(action,drive) }
                            PRow { collapseWidth:225; buttonWidth:91; heading:view.t("Salute immagine","Image health"); hint:view.t("Controlla i danni registrati nell'immagine di sistema.","Check the component image for recorded corruption."); action:"dism_check"; buttonText:view.t("Verifica","Check"); interactive:!view.occupied; onInvoke:view.request(action,drive) }
                            PRow { collapseWidth:225; buttonWidth:91; heading:view.t("Riparazione immagine","Repair image"); hint:view.t("Ripara i danni; può usare Windows Update.","Repair corruption; may use Windows Update."); action:"dism_restore"; buttonText:view.t("Ripara","Repair"); interactive:!view.occupied; onInvoke:view.request(action,drive) }
                        }
                    }
                    Text { text: view.t("RETE","NETWORK"); color:"#e4c579"; font.pixelSize:10; font.bold:true }
                    Rectangle {
                        width: parent.width; height: networkRows.implicitHeight
                        radius: 8; color: "#142138"; border.color: "#2e415c"
                        Column {
                            id: networkRows
                            width: parent.width
                            PRow { collapseWidth:225; buttonWidth:91; heading:view.t("Svuota DNS","Flush DNS"); hint:view.t("Cancella la cache DNS.","Clear cached DNS records."); action:"dns_flush"; buttonText:view.t("Svuota","Flush"); interactive:!view.occupied; onInvoke:view.request(action,drive) }
                            PRow { collapseWidth:225; buttonWidth:91; heading:view.t("Ripristina Winsock","Reset Winsock"); hint:view.t("Può interrompere le connessioni e richiedere un riavvio.","May interrupt connections and require a restart."); action:"winsock_reset"; buttonText:view.t("Ripristina","Reset"); interactive:!view.occupied; onInvoke:view.request(action,drive) }
                        }
                    }
                    PShortcut { caption: view.t("Crea punto di ripristino", "Create restore point"); iconName: "restore"; interactive: !view.occupied; onTriggered: view.request("restore_point") }
                    PShortcut { caption: view.t("Rapporto batteria", "Battery report"); iconName: "battery-report"; interactive: !view.occupied; onTriggered: view.request("battery_report") }
                    PSectionLog { scope: "tools"; caption: view.t("Output comandi", "Command output") }
                }
                PPanel {
                    viewName: "disk"
                    width: view.pairedPanelWidth(pair.width, 305)
                    spacing: 8
                    PSectionTitle { text: view.t("Ottimizzazione dischi","Drive optimization") }
                    PSectionHint {
                        text: view.t("Windows usa il metodo di ottimizzazione adatto a ciascuna unità.",
                                     "Windows uses the appropriate optimization method for each drive.")
                    }
                    Rectangle {
                        width: parent.width
                        height: driveSelector.implicitHeight + 24
                        radius: 8; color: "#142138"; border.color: "#2e415c"
                        Column {
                            id: driveSelector
                            x: 14; y: 12; width: parent.width - 28; spacing: 12
                            RowLayout {
                                width: parent.width; spacing: 8
                                Image {
                                    source: "image://panacea-nav/disk/detail"
                                    sourceSize.width: 96; sourceSize.height: 96
                                    Layout.preferredWidth: 28; Layout.preferredHeight: 28
                                }
                                PButton {
                                    id: drivePicker
                                    objectName: "driveSelector"
                                    Layout.preferredWidth: 112
                                    caption: (view.selectedDrive || view.t("Seleziona unità", "Select drive")) + "  ▾"
                                    interactive: !view.occupied && view.driveChoices.length > 0
                                    onPressed: view.showDriveChoices = !view.showDriveChoices
                                    Accessible.role: Accessible.ComboBox
                                    MouseArea {
                                        parent: view
                                        anchors.fill: parent
                                        z: 199
                                        visible: view.showDriveChoices
                                        onClicked: view.showDriveChoices = false
                                    }
                                    Rectangle {
                                        id: driveMenu
                                        objectName: "drivePopup"
                                        parent: view
                                        z: 200
                                        visible: view.showDriveChoices
                                        width: drivePicker.width
                                        height: Math.min(8, view.driveChoices.length) * 24 + 8
                                        property point origin: drivePicker.mapToItem(view, 0, 0)
                                        x: origin.x
                                        y: origin.y + drivePicker.height + height <= view.height ?
                                           origin.y + drivePicker.height : Math.max(0, origin.y - height)
                                        color: "#1b2b44"; radius: 6; border.color: "#2e415c"
                                        property int currentIndex: Math.max(0, view.driveChoices.indexOf(view.selectedDrive))
                                        onActiveFocusChanged: if (visible && !activeFocus) view.showDriveChoices = false
                                        function revealSelection() {
                                            if (!driveRows) return
                                            var target = driveRows.contentY
                                            if (currentIndex * 24 < target) target = currentIndex * 24
                                            if ((currentIndex + 1) * 24 > target + driveRows.height)
                                                target = (currentIndex + 1) * 24 - driveRows.height
                                            driveRows.contentY = Math.max(0, Math.min(Math.max(0, driveRows.contentHeight - driveRows.height), target))
                                        }
                                        onCurrentIndexChanged: revealSelection()
                                        onVisibleChanged: if (visible) {
                                            origin = drivePicker.mapToItem(view, 0, 0)
                                            currentIndex = Math.max(0, view.driveChoices.indexOf(view.selectedDrive))
                                            forceActiveFocus()
                                            Qt.callLater(revealSelection)
                                        }
                                        function acceptSelection() {
                                            if (!view.occupied && view.driveChoices[currentIndex])
                                                view.selectedDrive = view.driveChoices[currentIndex]
                                            view.showDriveChoices = false
                                            drivePicker.forceActiveFocus()
                                        }
                                        Keys.onDownPressed: currentIndex = Math.min(view.driveChoices.length - 1, currentIndex + 1)
                                        Keys.onUpPressed: currentIndex = Math.max(0, currentIndex - 1)
                                        Keys.onReturnPressed: acceptSelection()
                                        Keys.onSpacePressed: acceptSelection()
                                        Keys.onEscapePressed: { view.showDriveChoices = false; drivePicker.forceActiveFocus() }
                                        Flickable {
                                            id: driveRows
                                            x: 4; y: 4; width: parent.width - 8; height: parent.height - 8
                                            clip: true; contentWidth: width; contentHeight: driveOptions.implicitHeight
                                            boundsBehavior: Flickable.StopAtBounds
                                        Column {
                                            id: driveOptions
                                            width: parent.width
                                            Repeater {
                                                model: view.driveChoices
                                                Rectangle {
                                                    required property int index
                                                    required property string modelData
                                                    width: parent.width; height: 24; radius: 3
                                                    color: index === driveMenu.currentIndex ? "#263a56" : "transparent"
                                                    Text { x: 8; anchors.verticalCenter: parent.verticalCenter; text: modelData; color: "#f1f3f8"; font.pixelSize: 12 }
                                                    MouseArea {
                                                        anchors.fill: parent; hoverEnabled: true
                                                        onPositionChanged: if (containsMouse) driveMenu.currentIndex = index
                                                        onClicked: { driveMenu.currentIndex = index; driveMenu.acceptSelection() }
                                                    }
                                                }
                                            }
                                        }
                                        }
                                    }
                                }
                                Item { Layout.fillWidth: true }
                                PButton { Layout.preferredWidth: 85; caption:view.t("Aggiorna","Refresh"); interactive:!view.occupied; onPressed:view.showRead("drives") }
                            }
                            Text {
                                visible: !!view.drives.error
                                width: parent.width
                                text: view.t("Informazioni unità non disponibili: ", "Drive information unavailable: ") + (view.drives.error || "")
                                textFormat: Text.PlainText; wrapMode: Text.WordWrap
                                color: "#e4b66d"; font.pixelSize: 13
                            }
                            Repeater {
                                model: (view.drives.drives || []).filter(function(row) { return row.letter === view.selectedDrive })
                                Column {
                                    width: parent.width; spacing: 12
                                    Text {
                                        text: modelData.available ? modelData.letter + " · " + (modelData.type === "Fixed" ? view.t("Unità fissa", "Fixed drive") : view.t("Unità locale", "Local drive")) + " · " +
                                              view.formatBytes(modelData.free_bytes) + view.t(" liberi / ", " free / ") + view.formatBytes(modelData.total_bytes) :
                                              view.t("Unità non disponibile", "Drive unavailable") + " · " + (modelData.error || "")
                                        width: parent.width; wrapMode:Text.WordWrap; color:"#9eafc8"; font.pixelSize:13
                                    }
                                    PProgress {
                                        width: parent.width; height:8
                                        fraction:typeof modelData.used_percent === "number" ? modelData.used_percent / 100 : 0
                                    }
                                }
                            }
                            PShortcut {
                                height: 38; caption:view.t("Ottimizza","Optimize"); iconName:"disk"
                                interactive:!view.occupied && readService.driveLetters.indexOf(view.selectedDrive) !== -1
                                onTriggered:view.request("drive_optimize",view.selectedDrive)
                            }
                        }
                    }
                    Rectangle {
                        width: parent.width; height: 64
                        radius:8; color:"#142138"; border.color:"#2e415c"
                        PShortcut {
                            x:14; y:12; width:parent.width - 28; height:40
                            caption: view.t("Apri ottimizzazione unità di Windows", "Open Windows drive optimizer")
                            iconName: "disk"; interactive:!view.occupied
                            onTriggered:view.request("open_defrag")
                        }
                    }
                    PButton {
                        caption: view.showExtraDriveTools ?
                                 view.t("Nascondi strumenti aggiuntivi", "Hide extra tools") :
                                 view.t("Strumenti aggiuntivi", "Extra tools")
                        onPressed: view.showExtraDriveTools = !view.showExtraDriveTools
                    }
                    Column {
                        width: parent.width
                        visible: view.showExtraDriveTools
                        spacing: 6
                        PRow { heading:view.t("Integrità volume","Disk health scan"); hint:"CHKDSK /scan /perf"; action:"chkdsk"; drive:view.selectedDrive; buttonText:view.t("Analizza","Scan"); interactive:!view.occupied && readService.driveLetters.indexOf(view.selectedDrive) !== -1; onInvoke:view.request(action,drive) }
                        PRow { heading:"Windows Update"; hint:view.t("Apri aggiornamenti","Open updates"); action:"windows_update"; buttonText:view.t("Apri","Open"); interactive:!view.occupied; onInvoke:view.request(action,drive) }
                        PRow { heading:view.t("Aggiornamenti facoltativi","Optional updates"); hint:view.t("Impostazioni Windows","Windows Settings"); action:"windows_optional"; buttonText:view.t("Apri","Open"); interactive:!view.occupied; onInvoke:view.request(action,drive) }
                    }
                    PSectionLog { scope: "disk"; caption: view.t("Output ottimizzazione", "Optimization output") }
                }
            }
        }
    }

    Component {
        id: turboAndStartupSection
        Column {
            width: parent.width; spacing: 16
            Flow {
                id: pair
                width: parent.width; spacing:20
                PPanel {
                    viewName: "turbo"
                    width: view.pairedPanelWidth(pair.width, 320)
                    spacing: 8
                    PSectionTitle { text:view.t("Impostazioni Turbo","Performance settings") }
                    PSectionHint { text:view.t("Le impostazioni originali vengono salvate per il ripristino.", "Original settings are saved for restoration.") }
                    Rectangle {
                        width:parent.width; height:turboMasterContent.implicitHeight + 24; color:"#142138"; border.color:"#2e415c"; radius:8
                        Column {
                            id: turboMasterContent
                            x: 12
                            y: 12
                            width: parent.width - 24
                            spacing: 9
                            GridLayout {
                                width:parent.width
                                columns: width < 390 ? 1 : 2
                                rowSpacing: 6
                                Text { text:view.t("Tutte le impostazioni","All settings"); color:"#f1f3f8"; font.bold:true; font.pixelSize:14; Layout.fillWidth:true }
                                RowLayout {
                                    spacing: 8
                                PToggle {
                                    caption:view.t("Turbo completo","All settings")
                                    checked:view.turbo.master === true
                                    interactive: !view.occupied && typeof view.turbo.master === "boolean"
                                    onChanged: view.request(nextValue ? "turbo_on" : "turbo_off")
                                }
                                    Text { text:view.stateCaption(view.turbo.master); color:"#9eafc8"; font.pixelSize:11 }
                                }
                            }
                            Text {
                                text: typeof view.turbo.saved_count === "number" ?
                                      (view.turbo.saved_count > 0 ?
                                       view.t(view.turbo.saved_count + " impostazioni originali salvate",
                                              view.turbo.saved_count + " original settings saved") :
                                       view.t("Nessuna modifica salvata", "No saved changes")) :
                                      view.t("Impostazioni salvate non disponibili · Aggiorna stato",
                                             "Saved settings unavailable · Refresh state")
                                width:parent.width; wrapMode:Text.WordWrap; color:"#9eafc8"; font.pixelSize:11
                            }
                            Column {
                                width: parent.width
                                spacing: 5
                                PButton {
                                    width: parent.width
                                    caption: view.t("Ripristina impostazioni salvate", "Restore saved settings")
                                    interactive: !view.occupied && view.turbo.restore_available === true
                                    onPressed: view.request("turbo_off")
                                }
                                PButton {
                                    width: parent.width
                                    caption: view.t("Aggiorna stato", "Refresh state")
                                    interactive: !view.occupied
                                    onPressed: view.showRead("turbo_status")
                                }
                            }
                        }
                    }
                    Rectangle {
                        width: parent.width; height: turboOptions.implicitHeight
                        radius: 8; color: "#142138"; border.color: "#2e415c"
                        Column {
                            id: turboOptions
                            width: parent.width
                    Repeater {
                        model:[
                            {key:"power", name:view.t("Prestazioni elevate","High performance"), hint:view.t("Aumenta consumi, calore e uso della batteria.","More power use, heat and battery drain."), on:"power_on", off:"power_off"},
                            {key:"visual",name:view.t("Effetti visivi","Visual effects preset"), hint:view.t("Regola le animazioni di Windows.","Adjust Windows animations."),on:"visual_on",off:"visual_off"},
                            {key:"sysmain",name:view.t("Sospendi SysMain","Pause SysMain"),hint:view.t("Ferma il precaricamento delle app.","Stops app preloading."),on:"sysmain_on",off:"sysmain_off"},
                            {key:"wsearch",name:view.t("Sospendi Windows Search","Pause Windows Search"),hint:view.t("Ferma l’indicizzazione in background.","Stops background indexing."),on:"wsearch_on",off:"wsearch_off"},
                            {key:"spooler",name:view.t("Sospendi spooler di stampa","Pause Print Spooler"),hint:view.t("La stampa non è disponibile durante la sospensione.","Printing is unavailable while active."),on:"spooler_on",off:"spooler_off"}
                        ]
                        Rectangle {
                            width: parent.width
                            height: Math.max(width < 390 ? 110 : 52, turboRow.implicitHeight + 16)
                            color: "transparent"
                            GridLayout {
                                id: turboRow
                                anchors.fill:parent; anchors.margins:8
                                columns: parent.width < 390 ? 1 : 2
                                rowSpacing: 6; columnSpacing: 10
                                ColumnLayout {
                                    Layout.fillWidth:true; Layout.minimumWidth:0; spacing:3
                                    Text { text:modelData.name; color:"#f1f3f8"; font.pixelSize:13; font.bold:true; Layout.fillWidth:true; wrapMode:Text.WordWrap }
                                    Text { text:modelData.hint; color:"#9eafc8"; font.pixelSize:11; Layout.fillWidth:true; wrapMode:Text.WordWrap }
                                }
                                RowLayout {
                                    spacing: 8
                                PToggle {
                                    caption:modelData.name
                                    checked: !!view.turbo.states && view.turbo.states[modelData.key] === true
                                    interactive: !view.occupied && !!view.turbo.states && typeof view.turbo.states[modelData.key] === "boolean"
                                    onChanged: view.request(nextValue ? modelData.on : modelData.off)
                                }
                                Text { text:view.stateCaption(view.turbo.states ? view.turbo.states[modelData.key] : null); font.pixelSize:11; color:"#9eafc8" }
                                }
                            }
                        }
                    }
                        }
                    }
                    Text {
                        visible: !view.turbo.states
                        text:view.turbo.states ? view.t("Stato di lettura aggiornabile manualmente.", "State can be refreshed manually.")
                            : view.t("Leggi lo stato prima di usare gli interruttori.", "Read state before using toggles.")
                        width:parent.width; color:"#9eafc8"; font.pixelSize:11; wrapMode:Text.WordWrap
                    }
                }
                PPanel {
                    viewName: "startup"
                    width: view.pairedPanelWidth(pair.width, 320)
                    spacing: 9
                    PSectionTitle { text:view.t("Applicazioni all'avvio","Startup apps") }
                    PSectionHint {
                        text:view.t("Disabilita applicazioni non necessarie all'accesso a Windows.",
                                     "Disable unnecessary apps at sign-in.")
                    }
                    Rectangle {
                        width: parent.width
                        height: startupLinks.implicitHeight + 28
                        radius: 8
                        color: "#142138"
                        border.color: "#2e415c"
                        Column {
                            id: startupLinks
                            x: 14
                            y: 14
                            width: parent.width - 28
                            PShortcut { caption: view.t("Impostazioni di avvio", "Startup settings"); iconName: "turbo"; interactive: !view.occupied; onTriggered: view.request("startup_settings") }
                        }
                    }
                }
            }
        }
    }

    Component {
        id: resurrectionSection
        Column {
            width:parent.width; spacing:12
            PGroupHeader {
                caption: view.t("Manutenzione guidata", "Guided Maintenance"); iconName: "resurrect"
                subtitle: view.t("10 fasi · Punto di ripristino verificato obbligatorio", "10 steps · Verified restore point required")
            }
            Rectangle {
                width:parent.width; height:resurrectionHero.implicitHeight + 28; radius:8; color:"#142138"; border.color:"#2e415c"
                Column {
                    id: resurrectionHero
                    anchors.fill:parent; anchors.margins:14; spacing:6
                    Text {
                        text:resurrectionResult.status ? view.statusCaption(resurrectionResult.status) : view.t("Pronto · Nessuna fase eseguita","Ready · No steps run")
                        color:"#f1f3f8"; font.pixelSize:16; font.bold:true
                    }
                    Text { text:(resurrectionResult.done || 0) + " / 10 " + view.t("fasi","steps"); color:"#e4c579"; font.pixelSize:12 }
                    PProgress { width:parent.width; height:11; fraction:(resurrectionResult.done || 0) / 10 }
                    Flow {
                        id: resurrectionActions
                        objectName: "resurrectionActions"
                        width: parent.width
                        spacing:9
                        PButton {
                            objectName: "resurrectionStartButton"
                            width: resurrectionActions.width < 400 ? resurrectionActions.width : 168
                            height:38; caption:view.t("Avvia sequenza","Start sequence")
                            primary:true; interactive:!view.occupied
                            onPressed:view.request("resurrection")
                        }
                        PButton {
                            width: resurrectionActions.width < 400 ? resurrectionActions.width : 176
                            height:36
                            visible:maintenanceService.busy && maintenanceService.lastAction === "resurrection"
                            caption:view.t("Annulla dopo la fase","Cancel after step")
                            interactive:maintenanceService.busy && maintenanceService.lastAction === "resurrection"
                            onPressed:maintenanceService.cancel()
                        }
                    }
                }
            }
            Rectangle {
                id: safetyPanel
                objectName: "resurrectionSafety"
                width:parent.width; height:safetyWarning.height + 46
                radius:8; color:"#242b37"; border.color:"#8d6d40"
                Image {
                    x:14; y:14; width:24; height:24
                    source:"image://panacea-nav/restore/detail"
                    sourceSize.width:96; sourceSize.height:96
                }
                Text {
                    x:46; y:9; width:parent.width - 58; height:28
                    verticalAlignment:Text.AlignVCenter
                    text:view.t("Prima di iniziare", "Before you start")
                    color:"#e4b66d"; font.bold:true; font.pixelSize:13
                }
                Text {
                    id: safetyWarning
                    x:46; y:37; width:parent.width - 72
                    height:Math.max(implicitHeight, width >= 590 ? 76 : width >= 420 ? 116 : 174)
                    verticalAlignment:Text.AlignVCenter
                    text:view.t("Prima di procedere Panacea deve verificare un nuovo punto di ripristino. Poi eliminerà definitivamente le cache dei browser, i file temporanei e il contenuto del Cestino: il punto di ripristino non può recuperarli.\nIl ripristino della rete può interrompere la connessione o richiedere un riavvio. Salva il lavoro. Se premi Annulla, Panacea termina il passaggio in corso e non avvia i successivi.",
                                "A new restore point must be verified first. Browser caches, temporary files and Recycle Bin contents will then be deleted permanently. A restore point cannot bring them back.\nResetting the network can interrupt your connection or require a restart. Save your work. If you cancel, Panacea finishes the current step and stops before the next one.")
                    color:"#f1f3f8"; wrapMode:Text.WordWrap; font.pixelSize:12
                }
            }
            Text {
                text: view.t("Fasi della manutenzione", "Maintenance steps")
                height: 28
                verticalAlignment: Text.AlignVCenter
                width: parent.width
                color: "#f1f3f8"
                font.pixelSize: 17
                font.bold: true
            }
            Flow {
                id: stepGrid
                x: 4
                width: parent.width - 8
                spacing: 8
                readonly property int columns: parent.width >= 1180 ? 5 : parent.width >= 610 ? 3 : parent.width >= 430 ? 2 : 1
                Repeater {
                    model: [
                    { title: view.t("Punto di ripristino", "Restore point"), help: view.t("Sicurezza · Verifica un nuovo punto di ripristino Windows. I file eliminati non saranno recuperabili.", "Safety · Verify a new Windows restore point. Deleted files cannot be recovered.") },
                    { title: view.t("Cache browser", "Browser caches"), help: view.t("Pulizia · Rimuove i dati temporanei della cache dei browser.", "Cleanup · Remove temporary browser cache data.") },
                    { title: view.t("File temporanei", "Temporary files"), help: view.t("Pulizia · Elimina i file temporanei idonei; quelli protetti vengono ignorati.", "Cleanup · Remove eligible temporary files; protected items are skipped.") },
                    { title: view.t("Cestino", "Recycle Bin"), help: view.t("Pulizia · Elimina definitivamente tutti gli elementi del Cestino.", "Cleanup · Permanently delete all items in the Recycle Bin.") },
                    { title: view.t("Cache DNS", "DNS cache"), help: view.t("Rete · Aggiorna le risoluzioni dei nomi di dominio memorizzate localmente.", "Network · Refresh locally cached domain-name lookups.") },
                    { title: view.t("Reset di rete", "Network reset"), help: view.t("Rete · Reimposta Winsock; potrebbe essere necessario riavviare.", "Network · Reset Winsock; a restart may be needed.") },
                    { title: view.t("Ottimizzazione unità", "Drive optimization"), help: view.t("Disco · Lascia che Windows utilizzi il metodo di ottimizzazione adatto all'unità.", "Disk · Let Windows use the optimization appropriate for the drive.") },
                    { title: view.t("Scansione disco", "Disk health scan"), help: view.t("Disco · Analizza il file system per individuare errori con CHKDSK online.", "Disk · Scan the file system for errors using online CHKDSK.") },
                    { title: view.t("Integrità immagine", "Windows image health"), help: view.t("Riparazione · Verifica la presenza di corruzione registrata nell'immagine Windows.", "Repair · Check recorded corruption in the Windows component image.") },
                    { title: view.t("Scansione file sistema", "System file scan"), help: view.t("Riparazione · Analizza e ripara i file di sistema protetti con SFC.", "Repair · Scan and repair protected Windows files using SFC.") }
                    ]
                    Rectangle {
                        id: guidedStep
                        objectName: "resurrection_step_" + index
                        property bool expanded: false
                        width: (stepGrid.width - (stepGrid.columns - 1) * stepGrid.spacing) / stepGrid.columns
                        height: Math.max(54, guidedContent.implicitHeight + 18)
                        radius: 8
                        color: "#142138"
                        border.color: "#2e415c"
                        Column {
                            id: guidedContent
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.top: parent.top
                            anchors.leftMargin: 10
                            anchors.rightMargin: 10
                            anchors.topMargin: 9
                            spacing: 5
                            RowLayout {
                                width: parent.width
                                spacing: 8
                                Text {
                                    text: ("0" + (index + 1)).slice(-2)
                                    Layout.preferredWidth: 25
                                    color: "#e4c579"
                                    font.pixelSize: 13
                                    font.bold: true
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 2
                                    Text {
                                        text: view.stepDisplay(index, modelData.title)
                                        Layout.fillWidth: true
                                        color: "#f1f3f8"
                                        font.pixelSize: 12
                                        font.bold: true
                                        wrapMode: Text.WordWrap
                                    }
                                    Text {
                                        text: view.stepCaption(index)
                                        Layout.fillWidth: true
                                        color: progressSteps.length > index ?
                                               (progressSteps[index].success === true ? "#78c8a8" : "#ee939a") :
                                               (maintenanceService.busy &&
                                                maintenanceService.lastAction === "resurrection" &&
                                                resurrectionResult.done === index ? "#e4b66d" : "#9eafc8")
                                        font.pixelSize: 10
                                    }
                                }
                                Rectangle {
                                    id: stepInfo
                                    width: 28
                                    height: 28
                                    radius: 6
                                    color: guidedStep.expanded ? "#263a56" : "#1b2b44"
                                    border.color: activeFocus ? "#76b6e2" : "#2e415c"
                                    activeFocusOnTab: true
                                    Accessible.role: Accessible.Button
                                    Accessible.name: view.t("Dettagli fase ", "Step details ") + (index + 1)
                                    Accessible.description: modelData.help
                                    function activate() { guidedStep.expanded = !guidedStep.expanded }
                                    Keys.onReturnPressed: activate()
                                    Keys.onSpacePressed: activate()
                                    Text {
                                        anchors.centerIn: parent
                                        text: "i"
                                        color: "#9eafc8"
                                        font.pixelSize: 12
                                        font.bold: true
                                    }
                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: stepInfo.activate()
                                    }
                                }
                            }
                            Text {
                                id: stepExplanation
                                width: parent.width
                                visible: guidedStep.expanded
                                text: modelData.help
                                color: "#9eafc8"
                                font.pixelSize: 11
                                wrapMode: Text.WordWrap
                            }
                            Text {
                                width: parent.width
                                visible: guidedStep.expanded && progressSteps.length > index
                                text: progressSteps.length > index ? (progressSteps[index].message || "") : ""
                                color: "#f1f3f8"
                                font.pixelSize: 11
                                wrapMode: Text.WordWrap
                            }
                        }
                    }
                }
            }
            PSectionLog { scope: "resurrect"; caption: view.t("Output sequenza completo", "Full sequence output") }
            PButton { caption:view.t("Verifica blocco manutenzione", "Check maintenance guard"); interactive:!view.occupied; onPressed:view.showRead("guard_status") }
            Text {
                visible: text.length > 0
                text:view.guard.message || ""
                width:parent.width; color:view.guard.blocked ? "#e4b66d" : "#9eafc8"; font.pixelSize:11; wrapMode:Text.WordWrap
            }
        }
    }
}
