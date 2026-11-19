"""Stamp the disposable build checkout. Never create a tag or commit."""

import os
from pathlib import Path
import re
import subprocess

from packaging.version import InvalidVersion, Version


def choose_version(source, tags):
    if not re.fullmatch(r"\d+\.\d+\.\d+", source):
        raise ValueError("Expected a stable three-component source version")
    releases = []
    for tag in tags:
        try:
            releases.append(Version(tag))
        except InvalidVersion:
            continue
    if not releases:
        raise ValueError("No version tags available; fetch the repository tags first")
    highest = max(releases)
    if Version(source) > highest:
        return source
    # Also sorts after rc/post/dev versions of this release.
    major, minor, patch = highest.major, highest.minor, highest.micro
    patch += 100
    if patch > 65535:
        minor, patch = minor + 1, 0
    if minor > 65535:
        major, minor = major + 1, 0
    candidate = f"{major}.{minor}.{patch}"
    if max(major, minor, patch) > 65535 or Version(candidate) <= highest:
        raise ValueError("Cannot represent a newer Windows product version")
    return candidate


def stamp(root, tags):
    path = root / "version.py"
    raw = path.read_bytes()
    pattern = rb'(?m)^VERSION = "([^"\r\n]+)"(?=\r?$)'
    matches = list(re.finditer(pattern, raw))
    if len(matches) != 1:
        raise ValueError("Expected exactly one VERSION assignment")
    match = matches[0]
    source = match[1].decode("ascii")
    version = choose_version(source, tags)
    notes = root / "docs" / "releases" / f"{version}.md"
    if not notes.exists():
        with notes.open("x", encoding="utf-8") as stream:
            stream.write(f"# Panacea {version}\n\nDisposable PR compatibility candidate.\n")
    if version != source:
        path.write_bytes(raw[:match.start(1)] + version.encode("ascii") + raw[match.end(1):])
    return version


def main():
    from scripts.update_compat.hosted import hosted_guard

    hosted_guard()
    root = Path(os.environ["GITHUB_WORKSPACE"]).resolve(strict=True)
    if root != Path(__file__).resolve().parents[2] or Path.cwd().resolve() != root:
        raise RuntimeError("Stamping requires the Actions checkout")
    tags = subprocess.check_output(["git", "tag", "--list", "v*"], cwd=root, text=True)
    print(stamp(root, tags.splitlines()))


if __name__ == "__main__":
    main()
