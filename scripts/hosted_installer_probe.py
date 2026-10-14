"""Isolated real installer and protected EXE-update test on disposable Windows CI.

No command in this module may execute on the owner's PC. It does not run Turbo,
Resurrection, system repair or an unpublished real GitHub update manifest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import traceback
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from modules.update_install import (  # noqa: E402
    _assert_admin_directory, _assert_admin_file, install_verified, readiness_path)
from modules.updater import parse_checksum, verify_file  # noqa: E402
from scripts.build_installer import validate_setup  # noqa: E402


def disposable_guard():
    if (os.name != "nt" or os.getenv("GITHUB_ACTIONS") != "true"
            or os.getenv("RUNNER_OS") != "Windows"
            or os.getenv("PANACEA_ALLOW_HOSTED_PROBE") != "true"):
        raise RuntimeError("Only an authorized GitHub-hosted disposable Windows runner is allowed.")
    temp = Path(os.environ["RUNNER_TEMP"]).resolve(strict=True)
    if len(temp.parts) < 3 or str(temp).lower() in ("c:\\", "d:\\"):
        raise RuntimeError("Unsafe temporary directory.")
    program_files = Path(os.environ["ProgramFiles"]).resolve(strict=True)
    _assert_admin_directory(program_files)
    return temp, program_files


def run_checked(command, *, timeout=120, env=None):
    result = subprocess.run([str(item) for item in command], stdin=subprocess.DEVNULL,
                            capture_output=True, text=True, timeout=timeout,
                            check=False, env=env)
    if result.returncode:
        raise RuntimeError(f"{Path(command[0]).name} exit {result.returncode}: "
                           + (result.stderr or result.stdout)[-1500:])
    return result


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def actual_install_test(args):
    temp, program_files = disposable_guard()
    portable = Path(args.portable).resolve(strict=True)
    expected = parse_checksum(Path(args.checksum).read_bytes())
    verify_file(portable, expected, portable.stat().st_size)
    setup = Path(args.setup).resolve(strict=True)
    checksum = Path(args.setup_checksum).read_text(encoding="ascii")
    match = re.fullmatch(r"([0-9a-fA-F]{64})\s+\*?PanaceaSetup\.exe\s*", checksum)
    if not match or match.group(1).lower() != validate_setup(setup):
        raise RuntimeError("Installer checksum did not match.")
    dest = program_files / ("Panacea-CI-" + uuid.uuid4().hex)
    sentinel = temp / ("panacea-other-" + uuid.uuid4().hex + ".txt")
    sentinel.write_text("PRESERVE", encoding="utf-8")
    start_link = (Path(os.environ["ProgramData"]) / "Microsoft" / "Windows" /
                  "Start Menu" / "Programs" / "Panacea.lnk")
    previous_link = start_link.exists()
    report = {"setup_sha256": match.group(1).lower(), "portable_sha256": expected,
              "directory": str(dest), "checks": {},
              "unverified": ["Interactive UAC prompts (hosted runner has UAC off)",
                             "In-app online update from an unpublished future version",
                             "Windows reboot and forcibly interrupted update helper",
                             "Turbo, Resurrection, repairs, real display DPI"]}
    installed = False
    try:
        run_checked([setup, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
                     "/NOCLOSEAPPLICATIONS", f"/DIR={dest}"])
        installed = True
        app = dest / "Panacea.exe"
        verify_file(app, expected, portable.stat().st_size)
        _assert_admin_directory(dest)
        _assert_admin_file(app)
        report["checks"]["protected_program_files_and_asset"] = "PASS"

        if not start_link.is_file():
            raise RuntimeError("Panacea Start Menu shortcut was not created.")
        report["checks"]["start_menu_shortcut"] = "PASS"
        verify_file(portable, expected, portable.stat().st_size)
        report["checks"]["portable_asset_not_touched"] = "PASS"

        run_checked([app, "--smoke-test"], timeout=50,
                    env={**os.environ, "PYINSTALLER_RESET_ENVIRONMENT": "1"})
        report["checks"]["packaged_gui_from_program_files"] = "PASS"

        unsafe = temp / ("panacea-portable-" + uuid.uuid4().hex)
        unsafe.mkdir()
        try:
            try:
                _assert_admin_directory(unsafe)
            except Exception:
                report["checks"]["portable_unprotected_auto_update_refused"] = "PASS"
            else:
                raise RuntimeError("User-writable temporary directory was considered protected.")
        finally:
            unsafe.rmdir()

        bad = install_verified(portable, app, "0" * 64,
                               lambda *_: (_ for _ in ()).throw(AssertionError("bad hash launched")),
                               protected=True)
        if bad.success or sha256(app) != expected:
            raise RuntimeError("Incorrect update digest was accepted.")
        report["checks"]["invalid_update_digest_blocked"] = "PASS"

        def broken_launch(_path, _token):
            raise OSError("injected launch failure")
        rollback = install_verified(portable, app, expected, broken_launch, protected=True)
        if rollback.success or not rollback.rolled_back or sha256(app) != expected:
            raise RuntimeError("Backup rollback did not protect the installed PE.")
        report["checks"]["real_installed_image_rollback"] = "PASS"

        child = None
        try:
            def launch(path, token):
                nonlocal child
                child = subprocess.Popen(
                    [str(path), "--panacea-update-ready", token],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL, cwd=str(path.parent),
                    env={**os.environ, "PYINSTALLER_RESET_ENVIRONMENT": "1"},
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                return child

            result = install_verified(portable, app, expected, launch, protected=True)
            if not result.success:
                raise RuntimeError("In-place update of installer installation failed: " + str(result.error))
            deadline = time.monotonic() + 50
            while time.monotonic() < deadline:
                if not readiness_path(app).exists() and not result.backup.exists():
                    break
                if child.poll() is not None:
                    raise RuntimeError("New packaged image exited before readiness.")
                time.sleep(0.25)
            else:
                raise RuntimeError("Installed app did not acknowledge real GUI startup.")
            verify_file(app, expected, portable.stat().st_size)
            report["checks"]["installed_exe_in_place_restart_ready"] = "PASS"
        finally:
            if child is not None and child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=5)

        matches = list(dest.glob("unins*.exe"))
        if len(matches) != 1:
            raise RuntimeError("Expected exactly one registered Inno Setup uninstaller.")
        run_checked([matches[0], "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"])
        # Inno Setup can finish cleaning its running uninstaller asynchronously.
        # Wait for actual deletion rather than treating the process exit as proof.
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if not app.exists() and (previous_link or not start_link.exists()):
                break
            time.sleep(0.25)
        if app.exists():
            raise RuntimeError("Uninstaller exited but Panacea.exe still exists: " + str(app))
        if sentinel.read_text(encoding="utf-8") != "PRESERVE":
            raise RuntimeError("Uninstaller modified an unrelated sentinel.")
        verify_file(portable, expected, portable.stat().st_size)
        if not previous_link and start_link.exists():
            raise RuntimeError("Start Menu shortcut remained after uninstall.")
        installed = False
        report["checks"]["uninstall_keeps_outside_and_portable"] = "PASS"
    finally:
        report["installation_may_remain"] = installed
        sentinel.unlink(missing_ok=True)
        # Never recursively delete Program Files entries from a test script.
        # This GitHub-hosted runner is discarded after the job.
    return report


def main():
    parser = argparse.ArgumentParser()
    for name in ("setup", "setup_checksum", "portable", "checksum", "report"):
        parser.add_argument("--" + name.replace("_", "-"), type=Path, required=True)
    args = parser.parse_args()
    report = {"status": "FAIL"}
    try:
        report = actual_install_test(args)
        report["status"] = "PASS"
    except Exception as exc:
        report["error"] = str(exc)
        report["trace"] = traceback.format_exc(limit=7)
        raise
    finally:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
