"""Shared runner guard, pinned module loading and result recording."""

from contextlib import contextmanager
import json
import os
from pathlib import Path
import sys
import types

from scripts.update_compat.published import PUBLISHED


def hosted_guard():
    if (os.name != "nt" or os.getenv("RUNNER_ENVIRONMENT") != "github-hosted"
            or os.getenv("GITHUB_ACTIONS") != "true"
            or os.getenv("PANACEA_ALLOW_HOSTED_PROBE") != "true"):
        raise RuntimeError("Requires an explicitly enabled GitHub-hosted Windows runner")
    from scripts.hosted_installer_probe import disposable_guard
    return disposable_guard()


@contextmanager
def report(name):
    hosted_guard()
    path = Path("build/update-compat") / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"status": "FAIL", "sha": os.environ["SOURCE_SHA"], "probe": name}
    try:
        yield data
    except Exception as error:
        data["error"] = f"{type(error).__name__}: {error}"
        raise
    else:
        data["status"] = "PASS"
    finally:
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


@contextmanager
def published_modules(executable, tag, *, install=False):
    """Load the installed version's own imports in a single-purpose probe process."""
    with checked_modules(executable, PUBLISHED[tag].exe, install=install) as loaded:
        config = loaded["version"]
        if "v" + config.VERSION != tag or config.GITHUB_REPO.casefold() != "falker47/panacea":
            raise RuntimeError("Unexpected pinned version identity")
        yield loaded


def candidate_is_current(executable, meta, artifacts):
    from scripts.update_compat.github_emulator import ReleaseFixture
    fixture = ReleaseFixture(artifacts, "v" + meta["version"])
    with checked_modules(executable, meta["exe_sha256"]) as loaded:
        config = loaded["version"]
        if config.VERSION != meta["version"] or config.GITHUB_REPO != "falker47/Panacea":
            raise RuntimeError("Unexpected candidate identity")
        client = loaded["modules.updater"].UpdateClient(config.GITHUB_REPO, config.VERSION, opener=fixture.open)
        return client.check() is None


@contextmanager
def checked_modules(executable, digest, *, install=False):
    hosted_guard()
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError("Published bytecode requires CPython 3.12")
    from PyInstaller.archive.readers import CArchiveReader
    from modules.updater import verify_file
    verify_file(executable, digest)
    archive = CArchiveReader(str(executable)).open_embedded_archive("PYZ.pyz")
    names = ["version", "modules.updater"]
    if install:
        names.append("modules.update_install")
    original = {name: sys.modules.get(name) for name in names}
    try:
        loaded = {}
        for name in names:
            module = types.ModuleType(name)
            sys.modules[name] = module
            exec(archive.extract(name), module.__dict__)
            loaded[name] = module
        yield loaded
    finally:
        for name, module in original.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module
