import hashlib
from urllib.error import HTTPError
from urllib.request import Request

import pytest

from modules.updater import UpdateClient, UpdateVerificationError
from scripts.update_compat.github_emulator import ASSETS, REPO, ReleaseFixture
from test_updater import pe_bytes


@pytest.fixture
def assets(tmp_path):
    for name in ASSETS[::2]:
        payload = pe_bytes()
        (tmp_path / name).write_bytes(payload)
        (tmp_path / (name + ".sha256")).write_text(f"{hashlib.sha256(payload).hexdigest()}  {name}\n")
    return tmp_path


@pytest.mark.parametrize("lower", [True, False])
def test_redirected_download_and_no_repeated_offer(assets, lower):
    fixture = ReleaseFixture(assets, "v2.2.0", lower_case=lower)
    client = UpdateClient(REPO, "2.1.1", opener=fixture.open)
    release = client.check()
    assert release.version == "2.2.0"
    assert [a["name"] for a in fixture.manifest["assets"]] == list(ASSETS)
    assert client.download(release, assets / "stage").read_bytes() == pe_bytes()
    assert [r["status"] for r in fixture.requests] == [200, 302, 200, 302, 200]
    assert all("release-assets.githubusercontent.com" in r["url"] and "?sig=" in r["url"]
               for r in fixture.requests[2::2])
    assert UpdateClient(REPO, "2.2.0", opener=fixture.open).check() is None


@pytest.mark.parametrize("field", ["draft", "prerelease"])
def test_stability_fields(assets, field):
    fixture = ReleaseFixture(assets, "v2.2.0", **{field: True})
    assert UpdateClient(REPO, "2.1.1", opener=fixture.open).check() is None


def test_unknown_request_and_corrupt_asset(assets):
    fixture = ReleaseFixture(assets, "v2.2.0")
    for url in ("https://example.org/", "https://github.com/private"):
        with pytest.raises(HTTPError) as error:
            fixture.open(Request(url), timeout=1)
        assert error.value.code == 404
        assert fixture.requests[-1] == {"url": url, "status": 404}
    (assets / "Panacea.exe").write_bytes(b"x" * len(pe_bytes()))
    client = UpdateClient(REPO, "2.1.1", opener=fixture.open)
    with pytest.raises(UpdateVerificationError, match="SHA-256"):
        client.download(client.check(), assets / "stage")
    assert not list((assets / "stage").iterdir())
