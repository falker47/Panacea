"""Frozen CI transport adapter. Only its embedded candidate and inert faults are eligible."""

import json
import os
from pathlib import Path
import sys
import time

from scripts.update_compat.github_emulator import ReleaseFixture
from scripts.update_compat.hosted import hosted_guard, published_modules
from modules.updater import parse_checksum, verify_file


def main():
    _, program_files = hosted_guard()
    if not getattr(sys, "frozen", False):
        raise RuntimeError("Requires a frozen Actions fixture")
    workspace = Path(sys.argv[1]).resolve(strict=True)
    case = sys.argv[2]
    target = program_files / "Panacea" / "Panacea.exe"
    if workspace.parent != target.parent or Path(sys.executable) != workspace / "Panacea-updater.exe":
        raise RuntimeError("Unexpected fixture location")
    spec = json.loads((Path(sys._MEIPASS) / "fixture.json").read_text(encoding="utf-8"))
    if spec["run"] != os.environ["GITHUB_RUN_ID"] or spec["sha"] != os.environ["SOURCE_SHA"]:
        raise RuntimeError("Fixture belongs to a different build")
    digest = spec["allowed"][case]
    root = Path(os.environ["GITHUB_WORKSPACE"])
    artifacts = root / "build/candidate"
    portable_dir = artifacts if case == "good" else root / "build/compat-faults" / case
    if parse_checksum((portable_dir / "Panacea.exe.sha256").read_bytes()) != digest:
        raise RuntimeError("Input differs from the checksum embedded at fixture build time")
    verify_file(workspace / "staged.exe", digest)
    fixture = ReleaseFixture(artifacts, "v" + spec["version"], portable_dir=portable_dir)
    events = []
    try:
        with published_modules(target, spec["from"], install=True) as old:
            installer = old["modules.update_install"]
            client_type = old["modules.updater"].UpdateClient
            write_status = installer._write_status

            def observe(path, status, message):
                write_status(path, status, message)
                events.append({"status": status, "at": time.monotonic(), "message": message})

            installer._write_status = observe
            return installer.run_update_helper(
                workspace, client_factory=lambda repo, version: client_type(repo, version, opener=fixture.open))
    finally:
        log = root / "build/update-compat" / f"helper-{case}.json"
        log.write_text(json.dumps({"events": events, "requests": fixture.requests}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
