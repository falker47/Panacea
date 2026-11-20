"""Inventory and enforce the Windows one-file release policy without extracting the app."""
import argparse
import json
from pathlib import Path
import re

from PyInstaller.archive.readers import CArchiveReader


# Paths are archive destinations, independent of the build machine or install prefix.
# Keep the native QtNetwork/QtOpenGL dependencies of the Qml/Quick Python bindings.
UNUSED_BINDINGS = (
    "Qt3DAnimation", "Qt3DCore", "Qt3DExtras", "Qt3DInput", "Qt3DLogic", "Qt3DRender",
    "QtBluetooth", "QtCharts", "QtDataVisualization", "QtDesigner", "QtGraphs",
    "QtLocation", "QtMultimedia", "QtMultimediaWidgets", "QtPdf", "QtPdfWidgets",
    "QtPositioning", "QtQuick3D", "QtQuickWidgets", "QtSql", "QtTextToSpeech",
    "QtWebEngineCore", "QtWebEngineQuick", "QtWebEngineWidgets", "QtWebView", "QtWidgets",
)
UNUSED_FAMILIES = (
    "webengine", "webview", "quick3d", "pdf", "qt3d", "qt63d", "multimedia", "virtualkeyboard",
    "charts", "graphs", "datavisualization", "location", "positioning", "texttospeech", "sql",
    "bluetooth", "designer", "quickdialogs", "quickparticles", "quicktimeline", "quickvectorimage",
    "openglwidgets", "printsupport", "quickwidgets", "svgwidgets", "qt6widgets", "shadertools",
    "webchannel", "websockets", "remoteobjects", "scxml", "sensors", "spatialaudio",
)
UNUSED_PLUGINS = {
    "assetimporters", "canbus", "designer", "geometryloaders", "geoservices", "multimedia",
    "position", "qmllint", "qmltooling", "renderers", "renderplugins", "sceneparsers",
    "scxmldatamodel", "sensors", "sqldrivers", "styles", "texttospeech", "webview",
}
UNUSED_QML = (
    "qt5compat/", "qtquick/dialogs/", "qtquick/localstorage/", "qtquick/nativestyle/",
    "qtquick/particles/", "qtquick/scene2d/", "qtquick/scene3d/", "qtquick/timeline/",
    "qtquick/tooling/", "qtquick/vectorimage/", "qttest/", "qt/labs/platform/",
    "qt/labs/wavefrontmesh/",
)
QT_DLLS = ("Core", "Gui", "Qml", "Quick", "QuickLayouts", "QuickControls2", "QuickControls2Basic",
           "QuickEffects", "QuickTemplates2", "QuickControls2Impl", "QuickControls2BasicStyleImpl",
           "QuickShapes", "LabsQmlModels", "Svg")
QML_PLUGINS = {
    "QtQuick": "qtquick2plugin", "QtQuick/Window": "quickwindowplugin",
    "QtQuick/Layouts": "qquicklayoutsplugin", "QtQuick/Effects": "effectsplugin",
    "QtQuick/Controls": "qtquickcontrols2plugin",
    "QtQuick/Controls/Basic": "qtquickcontrols2basicstyleplugin",
    "QtQuick/Controls/impl": "qtquickcontrols2implplugin",
    "QtQuick/Controls/Basic/impl": "qtquickcontrols2basicstyleimplplugin",
    "QtQuick/Shapes": "qmlshapesplugin", "Qt/labs/qmlmodels": "labsmodelsplugin",
    "QtQuick/Templates": "qtquicktemplates2plugin",
}
REQUIRED = (
    *(f"PySide6/Qt6{name}.dll" for name in QT_DLLS),
    "PySide6/plugins/platforms/qwindows.dll", "PySide6/plugins/imageformats/qsvg.dll",
    *(f"PySide6/qml/{module}/{file}" for module, plugin in QML_PLUGINS.items()
      for file in ("qmldir", f"{plugin}.dll")),
)
TARGET_BYTES = 60_000_000
MAX_EXE_BYTES = 70_000_000
MAX_EXTRACTED_BYTES = 180_000_000


def normalized(name):
    return name.replace("\\", "/").casefold()


def denied(name):
    path = normalized(name)
    # Qt DLLs may also be collected flat at the archive root.
    relative = path.removeprefix("pyside6/")
    if path == relative and not relative.startswith(("qt", "qml/", "plugins/", "translations/")):
        return False
    if any(family in relative for family in UNUSED_FAMILIES):
        return True
    if relative.startswith("translations/"):
        return not re.search(r"_(?:it|en)(?:_[a-z]{2})?\.qm$", relative)
    if relative.startswith("plugins/") and relative.split("/")[1] in UNUSED_PLUGINS:
        return True
    qml = relative.removeprefix("qml/")
    if qml.startswith(UNUSED_QML) or "/designer/" in qml:
        return True
    controls = "qtquick/controls/"
    if qml.startswith(controls):
        child, sep, _ = qml[len(controls):].partition("/")
        if sep and child not in {"basic", "impl"}:
            return True
    return bool(re.match(r"qt6quickcontrols2(?!basic|impl|\.)", relative))


def missing_required(names):
    present = {normalized(name) for name in names}
    return [name for name in REQUIRED if normalized(name) not in present]


def archive_report(toc, exe_bytes):
    entries = [{"name": name, "compressed_bytes": stored, "extracted_bytes": expanded}
               for name, (_, stored, expanded, _, _) in toc.items()]
    expanded = sum(e["extracted_bytes"] for e in entries)
    errors = []
    missing = missing_required(toc)
    forbidden = sorted(name for name in toc if denied(name))
    if missing or forbidden:
        errors.append("Archive policy violation (see missing and forbidden)")
    if exe_bytes > MAX_EXE_BYTES:
        errors.append(f"Executable exceeds {MAX_EXE_BYTES} bytes")
    if expanded > MAX_EXTRACTED_BYTES:
        errors.append(f"Archive exceeds {MAX_EXTRACTED_BYTES} uncompressed bytes")
    return {
        "exe_bytes": exe_bytes, "target_bytes": TARGET_BYTES, "within_target": exe_bytes <= TARGET_BYTES,
        "max_exe_bytes": MAX_EXE_BYTES, "entry_count": len(entries),
        "compressed_bytes": sum(e["compressed_bytes"] for e in entries),
        "extracted_bytes": expanded, "max_extracted_bytes": MAX_EXTRACTED_BYTES,
        "top_20_by_compressed_bytes": sorted(entries, key=lambda e: (-e["compressed_bytes"], e["name"]))[:20],
        "missing": missing, "forbidden": forbidden, "errors": errors,
        "entries": sorted(entries, key=lambda e: e["name"]),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = archive_report(CArchiveReader(args.exe).toc, args.exe.stat().st_size)
    except (OSError, ValueError, RuntimeError) as exc:
        report = {"errors": [str(exc)]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in {"entries", "top_20_by_compressed_bytes"}}))
    return int(bool(report["errors"]))


if __name__ == "__main__":
    raise SystemExit(main())
