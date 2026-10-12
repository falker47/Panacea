"""Updater tests use fake HTTP streams; no network or executable launch."""
import hashlib
import io
import json
import struct
import urllib.error

import pytest

from modules import updater


REPO = "owner/Panacea"
TAG = "v1.49.0"
BASE = f"https://github.com/{REPO}/releases/download/{TAG}/"


def pe_bytes():
    data = bytearray(512)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 60, 128)
    data[128:132] = b"PE\0\0"
    struct.pack_into("<HHIIIHH", data, 132, 0x8664, 1, 0, 0, 0, 240, 0x22)
    struct.pack_into("<H", data, 152, 0x20B)
    return bytes(data)


def manifest():
    return {
        "tag_name": TAG, "draft": False, "prerelease": False,
        "html_url": f"https://github.com/{REPO}/releases/tag/{TAG}",
        "body": "Verified release notes.",
        "assets": [
            {"name": "Panacea.exe", "browser_download_url": BASE + "Panacea.exe", "size": 512},
            {"name": "Panacea.exe.sha256", "browser_download_url": BASE + "Panacea.exe.sha256", "size": 78},
        ],
    }


class Response(io.BytesIO):
    def __init__(self, data, url, *, fail_after=None):
        super().__init__(data)
        self.url = url
        self.headers = {}
        self.fail_after = fail_after

    def geturl(self):
        return self.url

    def read(self, size=-1):
        if self.fail_after is not None and self.tell() >= self.fail_after:
            raise OSError("connection interrupted")
        return super().read(min(size, self.fail_after or size))


def fake_opener(release=None, data=None, checksum=None, *, interrupt=False, final_url=None):
    release = manifest() if release is None else release
    data = pe_bytes() if data is None else data
    checksum = (hashlib.sha256(data).hexdigest() + "  Panacea.exe\n").encode() if checksum is None else checksum

    def open_response(request, timeout):
        url = request.full_url
        if url.endswith("/releases/latest"):
            payload = json.dumps(release).encode()
        elif url.endswith(".sha256"):
            payload = checksum
        else:
            payload = data
        return Response(payload, final_url or url, fail_after=128 if interrupt and url.endswith(".exe") else None)
    return open_response


@pytest.mark.parametrize("remote,local,expected", [
    ("v1.49.0", "1.47", True), ("1.10", "1.9", True),
    ("1.49.0", "1.49", False), ("v1.47", "1.49.0", False),
    ("1.49.0rc1", "1.48", False), ("1.50.dev1", "1.49", False),
])
def test_version_ordering_handles_legacy_and_rejects_unstable(remote, local, expected):
    assert updater.is_newer(remote, local) is expected


def test_invalid_version_is_explicit_failure():
    with pytest.raises(updater.UpdateManifestError):
        updater.is_newer("latest", "1.47")


def test_check_returns_exact_stable_release_and_notes():
    release = updater.UpdateClient(REPO, "1.47", opener=fake_opener()).check()
    assert release.version == "1.49.0"
    assert release.exe_url == BASE + "Panacea.exe"
    assert release.sha256_url == BASE + "Panacea.exe.sha256"
    assert release.size == 512
    assert release.notes == "Verified release notes."


@pytest.mark.parametrize("change", [
    lambda m: m.update(draft=True),
    lambda m: m.update(prerelease=True),
    lambda m: m.update(tag_name="v1.49.0rc1"),
])
def test_unstable_releases_are_never_offered(change):
    release = manifest()
    change(release)
    assert updater.UpdateClient(REPO, "1.47", opener=fake_opener(release)).check() is None


def test_equal_or_older_release_is_not_offered():
    assert updater.UpdateClient(REPO, "1.49.0", opener=fake_opener()).check() is None


@pytest.mark.parametrize("change", [
    lambda m: m["assets"].pop(),
    lambda m: m["assets"].append(m["assets"][1].copy()),
    lambda m: m["assets"][0].update(name="Other.exe"),
    lambda m: m["assets"][0].update(browser_download_url="https://example.com/Panacea.exe"),
    lambda m: m["assets"][1].update(browser_download_url="http://github.com/owner/Panacea/releases/download/v1.49.0/Panacea.exe.sha256"),
    lambda m: m["assets"][0].update(browser_download_url=BASE.replace("owner/", "foreign/") + "Panacea.exe"),
    lambda m: m["assets"][0].update(browser_download_url=BASE + "Panacea.exe\n"),
    lambda m: m["assets"][0].update(browser_download_url=BASE.replace("github.com", "@github.com") + "Panacea.exe"),
    lambda m: m.update(html_url="https://github.com/foreign/Panacea/releases/tag/v1.49.0"),
    lambda m: m["assets"][0].update(size=True),
    lambda m: m["assets"][0].update(size=0),
    lambda m: m["assets"][1].update(size=1000000),
])
def test_malformed_or_foreign_manifests_fail_closed(change):
    release = manifest()
    change(release)
    with pytest.raises(updater.UpdateManifestError):
        updater.UpdateClient(REPO, "1.47", opener=fake_opener(release)).check()


