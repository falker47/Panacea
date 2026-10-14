"""Installer packaging invariants and fail-closed checks."""
from pathlib import Path
import struct
from types import SimpleNamespace

import pytest

from scripts import build_installer


def pe_fixture(path):
    data = bytearray(1_000_250)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 60, 128)
    data[128:132] = b"PE\0\0"
    path.write_bytes(data)
    return path


def test_inno_installer_is_stable_machine_install_with_no_forced_close():
    text = build_installer.SPEC.read_text(encoding="utf-8")
    for required in (
        "AppId={{B6C0FB10-27BC-4E6F-9078-40F9E8B49B2D}",
        "DefaultDirName={autopf}\\Panacea", "PrivilegesRequired=admin",
        "DisableDirPage=yes", "UsePreviousAppDir=no",
        "CloseApplications=no", "RestartApplications=no",
        "OutputBaseFilename=PanaceaSetup", 'DestName: "Panacea.exe"',
        "UninstallDisplayIcon={app}\\Panacea.exe",
        "{autoprograms}\\Panacea", "AppVersion={#PanaceaVersion}",
    ):
        assert required in text
    assert "[UninstallDelete]" not in text


def test_installer_rejects_bad_input_checksum_before_compiling(tmp_path, monkeypatch):
    exe = tmp_path / "Panacea.exe"
    checksum = tmp_path / "Panacea.exe.sha256"
    exe.write_bytes(b"wrong")
    checksum.write_text("0" * 64 + "  Panacea.exe\n", encoding="ascii")
    monkeypatch.setattr(build_installer, "locate_compiler", lambda *_: pytest.fail("compiler must not run"))
    with pytest.raises(Exception):
        build_installer.build_installer(exe, checksum, tmp_path)


def test_installer_requires_exact_asset_names(tmp_path):
    with pytest.raises(ValueError, match="exact"):
        build_installer.validate_portable(tmp_path / "other.exe", tmp_path / "other.sha256")


def test_installer_pe_header_and_checksum(tmp_path):
    exe = pe_fixture(tmp_path / "PanaceaSetup.exe")
    assert build_installer.validate_setup(exe) == build_installer.binary_sha256(exe)
    exe.write_bytes(b"corrupt")
    with pytest.raises(ValueError):
        build_installer.validate_setup(exe)


def test_installer_build_passes_version_and_generates_verified_manifest(tmp_path, monkeypatch):
    source = tmp_path / "Panacea.exe"
    source.write_bytes(b"fixture")
    monkeypatch.setattr(build_installer, "validate_portable", lambda *_: (source, "fixture-hash"))
    monkeypatch.setattr(build_installer, "locate_compiler", lambda *_: "C:/Inno Setup/ISCC.exe")
    called = []

    def compiler(args, **kwargs):
        called.append((args, kwargs))
        destination = next(item.split("=", 1)[1] for item in args if item.startswith("/DPanaceaOutputDir="))
        pe_fixture(Path(destination) / "PanaceaSetup.exe")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(build_installer.subprocess, "run", compiler)
    installer, digest = build_installer.build_installer(source, tmp_path / "Panacea.exe.sha256", tmp_path / "out")
    assert installer.name == "PanaceaSetup.exe"
    assert digest == build_installer.binary_sha256(installer)
    assert (installer.parent / "PanaceaSetup.exe.sha256").read_text(encoding="ascii") == (
        digest + "  PanaceaSetup.exe\n")
    from version import VERSION
    assert f"/DPanaceaVersion={VERSION}" in called[0][0]
    assert any(item.startswith("/DPanaceaIconPath=") for item in called[0][0])
    assert called[0][1]["check"] is True
    assert called[0][1]["timeout"] == 240
