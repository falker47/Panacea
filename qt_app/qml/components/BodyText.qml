import QtQuick
import QtQuick.Controls.Basic

Label {
    property bool tabular: false
    font.family: Theme.fontFamily
    font.pixelSize: Theme.fontBody
    font.features: tabular ? ({ "tnum": 1 }) : ({})
    color: Theme.text
    textFormat: Text.PlainText
    wrapMode: Text.Wrap
}
