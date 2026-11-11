"""Forward-update contract for the *currently published* Panacea client.

This does not certify a future unpublished EXE or a physical Windows upgrade.
It prevents a future source release from silently losing canonical GitHub
discovery, SHA-256 verification, or the stable asset naming convention.
"""
from __future__ import annotations

import hashlib
import io
import json
import struct

from packaging.version import Version
import pytest

from modules.updater import UpdateClient, UpdateManifestError, UpdateVerificationError
from version import GITHUB_REPO, VERSION


def _future_release():
    installed = Version(VERSION)
    assert not installed.is_prerelease and not installed.is_devrelease
    assert GITHUB_REPO == "falker47/Panacea"
    tag = f"v{installed.major}.{installed.minor + 1}.0"
    base = f"https://github.com/{GITHUB_REPO}/releases"
    executable = bytearray(512)
    executable[:2] = b"MZ"
    struct.pack_into("<I", executable, 60, 128)
    executable[128:132] = b"PE\0\0"
    struct.pack_into("<HHIIIHH", executable, 132, 0x8664, 1, 0, 0, 0, 240, 0x22)
    struct.pack_into("<H", executable, 152, 0x20B)
    executable = bytes(executable)
    checksum = f"{hashlib.sha256(executable).hexdigest()}  Panacea.exe\n".encode("ascii")
    manifest = {
        "tag_name": tag,
        "draft": False,
        "prerelease": False,
        "html_url": f"{base}/tag/{tag}",
        "assets": [
            {"name": "Panacea.exe",
             "browser_download_url": f"{base}/download/{tag}/Panacea.exe",
             "size": len(executable)},
            {"name": "Panacea.exe.sha256",
             "browser_download_url": f"{base}/download/{tag}/Panacea.exe.sha256",
             "size": len(checksum)},
        ],
    }
    return tag, manifest, executable, checksum


class _Response(io.BytesIO):
    def __init__(self, data, url):
        super().__init__(data)
        self.url = url

    def geturl(self):
        return self.url


def _opener(manifest, executable, checksum):
    api = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    by_url = {
        api: json.dumps(manifest).encode("utf-8"),
        manifest["assets"][0]["browser_download_url"]: executable,
        manifest["assets"][1]["browser_download_url"]: checksum,
    }

    def open_response(request, timeout):
        url = request.full_url
        assert url in by_url, f"Unexpected update URL: {url}"
        return _Response(by_url[url], url)

    return open_response


def test_current_client_can_discover_and_verify_next_stable_version(tmp_path):
    tag, manifest, executable, checksum = _future_release()
    client = UpdateClient(GITHUB_REPO, VERSION, opener=_opener(manifest, executable, checksum))
    release = client.check()
    assert release is not None
    assert release.version == tag.lstrip("v")
    assert client.fetch_checksum(release) == hashlib.sha256(executable).hexdigest()
    verified = client.download(release, tmp_path)
    assert verified.read_bytes() == executable
    assert list(tmp_path.iterdir()) == [verified]

    # No reinstall/downgrade offer when the installed version is already current.
    next_client = UpdateClient(GITHUB_REPO, release.version,
                               opener=_opener(manifest, executable, checksum))
    assert next_client.check() is None


@pytest.mark.parametrize("tamper", ["foreign_page", "foreign_asset", "bad_asset_name"])
def test_future_release_still_rejects_untrusted_distribution(tamper):
    _, manifest, executable, checksum = _future_release()
    if tamper == "foreign_page":
        manifest["html_url"] = manifest["html_url"].replace(
            f"github.com/{GITHUB_REPO}/", "github.com/other/Panacea/")
    elif tamper == "foreign_asset":
        manifest["assets"][0]["browser_download_url"] = (
            manifest["assets"][0]["browser_download_url"].replace(
                f"github.com/{GITHUB_REPO}/", "github.com/other/Panacea/"))
    else:
        manifest["assets"][0]["name"] = "Other.exe"
    client = UpdateClient(GITHUB_REPO, VERSION, opener=_opener(manifest, executable, checksum))
    with pytest.raises(UpdateManifestError):
        client.check()


def test_future_release_with_wrong_checksum_is_not_staged(tmp_path):
    _, manifest, executable, _ = _future_release()
    bogus = f"{'0' * 64}  Panacea.exe\n".encode("ascii")
    manifest["assets"][1]["size"] = len(bogus)
    client = UpdateClient(GITHUB_REPO, VERSION, opener=_opener(manifest, executable, bogus))
    release = client.check()
    with pytest.raises(UpdateVerificationError):
        client.download(release, tmp_path)
    assert list(tmp_path.iterdir()) == []
