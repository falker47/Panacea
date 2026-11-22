# -*- mode: python ; coding: utf-8 -*-
"""Official PySide6 / Qt Quick one-file release image."""
import os
import sys
from pathlib import Path

project_root = Path(SPECPATH)
sys.path.insert(0, str(project_root))
from version import VERSION
from scripts.release_tools import version_resource
from scripts.verify_bundle import UNUSED_BINDINGS, denied, missing_required

version_file = project_root / "build" / "version-info.txt"
version_file.parent.mkdir(parents=True, exist_ok=True)
version_file.write_text(version_resource(VERSION), encoding="utf-8")

datas = [
    ("qt_app/Main.qml", "qt_app"),
    ("qt_app/qml", "qt_app/qml"),
    ("qt_app/i18n/*.json", "qt_app/i18n"),
    ("assets/panacea_icon.ico", "assets"),
    ("assets/panacea_icon.png", "assets"),
    ("assets/icons/lucide/png", "assets/icons/lucide/png"),
    ("assets/icons/lucide/LICENSE", "assets/icons/lucide"),
]
hiddenimports = [
    "qt_app.bridges.reliability_bridge", "qt_app.bridges.features_bridge",
    "modules.commands", "modules.cleanup", "modules.disk",
    "modules.restore", "modules.performance", "modules.maintenance_guard",
    "modules.updater", "modules.update_install", "modules.quick_cleanup",
]

# Resolve system DLLs against Windows, not unrelated SDKs on the developer's PATH.
# For example, Qt6Core needs Windows ICU's unversioned exports.
if sys.platform == "win32":
    windows = Path(os.environ["SystemRoot"])
    python = Path(sys.base_prefix)
    os.environ["PATH"] = os.pathsep.join(map(str, (
        windows / "System32", windows, python, python / "DLLs", Path(sys.executable).parent,
    )))

a = Analysis(
    ['qt_app/main.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PIL", "numpy", "customtkinter", "tkinter", *(f"PySide6.{m}" for m in UNUSED_BINDINGS)],
    noarchive=False,
    optimize=0,
)
# Qt's QML hook collects every installed plugin, including unused native engines.
# Filter destinations after binary dependency analysis and before EXE consumes the TOCs.
a.binaries = [entry for entry in a.binaries if not denied(entry[0])]
a.datas = [entry for entry in a.datas if not denied(entry[0])]
missing = missing_required(entry[0] for entry in a.binaries + a.datas)
if missing:
    raise ValueError(f"Release Qt dependencies missing after pruning: {missing}")
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name='Panacea',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\panacea_icon.ico'],
    version=str(version_file),
)