@pytest.mark.parametrize("status,exception", [(403, "UpdateRateLimitError"), (429, "UpdateRateLimitError"), (500, "UpdateNetworkError")])
def test_http_errors_are_explicit(status, exception):
    def failing(request, timeout):
        raise urllib.error.HTTPError(request.full_url, status, "unavailable", {}, None)
    with pytest.raises(getattr(updater, exception)):
        updater.UpdateClient(REPO, "1.47", opener=failing).check()


def test_offline_is_not_reported_as_up_to_date():
    def offline(request, timeout):
        raise urllib.error.URLError("offline")
    with pytest.raises(updater.UpdateNetworkError):
        updater.UpdateClient(REPO, "1.47", opener=offline).check()


def test_download_returns_only_verified_pe_and_reports_progress(tmp_path):
    client = updater.UpdateClient(REPO, "1.47", opener=fake_opener())
    release = client.check()
    progress = []
    path = client.download(release, tmp_path, lambda count, total: progress.append((count, total)))
    assert path.read_bytes() == pe_bytes()
    assert path.suffix == ".exe"
    assert progress[-1] == (512, 512)
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize("options,exception", [
    ({"interrupt": True}, "UpdateNetworkError"),
    ({"data": pe_bytes()[:-1]}, "UpdateVerificationError"),
    ({"data": pe_bytes() + b"x"}, "UpdateVerificationError"),
    ({"checksum": b"0" * 64 + b"  Panacea.exe\n"}, "UpdateVerificationError"),
    ({"checksum": b"not a checksum"}, "UpdateVerificationError"),
    ({"checksum": b"0" * 64 + b"  Other.exe\n"}, "UpdateVerificationError"),
    ({"checksum": b"0" * 10000}, "UpdateVerificationError"),
    ({"data": b"x" * 512}, "UpdateVerificationError"),
    ({"final_url": "http://release-assets.githubusercontent.com/asset"}, "UpdateManifestError"),
    ({"final_url": "https://foreign.example/asset"}, "UpdateManifestError"),
])
def test_failed_download_never_returns_or_leaves_partial_executable(tmp_path, options, exception):
    client = updater.UpdateClient(REPO, "1.47", opener=fake_opener())
    release = client.check()
    client._open = fake_opener(**options)
    with pytest.raises(getattr(updater, exception)):
        client.download(release, tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_download_cancellation_removes_partial_file(tmp_path):
    client = updater.UpdateClient(REPO, "1.47", opener=fake_opener())
    with pytest.raises(updater.UpdateCancelled):
        client.download(client.check(), tmp_path, lambda count, total: False)
    assert list(tmp_path.iterdir()) == []


def test_download_rejects_foreign_release_passed_directly(tmp_path):
    client = updater.UpdateClient(REPO, "1.47", opener=fake_opener())
    release = updater.Release("1.49.0", "https://example.com/notes", BASE + "Panacea.exe", 512, BASE + "Panacea.exe.sha256")
    with pytest.raises(updater.UpdateManifestError):
        client.download(release, tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_pe_offset_must_point_inside_file(tmp_path):
    data = bytearray(pe_bytes())
    struct.pack_into("<I", data, 60, 1000000)
    client = updater.UpdateClient(REPO, "1.47", opener=fake_opener(data=bytes(data)))
    with pytest.raises(updater.UpdateVerificationError):
        client.download(client.check(), tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_download_collision_does_not_delete_existing_file(tmp_path, monkeypatch):
    sentinel = tmp_path / "Panacea-fixed.exe"
    sentinel.write_bytes(b"keep existing")
    partial = tmp_path / "Panacea-fixed.part"

    def fixed_temporary(**kwargs):
        import os
        return os.open(partial, os.O_RDWR | os.O_CREAT | os.O_EXCL), str(partial)

    monkeypatch.setattr(updater.tempfile, "mkstemp", fixed_temporary)
    client = updater.UpdateClient(REPO, "1.47", opener=fake_opener())
    with pytest.raises(updater.UpdateError):
        client.download(client.check(), tmp_path)
    assert sentinel.read_bytes() == b"keep existing"
    assert not partial.exists()


@pytest.mark.parametrize("offset,value", [(132, 0), (134, 0), (148, 65535), (150, 0x2002), (152, 0)])
def test_malformed_pe_coff_and_optional_headers_are_rejected(tmp_path, offset, value):
    data = bytearray(pe_bytes())
    struct.pack_into("<H", data, offset, value)
    client = updater.UpdateClient(REPO, "1.47", opener=fake_opener(data=bytes(data)))
    with pytest.raises(updater.UpdateVerificationError):
        client.download(client.check(), tmp_path)
    assert list(tmp_path.iterdir()) == []
