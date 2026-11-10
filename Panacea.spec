# -*- mode: python ; coding: utf-8 -*-
"""Official PySide6 / Qt Quick one-file release image."""
import sys
from pathlib import Path

project_root = Path(SPECPATH)
sys.path.insert(0, str(project_root))
from version import VERSION
from scripts.release_tools import version_resource

version_file = project_root / "build" / "version-info.txt"
version_file.parent.mkdir(parents=True, exist_ok=True)
version_file.write_text(version_resource(VERSION), encoding="utf-8")

datas = [
    ("qt_app/Main.qml", "qt_app"),
    ("qt_app/ParityPage.qml", "qt_app"),
    ("assets/panacea_icon.ico", "assets"),
    ("assets/panacea_icon.png", "assets"),
    ("assets/icons/lucide/png", "assets/icons/lucide/png"),
    ("assets/icons/lucide/LICENSE", "assets/icons/lucide"),
]
hiddenimports = [
    "modules.commands", "modules.cleanup", "modules.disk",
    "modules.restore", "modules.performance", "modules.maintenance_guard",
    "modules.updater", "modules.update_install", "modules.quick_cleanup",
]

a = Analysis(
    ['qt_app/main.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["numpy", "customtkinter"],
    noarchive=False,
    optimize=0,
)
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
