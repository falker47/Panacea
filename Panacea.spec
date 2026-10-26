# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
import sys
from pathlib import Path

project_root = Path(SPECPATH)
sys.path.insert(0, str(project_root))
from version import VERSION
from scripts.release_tools import version_resource

version_file = project_root / 'build' / 'version-info.txt'
version_file.parent.mkdir(parents=True, exist_ok=True)
version_file.write_text(version_resource(VERSION), encoding='utf-8')

# Bundle only runtime references. Source artwork/licensing files remain in Git.
datas = [
    ('assets/panacea_icon.ico', 'assets'),
    ('assets/panacea_icon.png', 'assets'),
    ('assets/icons/lucide/png', 'assets/icons/lucide/png'),
    ('assets/icons/lucide/LICENSE', 'assets/icons/lucide'),
]
binaries = []
hiddenimports = []
tmp_ret = collect_all('customtkinter')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Pillow can optionally import numpy; Panacea uses none of its APIs.
    # Exclude it so unrelated globally installed packages do not inflate the EXE.
    excludes=['numpy'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
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
