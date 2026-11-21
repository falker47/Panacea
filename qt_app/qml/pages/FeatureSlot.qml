import QtQuick
import QtQml
import "../components"

Loader {
    id: slot
    required property string name
    objectName: "feature_" + name
    property Component candidate
    readonly property url location: featureUrls[name] || ""
    readonly property Item feature: item ? item.feature : null
    readonly property bool available: feature !== null
    readonly property bool loading: (candidate !== null && candidate.status === Component.Loading)
                                    || status === Loader.Loading
    signal navigateRequested(string section)
    visible: available
    focus: true
    active: candidate !== null && candidate.status === Component.Ready

    Component.onCompleted: {
        if (location.toString().length)
            candidate = Qt.createComponent(location, Component.Asynchronous, slot)
    }
    sourceComponent: Item {
        id: host
        property Item feature
        implicitWidth: feature ? feature.implicitWidth : 0
        implicitHeight: feature ? (feature.implicitHeight || feature.height) : 0
        Component.onCompleted: feature = featureFactory.create(slot.candidate, host, i18n.language, Theme)
        Binding { target: host.feature; property: "width"; value: host.width; when: host.feature !== null }
        Binding { target: host.feature; property: "language"; value: i18n.language; when: host.feature !== null }
    }
    Connections {
        target: slot.feature
        ignoreUnknownSignals: true
        function onNavigateRequested(section) { slot.navigateRequested(section) }
    }
}
