"""Stable GitHub release discovery and bounded, verified executable downloads.

Only repository-owned HTTPS URLs are accepted. GitHub's asset CDN is allowed
after an authenticated repository URL redirects there. No downloaded file is
executed by this module; the installer verifies the bytes again.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct
import tempfile
from typing import Callable
import urllib.error
import urllib.parse
import urllib.request

from packaging.version import InvalidVersion, Version


class UpdateError(Exception):
    """An update failed; the current application remains usable."""


class UpdateNetworkError(UpdateError):
    pass


class UpdateRateLimitError(UpdateNetworkError):
    pass


class UpdateManifestError(UpdateError):
    pass


class UpdateVerificationError(UpdateError):
    pass


class UpdateCancelled(UpdateError):
    pass


MAX_ASSET_SIZE = 512 * 1024 * 1024
MAX_MANIFEST_SIZE = 1024 * 1024
MAX_CHECKSUM_SIZE = 4096
CHUNK_SIZE = 128 * 1024
_HASH_RE = re.compile(r"[0-9a-fA-F]{64}")


@dataclass(frozen=True)
class Release:
    version: str
    release_url: str
    exe_url: str
    size: int
    sha256_url: str
    notes: str = ""


def _version(value: str) -> Version:
    try:
        if not isinstance(value, str):
            raise InvalidVersion(str(value))
        return Version(value.strip())
    except InvalidVersion as exc:
        raise UpdateManifestError("Release version is invalid.") from exc


def is_newer(remote: str, local: str) -> bool:
    """Compare legacy/PEP 440 versions and never offer prerelease/dev builds."""
    candidate, installed = _version(remote), _version(local)
    return not candidate.is_prerelease and not candidate.is_devrelease and candidate > installed


def _secure_url(url: str):
    if not isinstance(url, str) or any(ord(char) <= 32 or ord(char) == 127 for char in url):
        raise UpdateManifestError("Release URL is missing.")
    try:
        parsed = urllib.parse.urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise UpdateManifestError("Release URL has an invalid port.") from exc
    if (parsed.scheme != "https" or "@" in parsed.netloc or port is not None
            or parsed.query or parsed.fragment):
        raise UpdateManifestError("Release URLs must be plain repository-owned HTTPS URLs.")
    return parsed


def _assert_plain_path(path: Path) -> None:
    """Reject symlinks and Windows reparse points in every existing ancestor."""
    path = Path(os.path.abspath(path))
    for item in (path, *path.parents):
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise UpdateVerificationError("Update paths cannot traverse links or reparse points.")


def _read_bounded(response, maximum: int, error_type=UpdateVerificationError) -> bytes:
    data = bytearray()
    while len(data) <= maximum:
        chunk = response.read(min(CHUNK_SIZE, maximum + 1 - len(data)))
        if not chunk:
            return bytes(data)
        data.extend(chunk)
    raise error_type("Update response exceeds its size limit.")


def parse_checksum(data: bytes) -> str:
    """Accept a single SHA-256 or a standard checksum for exactly Panacea.exe."""
    try:
        text = data.decode("ascii").strip()
    except UnicodeDecodeError as exc:
        raise UpdateVerificationError("Checksum is not ASCII.") from exc
    match = re.fullmatch(r"([0-9a-fA-F]{64})(?:[ \t]+\*?Panacea\.exe)?", text)
    if not match:
        raise UpdateVerificationError("Checksum must identify exactly Panacea.exe.")
    return match.group(1).lower()


def verify_stream(stream, expected_sha256: str, expected_size: int | None = None) -> int:
    """Verify an open file, including PE signature, without reopening its path."""
    if not isinstance(expected_sha256, str) or not _HASH_RE.fullmatch(expected_sha256):
        raise UpdateVerificationError("Expected SHA-256 is invalid.")
    stream.seek(0)
    digest = hashlib.sha256()
    count = 0
    while True:
        chunk = stream.read(CHUNK_SIZE)
        if not chunk:
            break
        count += len(chunk)
        if count > MAX_ASSET_SIZE or expected_size is not None and count > expected_size:
            raise UpdateVerificationError("Executable exceeds its advertised size.")
        digest.update(chunk)
    if expected_size is not None and count != expected_size:
        raise UpdateVerificationError("Executable size does not match the release.")
    if digest.hexdigest() != expected_sha256.lower():
        raise UpdateVerificationError("Executable SHA-256 does not match the release.")
    stream.seek(0)
    header = stream.read(64)
    if len(header) != 64 or header[:2] != b"MZ":
        raise UpdateVerificationError("Executable has no valid DOS/PE header.")
    offset = struct.unpack_from("<I", header, 60)[0]
    if offset < 64 or offset > count - 26:
        raise UpdateVerificationError("Executable PE header is outside the file.")
    stream.seek(offset)
    if stream.read(4) != b"PE\0\0":
        raise UpdateVerificationError("Executable PE signature is invalid.")
    coff = stream.read(20)
    machine, sections, _, _, _, optional_size, characteristics = struct.unpack("<HHIIIHH", coff)
    if (machine not in (0x14C, 0x8664, 0xAA64) or not 1 <= sections <= 96
            or not characteristics & 2 or characteristics & 0x2000):
        raise UpdateVerificationError("PE header does not describe a supported executable image.")
    magic = struct.unpack("<H", stream.read(2))[0]
    minimum_optional = 96 if magic == 0x10B else 112 if magic == 0x20B else None
    if (minimum_optional is None or optional_size < minimum_optional
            or offset + 24 + optional_size + 40 * sections > count
            or machine in (0x8664, 0xAA64) and magic != 0x20B
            or machine == 0x14C and magic != 0x10B):
        raise UpdateVerificationError("Executable optional/section headers are invalid or truncated.")
    stream.seek(0)
    return count


def verify_file(path: str | Path, expected_sha256: str, expected_size: int | None = None) -> int:
    path = Path(path)
    _assert_plain_path(path)
    with path.open("rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise UpdateVerificationError("Executable must be a regular file.")
        return verify_stream(stream, expected_sha256, expected_size)


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, client):
        self.client = client

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.client._validate_transport_url(newurl, asset=True)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class UpdateClient:
    def __init__(self, repo: str, current_version: str, *, opener=None, timeout: float = 20):
        if (not isinstance(repo, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo)
                or any(part in (".", "..") for part in repo.split("/"))):
            raise UpdateManifestError("Repository must be an owner/name pair.")
        _version(current_version)
        self.repo, self.current_version, self.timeout = repo, current_version, timeout
        self.api_url = f"https://api.github.com/repos/{repo}/releases/latest"
        self._open = opener or urllib.request.build_opener(_SafeRedirect(self)).open

    def _validate_transport_url(self, url: str, *, asset=False):
        # GitHub's CDN query carries a signed expiry and is required for downloads.
        if not isinstance(url, str) or any(ord(char) <= 32 or ord(char) == 127 for char in url):
            raise UpdateManifestError("Update redirect URL is invalid.")
        try:
            parsed = urllib.parse.urlsplit(url)
            port = parsed.port
        except ValueError as exc:
            raise UpdateManifestError("Update redirect URL is invalid.") from exc
        if (parsed.scheme != "https" or "@" in parsed.netloc
                or parsed.hostname not in ("github.com", "api.github.com", "release-assets.githubusercontent.com")
                or port is not None or parsed.fragment):
            raise UpdateManifestError("Update redirect left trusted HTTPS GitHub hosts.")
        if parsed.hostname == "release-assets.githubusercontent.com":
            if not asset:
                raise UpdateManifestError("Release metadata cannot come from the asset CDN.")
        elif parsed.hostname == "api.github.com":
            if url != self.api_url:
                raise UpdateManifestError("Release metadata URL is outside this repository.")
        elif not parsed.path.startswith(f"/{self.repo}/releases/download/") or parsed.query:
            raise UpdateManifestError("Asset redirect is outside this repository.")

    def _request(self, url: str, *, asset=False):
        request = urllib.request.Request(url, headers={
            "User-Agent": "Panacea-Verified-Updater", "Accept": "application/vnd.github+json" if not asset else "application/octet-stream",
            "Accept-Encoding": "identity",
        })
        try:
            response = self._open(request, timeout=self.timeout)
            try:
                self._validate_transport_url(response.geturl(), asset=asset)
            except Exception:
                response.close()
                raise
            return response
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 429):
                raise UpdateRateLimitError("GitHub denied or rate-limited the update check. Try again later.") from exc
            raise UpdateNetworkError(f"GitHub update request failed (HTTP {exc.code}).") from exc
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            raise UpdateNetworkError("Cannot contact GitHub. Check the connection and retry.") from exc

    def _validate_release(self, release: Release, tag: str | None = None):
        if not isinstance(release, Release):
            raise UpdateManifestError("A verified release manifest is required.")
        if (type(release.size) is not int or not 64 <= release.size <= MAX_ASSET_SIZE
                or not is_newer(release.version, self.current_version)):
            raise UpdateManifestError("Release is not a newer stable executable of valid size.")
        page = _secure_url(release.release_url)
        prefix = f"/{self.repo}/releases/tag/"
        if page.hostname != "github.com" or not page.path.startswith(prefix):
            raise UpdateManifestError("Release page is outside the configured repository.")
        actual_tag = page.path[len(prefix):]
        if not actual_tag or "/" in actual_tag or _version(actual_tag) != _version(release.version):
            raise UpdateManifestError("Release page does not match its version.")
        if tag is not None and actual_tag != tag:
            raise UpdateManifestError("Release tag and page disagree.")
        for url, filename in ((release.exe_url, "Panacea.exe"), (release.sha256_url, "Panacea.exe.sha256")):
            asset = _secure_url(url)
            if asset.hostname != "github.com" or asset.path != f"/{self.repo}/releases/download/{actual_tag}/{filename}":
                raise UpdateManifestError("Asset URL must identify the exact repository release asset.")

    def check(self) -> Release | None:
        try:
            with self._request(self.api_url) as response:
                data = _read_bounded(response, MAX_MANIFEST_SIZE, UpdateManifestError)
            manifest = json.loads(data)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise UpdateManifestError("GitHub returned invalid release metadata.") from exc
        except (OSError, TimeoutError) as exc:
            raise UpdateNetworkError("Release metadata download was interrupted.") from exc
        if not isinstance(manifest, dict):
            raise UpdateManifestError("GitHub release metadata is not an object.")
        if type(manifest.get("draft")) is not bool or type(manifest.get("prerelease")) is not bool:
            raise UpdateManifestError("Release stability fields are missing.")
        if manifest["draft"] or manifest["prerelease"]:
            return None
        tag = manifest.get("tag_name")
        if not is_newer(tag, self.current_version):
            return None
        assets = manifest.get("assets")
        if not isinstance(assets, list) or any(not isinstance(asset, dict) for asset in assets):
            raise UpdateManifestError("Release assets are missing or malformed.")
        selected = {}
        for name in ("Panacea.exe", "Panacea.exe.sha256"):
            matches = [asset for asset in assets if asset.get("name") == name]
            if len(matches) != 1:
                raise UpdateManifestError(f"Release must contain exactly one {name} asset.")
            selected[name] = matches[0]
        checksum_size = selected["Panacea.exe.sha256"].get("size")
        if type(checksum_size) is not int or not 64 <= checksum_size <= MAX_CHECKSUM_SIZE:
            raise UpdateManifestError("Checksum asset size is invalid.")
        release = Release(str(_version(tag)), manifest.get("html_url"),
                          selected["Panacea.exe"].get("browser_download_url"),
                          selected["Panacea.exe"].get("size"),
                          selected["Panacea.exe.sha256"].get("browser_download_url"),
                          manifest.get("body") or "")
        self._validate_release(release, tag)
        return release

    def fetch_checksum(self, release: Release) -> str:
        self._validate_release(release)
        try:
            with self._request(release.sha256_url, asset=True) as response:
                return parse_checksum(_read_bounded(response, MAX_CHECKSUM_SIZE))
        except (OSError, TimeoutError) as exc:
            raise UpdateNetworkError("Checksum download was interrupted.") from exc

    def download(self, release: Release, directory: str | Path,
                 progress: Callable[[int, int], bool | None] | None = None) -> Path:
        self._validate_release(release)
        expected = self.fetch_checksum(release)
        directory = Path(os.path.abspath(directory))
        _assert_plain_path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        _assert_plain_path(directory)
        descriptor, temporary = tempfile.mkstemp(prefix="Panacea-", suffix=".part", dir=directory)
        temporary = Path(temporary)
        verified = temporary.with_suffix(".exe")
        verified_created = False
        completed = False
        try:
            with os.fdopen(descriptor, "w+b") as stream:
                if progress and progress(0, release.size) is False:
                    raise UpdateCancelled("Update download cancelled.")
                with self._request(release.exe_url, asset=True) as response:
                    count = 0
                    while True:
                        chunk = response.read(min(CHUNK_SIZE, release.size + 1 - count))
                        if not chunk:
                            break
                        count += len(chunk)
                        if count > release.size:
                            raise UpdateVerificationError("Download exceeds the advertised executable size.")
                        stream.write(chunk)
                        if progress and progress(count, release.size) is False:
                            raise UpdateCancelled("Update download cancelled.")
                stream.flush()
                os.fsync(stream.fileno())
                verify_stream(stream, expected, release.size)
            _assert_plain_path(directory)
            # An exclusive destination prevents overwriting an unrelated existing file.
            with verified.open("xb+") as destination:
                verified_created = True
                with temporary.open("rb") as source:
                    while chunk := source.read(CHUNK_SIZE):
                        destination.write(chunk)
                destination.flush()
                os.fsync(destination.fileno())
                verify_stream(destination, expected, release.size)
            temporary.unlink()
            completed = True
            return verified
        except (OSError, TimeoutError) as exc:
            raise UpdateNetworkError("Download was interrupted or could not be written.") from exc
        finally:
            temporary.unlink(missing_ok=True)
            if verified_created and not completed:
                verified.unlink(missing_ok=True)
