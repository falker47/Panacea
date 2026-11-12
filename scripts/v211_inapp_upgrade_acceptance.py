"""Actual old-GUI update acceptance against published v2.1.1, isolated Windows ONLY.

This performs no maintenance commands. It installs a public stable version into
a unique protected Program Files folder on a disposable GitHub-hosted runner,
checks the exact published frozen updater metadata, and clicks the OLD GUI's
verified-update control and its own confirmation dialog. No arbitrary desktop
clicks, no personal PC, no silent approval. PR #9 supplies the pinned 2.0.2
label-matching helper and reference image; it is never merged or modified here.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
import uuid
import winreg

from PIL import ImageGrab

from modules.updater import parse_checksum, verify_file
from scripts.build_installer import validate_setup
from scripts.hosted_installer_probe import disposable_guard, run_checked
from scripts.hosted_windows_release_probe import _kill_only_child, launch_visible_legacy
from scripts.packaged_probe import usable_candidate_window


REPO = "falker47/Panacea"
NEW_TAG = "v2.1.1"
NEW_VERSION = "2.1.1"
OLD_VERSIONS = ("2.0.2", "2.1.0")
APP_KEY = (r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
           r"\{B6C0FB10-27BC-4E6F-9078-40F9E8B49B2D}_is1")


def _clean_host():
    temp, program_files = disposable_guard()
    if os.environ.get("RUNNER_ENVIRONMENT") != "github-hosted":
        raise RuntimeError("Exact disposable hosted runner is required")
    for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, APP_KEY, 0, winreg.KEY_READ | view):
                raise RuntimeError("Runner is not clean: existing Panacea installed")
        except FileNotFoundError:
            continue
    return temp, program_files


def _registration():
    for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, APP_KEY, 0, winreg.KEY_READ | view) as key:
                return (Path(winreg.QueryValueEx(key, "InstallLocation")[0]),
                        winreg.QueryValueEx(key, "DisplayVersion")[0])
        except FileNotFoundError:
            continue
    return None


def _download(tag: str, folder: Path, *, include_setup=False):
    folder.mkdir(parents=True, exist_ok=False)
    args = ["gh", "release", "download", tag, "--repo", REPO,
            "--pattern", "Panacea.exe", "--pattern", "Panacea.exe.sha256"]
    if include_setup:
        args += ["--pattern", "PanaceaSetup.exe", "--pattern", "PanaceaSetup.exe.sha256"]
    run_checked(args + ["--dir", str(folder)], timeout=150)
    executable = folder / "Panacea.exe"
    digest = parse_checksum((folder / "Panacea.exe.sha256").read_bytes())
    verify_file(executable, digest, executable.stat().st_size)
    if include_setup:
        setup = folder / "PanaceaSetup.exe"
        setup_digest = (folder / "PanaceaSetup.exe.sha256").read_text(encoding="ascii").split()[0].lower()
        if validate_setup(setup) != setup_digest:
            raise RuntimeError("Public installer checksum mismatch")
    return digest


def _historical_reference(root: Path):
    reference = root / "build" / "recovery-reference"
    script = reference / "scripts" / "hosted_updater_recovery.py"
    fixture = reference / "tests" / "fixtures" / "v202_install_update.png"
    if not script.is_file() or not fixture.is_file():
        raise RuntimeError("Pinned PR #9 historical script/fixture is missing")
    spec = importlib.util.spec_from_file_location("_pinned_historical_recovery", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _click_native_confirmation(target: Path, evidence: Path, *, timeout=35):
    user = ctypes.WinDLL("user32", use_last_error=True)
    user.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    user.FindWindowW.restype = wintypes.HWND
    user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user.GetWindowThreadProcessId.restype = wintypes.DWORD
    user.GetDlgItem.argtypes = [wintypes.HWND, ctypes.c_int]
    user.GetDlgItem.restype = wintypes.HWND
    user.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user.PostMessageW.restype = wintypes.BOOL
    owner = usable_candidate_window(target)
    if not owner:
        raise RuntimeError("Original installed GUI is not visible before confirmation")
    pid = owner["pid"]
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        dialog = user.FindWindowW("#32770", "Install verified update")
        if dialog:
            actual = wintypes.DWORD()
            user.GetWindowThreadProcessId(dialog, ctypes.byref(actual))
            if actual.value != pid:
                raise RuntimeError("Update confirmation belongs to an unexpected process")
            yes = user.GetDlgItem(dialog, 6)
            if not yes:
                raise RuntimeError("Exact verified-update Yes control is absent")
            ImageGrab.grab().save(evidence / "confirmation.png")
            if not user.PostMessageW(yes, 0x00F5, 0, 0):
                raise RuntimeError("Could not confirm the owned native update dialog")
            return
        time.sleep(0.3)
    ImageGrab.grab().save(evidence / "confirmation-unmatched.png")
    raise RuntimeError("Expected old-GUI native update confirmation did not appear")


def _click_qt_update(target: Path, evidence: Path):
    from pywinauto import Desktop

    owner = usable_candidate_window(target)
    if not owner:
        raise RuntimeError("Qt production window is not visible")
    pid = owner["pid"]
    desktop = Desktop(backend="uia")
    deadline = time.monotonic() + 90
    clicked_check = False
    observed = set()
    while time.monotonic() < deadline:
        window = desktop.window(process=pid, title_re=r"^Panacea 2\.1\.0")
        if not window.exists(timeout=1):
            time.sleep(0.3)
            continue
        buttons = []
        for item in window.descendants():
            try:
                name = item.element_info.name
                if item.element_info.control_type == "Button" and item.is_visible():
                    buttons.append((name, item))
            except Exception:
                continue
        observed.update(name for name, _ in buttons)
        installs = [item for name, item in buttons if name == "Install verified update"]
        if len(installs) == 1:
            ImageGrab.grab().save(evidence / "qt-update-offered.png")
            installs[0].click_input()
            _click_native_confirmation(target, evidence)
            return {"observed_buttons": sorted(observed), "used_accessibility": True}
        if not clicked_check and time.monotonic() + 50 >= deadline:
            checks = [item for name, item in buttons if name == "Check updates"]
            if len(checks) == 1:
                checks[0].click_input()
                clicked_check = True
        time.sleep(0.5)
    ImageGrab.grab().save(evidence / "qt-update-not-found.png")
    raise RuntimeError("Could not identify exact accessible Qt Install verified update button: "
                       + repr(sorted(observed)))


def _wait_for_new_version(target: Path, old_process, new_digest: str, new_size: int,
                          evidence: Path):
    deadline = time.monotonic() + 240
    states = []
    observed = None
    while time.monotonic() < deadline:
        paths = list(target.parent.glob("panacea-update-*/status.json"))
        if paths:
            if len(paths) != 1:
                raise RuntimeError("Ambiguous concurrent update helpers")
            try:
                current = json.loads(paths[0].read_text(encoding="utf-8"))
            except (ValueError, OSError):
                time.sleep(0.25)
                continue
            if current != observed:
                states.append(current)
                observed = current
                print("Update helper:", current, flush=True)
            if current.get("status") == "failed":
                raise RuntimeError("Protected helper failed: " + str(current.get("message")))
            if current.get("status") == "ready" and old_process.poll() is not None:
                verify_file(target, new_digest, new_size)
                result = usable_candidate_window(target)
                if result:
                    ImageGrab.grab().save(evidence / "updated-desktop.png")
                    return states, result
        time.sleep(0.4)
    ImageGrab.grab().save(evidence / "upgrade-timeout.png")
    raise RuntimeError("Old GUI did not exit and show verified 2.1.1 after readiness: "
                       + repr(observed))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--old-version", choices=OLD_VERSIONS, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = {"scenario": args.old_version + " -> " + NEW_VERSION,
              "runner": "disposable Windows, actual published binaries and old-GUI clicks",
              "result": "FAIL", "unsupported_claims": [
                  "interactive UAC consent on owner device", "abrupt power loss",
                  "GPD Win Mini physical installation and runtime"]}
    started = None
    args.report.parent.mkdir(parents=True, exist_ok=True)
    evidence = args.report.parent / ("screens-" + args.old_version)
    evidence.mkdir(exist_ok=True)
    try:
        temp, program_files = _clean_host()
        root = Path(__file__).resolve().parents[1]
        ref = _historical_reference(root)
        bundle = temp / ("Panacea-inapp-QA-" + uuid.uuid4().hex)
        bundle.mkdir()
        new_dir, old_dir = bundle / "new", bundle / "old"
        new_digest = _download(NEW_TAG, new_dir, include_setup=True)
        old_digest = _download("v" + args.old_version, old_dir, include_setup=True)
        report["published_sha256"] = {"old": old_digest, "new": new_digest}
        new_exe = new_dir / "Panacea.exe"
        # Verify actual bytecode embedded in each released executable before UI automation.
        _, client = ref.packaged_client(old_dir / "Panacea.exe", args.old_version, old_digest)
        offered = client.check()   # Actual public releases/latest metadata.
        if offered is None or offered.version != NEW_VERSION:
            raise RuntimeError("Old published client did not discover v2.1.1 live")
        if client.fetch_checksum(offered) != new_digest:
            raise RuntimeError("Old packaged updater did not trust the published digest")
        report["live_release_discovered"] = offered.version

        install_dir = program_files / ("Panacea-InApp-QA-" + uuid.uuid4().hex)
        if install_dir.exists():
            raise RuntimeError("Fresh protected install path collision")
        run_checked([old_dir / "PanaceaSetup.exe", "/SP-", "/VERYSILENT", "/SUPPRESSMSGBOXES",
                     "/NORESTART", "/NOCLOSEAPPLICATIONS", "/LANG=english",
                     "/DIR=" + str(install_dir)], timeout=160)
        target = install_dir / "Panacea.exe"
        verify_file(target, old_digest, (old_dir / "Panacea.exe").stat().st_size)
        if _registration() != (install_dir, args.old_version):
            raise RuntimeError("Original stable installer AppId/registration mismatch")

        started = launch_visible_legacy(target, timeout=90)
        if args.old_version == "2.0.2":
            ref.confirm_update(target, evidence)
            report["gui_control"] = "verified 2.0.2 image-matched button + native Yes"
        else:
            report["gui_control"] = _click_qt_update(target, evidence)
        states, visible = _wait_for_new_version(target, started, new_digest,
                                               new_exe.stat().st_size, evidence)
        _, installed = ref.packaged_client(target, NEW_VERSION, new_digest)
        if installed.check() is not None:
            raise RuntimeError("2.1.1 still offers the same already-installed release")
        if _registration() != (install_dir, args.old_version):
            raise RuntimeError("Original installed AppId/path was changed by EXE-only update")
        report["states"] = states
        report["new_visible_window"] = visible
        report["same_app_id_and_directory"] = True
        report["new_sha256_verified"] = True
        report["no_repeat_offer"] = True
        report["result"] = "PASS"
        print("PASS: Real old GUI initiated and completed verified update to v2.1.1", flush=True)
    except Exception as exc:
        report["error"] = str(exc)
        report["trace"] = traceback.format_exc(limit=12)
        raise
    finally:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        if started is not None:
            _kill_only_child(started)
        # Do not recursively delete protected files; VM is discarded after the job.


if __name__ == "__main__":
    main()
