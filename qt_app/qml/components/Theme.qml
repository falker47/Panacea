pragma Singleton
import QtQuick

QtObject {
    readonly property var systemColors: appSettings ? appSettings.systemColors : ({})
    readonly property bool highContrast: Object.keys(systemColors).length > 0
    readonly property bool reducedMotion: appSettings ? appSettings.systemReducedMotion || appSettings.reduceMotion : false

    readonly property color bg: systemColors.bg || "#0b1525"
    readonly property color surface: systemColors.surface || "#13213a"
    readonly property color surfaceAlt: systemColors.surfaceAlt || "#1a2b47"
    readonly property color border: systemColors.border || "#2a3d5c"
    readonly property color controlBorder: highContrast ? border : "#697e9c"
    readonly property color text: systemColors.text || "#f1f3f8"
    readonly property color textMuted: systemColors.textMuted || "#a9b6cc"
    readonly property color accent: systemColors.accent || "#e4c579"
    readonly property color onAccent: systemColors.onAccent || "#1a1408"
    readonly property color info: systemColors.info || "#76b6e2"
    readonly property color success: systemColors.success || "#5cc58a"
    readonly property color warning: systemColors.warning || "#f0b44c"
    readonly property color danger: systemColors.danger || "#ef6b6b"
    readonly property color focus: systemColors.focus || "#76b6e2"

    readonly property int radiusS: 6
    readonly property int radiusM: 10
    readonly property int spacing: 8
    readonly property var installedFonts: Qt.fontFamilies()
    readonly property string fontFamily: installedFonts.indexOf("Segoe UI Variable") >= 0 ? "Segoe UI Variable" : "Segoe UI"
    readonly property string fontMono: installedFonts.indexOf("Consolas") >= 0 ? "Consolas" : "monospace"
    readonly property int fontSmall: 12
    readonly property int fontBody: 14
    readonly property int fontLabel: 16
    readonly property int fontTitle: 20
    readonly property int fontDisplay: 28

    function tr(key, params) {
        // Reading the notified property makes every caller update on a language change.
        return i18n && i18n.language ? i18n.t(key, params || {}) : ""
    }

    function icon(name, color) {
        return name ? "image://panacea-nav/" + name + "/" + (color || text).toString().slice(1) : ""
    }

    function toneColor(tone) {
        switch (tone) {
        case "success": return success
        case "warning": return warning
        case "danger": return danger
        case "info": return info
        default: return textMuted
        }
    }

    function toneGlyph(tone) {
        switch (tone) {
        case "success": return "check"
        case "warning": return "warning"
        case "danger": return "error"
        case "info": return "info"
        default: return "clock"
        }
    }

    function wash(ink, opacity, base) {
        return highContrast ? base : Qt.tint(base, Qt.rgba(ink.r, ink.g, ink.b, opacity))
    }
}
