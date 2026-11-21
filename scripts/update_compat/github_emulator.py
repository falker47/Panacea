"""In-memory GitHub release fixture for UpdateClient's explicit opener parameter."""

from dataclasses import dataclass
from io import BytesIO
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.response import addinfourl

ASSETS = ("Panacea.exe", "Panacea.exe.sha256", "PanaceaSetup.exe", "PanaceaSetup.exe.sha256")
REPO = "falker47/Panacea"


@dataclass(frozen=True)
class Reply:
    status: int
    body: bytes | Path = b""
    location: str | None = None


class ReleaseFixture:
    def __init__(self, artifacts: Path, tag: str, *, lower_case=False, draft=False, prerelease=False,
                 portable_dir=None):
        self.requests = []
        repo = REPO.lower() if lower_case else REPO
        base = f"https://github.com/{repo}/releases"
        self.assets = {}
        self.redirects = {}
        manifest_assets = []
        for name in ASSETS:
            directory = portable_dir if portable_dir and name in ASSETS[:2] else artifacts
            path = directory / name
            url = f"{base}/download/{tag}/{name}"
            final = f"https://release-assets.githubusercontent.com/test/{tag}/{name}?sig=fixture"
            self.redirects[url] = final
            self.assets[final] = path
            manifest_assets.append({"name": name, "size": path.stat().st_size, "browser_download_url": url})
        self.manifest = {
            "tag_name": tag, "draft": draft, "prerelease": prerelease, "body": "Candidate under test",
            "html_url": f"{base}/tag/{tag}", "assets": manifest_assets,
        }

    def route(self, url):
        if url in (f"https://api.github.com/repos/{REPO}/releases/latest",
                   f"https://api.github.com/repos/{REPO.lower()}/releases/latest"):
            reply = Reply(200, json.dumps(self.manifest).encode("utf-8"))
        elif url in self.redirects:
            reply = Reply(302, location=self.redirects[url])
        elif url in self.assets:
            reply = Reply(200, self.assets[url])
        else:
            reply = Reply(404)
        self.requests.append({"url": url, "status": reply.status})
        return reply

    def open(self, request, *, timeout):
        url = request.full_url
        reply = self.route(url)
        if reply.status == 302:
            url = reply.location
            reply = self.route(url)
        if reply.status != 200:
            raise HTTPError(url, reply.status, "Unknown fixture URL", {}, None)
        body = reply.body.open("rb") if isinstance(reply.body, Path) else BytesIO(reply.body)
        return addinfourl(body, {}, url, reply.status)
