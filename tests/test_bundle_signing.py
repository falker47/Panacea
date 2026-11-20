"""The updater hashes certificate bytes. All signing tests use inert data and mocked tools."""
import base64
import hashlib
import io
import os
from pathlib import Path
import struct
from types import SimpleNamespace

import pytest

from modules.updater import UpdateVerificationError, verify_stream
from scripts import release_tools


def test_updater_hashes_the_appended_pe_certificate_table():
    from test_updater import pe_bytes

    image = bytearray(pe_bytes())
    optional = 128 + 24  # PE32+ optional header in this fixture
    struct.pack_into("<I", image, optional + 108, 16)  # NumberOfRvaAndSizes
    certificate = struct.pack("<IHH8s", 16, 0x0200, 2, b"testdata")
    # IMAGE_DIRECTORY_ENTRY_SECURITY uses a file offset. WIN_CERTIFICATE is aligned to 8.
    struct.pack_into("<II", image, optional + 112 + 8 * 4, len(image), len(certificate))
    image.extend(certificate)
    digest = hashlib.sha256(image).hexdigest()
    assert verify_stream(io.BytesIO(image), digest, len(image)) == len(image)
    image[-1] ^= 1
    with pytest.raises(UpdateVerificationError, match="SHA-256"):
        verify_stream(io.BytesIO(image), digest, len(image))


def test_unsigned_and_dry_run_never_invoke_signtool(monkeypatch, tmp_path, capsys):
    path = tmp_path / "Panacea.exe"
    path.write_bytes(b"fixture")
    for key in release_tools.SIGN_SECRETS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(release_tools.subprocess, "run", lambda *_a, **_kw: pytest.fail("unexpected process"))
    release_tools.optional_sign(path)
    assert "unsigned" in capsys.readouterr().out
    monkeypatch.setenv("PANACEA_SIGN_PASSWORD", "dummy")
    with pytest.raises(ValueError, match="Incomplete"):
        release_tools.optional_sign(path)
    monkeypatch.setenv("PANACEA_SIGN_PFX_BASE64", "ZHVtbXk=")
    monkeypatch.setenv("PANACEA_SIGN_TIMESTAMP_URL", "https://tsa.example.test")
    release_tools.optional_sign(path, dry_run=True)
    assert path.read_bytes() == b"fixture"


@pytest.mark.skipif(os.name != "nt", reason="Windows SDK fixture")
@pytest.mark.parametrize("verify_exit", [0, 1])
def test_sign_and_verify_only_the_selected_asset(monkeypatch, tmp_path, verify_exit):
    for name, value in {
        "ProgramFiles(x86)": str(tmp_path), "RUNNER_TEMP": str(tmp_path),
        "GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "github-hosted",
        "GITHUB_REF": "refs/heads/main", "PANACEA_ALLOW_HOSTED_PROBE": "true",
        "PANACEA_SIGN_PFX_BASE64": base64.b64encode(b"fixture").decode(),
        "PANACEA_SIGN_PASSWORD": "dummy", "PANACEA_SIGN_TIMESTAMP_URL": "https://tsa.example.test",
    }.items():
        monkeypatch.setenv(name, value)
    tool = tmp_path / "Windows Kits/10/bin/10.0.9.0/x64/signtool.exe"
    tool.parent.mkdir(parents=True)
    tool.touch()
    asset = tmp_path / "PanaceaSetup.exe"
    asset.write_bytes(b"setup")
    seen = []

    def fake_run(argv, **_kwargs):
        assert argv[0] == str(tool) and argv[-1] == str(asset)
        seen.append(argv)
        if argv[1] == "sign":
            assert Path(argv[argv.index("/f") + 1]).read_bytes() == b"fixture"
            asset.write_bytes(b"fixture signed bytes")
        return SimpleNamespace(returncode=verify_exit if argv[1] == "verify" else 0)

    monkeypatch.setattr(release_tools.subprocess, "run", fake_run)
    from scripts import build_installer
    monkeypatch.setattr(build_installer, "validate_setup", release_tools.binary_sha256)
    if verify_exit:
        with pytest.raises(RuntimeError, match="verify failed"):
            release_tools.finalize_asset(asset)
        assert not asset.with_suffix(".exe.sha256").exists()
    else:
        release_tools.finalize_asset(asset)
        assert asset.with_suffix(".exe.sha256").read_text().strip() == (
            hashlib.sha256(asset.read_bytes()).hexdigest() + "  PanaceaSetup.exe"
        )
    assert [a[1] for a in seen] == ["sign", "verify"]
    assert seen[1][2] == "/pa"
    assert not Path(seen[0][seen[0].index("/f") + 1]).exists()
