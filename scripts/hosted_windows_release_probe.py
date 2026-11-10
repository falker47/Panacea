"""Isolated Windows release probe: execute ONLY on a disposable GitHub-hosted runner.

This exercise uses real Win32 file handles and real packaged Panacea.exe bytes.
It never calls Turbo, Resurrection, network reset, drive optimization or SFC/DISM.
Normal UAC and the complete V2 update helper network flow remain unverified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from types import SimpleNamespace

# Direct script execution starts with scripts/ on sys.path, not the repository root.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from modules.cleanup import CleanupManager  # noqa: E402
from modules import update_install  # noqa: E402
from modules.updater import parse_checksum, verify_file  # noqa: E402


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(data)
    return value.hexdigest()


def require_disposable_runner() -> Path:
    if (os.name != "nt" or os.environ.get("GITHUB_ACTIONS") != "true"
            or os.environ.get("RUNNER_OS") != "Windows"
            or os.environ.get("PANACEA_ALLOW_HOSTED_PROBE") != "true"):
        raise RuntimeError("This test may run ONLY on an explicitly enabled GitHub-hosted Windows runner.")
    base = Path(os.environ["RUNNER_TEMP"]).resolve(strict=True)
    if len(base.parts) < 3 or str(base).lower() in {"c:\\", "d:\\"}:
        raise RuntimeError("RUNNER_TEMP must be a dedicated temporary directory, not a drive root.")
    return base


def cleanup_fixture(root: Path) -> dict:
    """Real Windows cleanup calls, but only in an isolated, explicitly approved test profile."""
    fake_profile = root / "fixture-user" / "Profile è Unicode"
    local = fake_profile / "AppData" / "Local"
    temp = local / "Temp"
    temp.mkdir(parents=True)
    keep_dir = root / "outside-temp-sentinel"
    keep_dir.mkdir()
    sentinel = keep_dir / "private-data.txt"
    sentinel.write_bytes(b"DO NOT DELETE")

    saved = {key: os.environ.get(key) for key in ("USERPROFILE", "LOCALAPPDATA", "TEMP")}
    os.environ.update({"USERPROFILE": str(fake_profile), "LOCALAPPDATA": str(local), "TEMP": str(temp)})
    try:
        manager = CleanupManager(logger=SimpleNamespace(log=lambda *args: None))
        # Suppress inspection of the runner's real Windows\\Temp. No legitimate
        # operating-system temp root outside this throwaway fixture is scanned.
        manager._windows_root = lambda: None
        assert manager.get_temp_paths() == [str(temp)], "Cleanup escaped isolated fixture root."
        nested = temp / "nested"
        nested.mkdir()
        (temp / "one.bin").write_bytes(b"abc")
        (nested / "two.bin").write_bytes(b"12345")
        assert manager.preview_temp_files() == (2, 8), manager.last_result
        assert (temp / "one.bin").read_bytes() == b"abc"
        assert (nested / "two.bin").read_bytes() == b"12345"
        assert manager.last_result.preview is True
        assert manager.clean_temp_files() == (2, 8), manager.last_result
        assert not (temp / "one.bin").exists()
        assert not (nested / "two.bin").exists()
        assert sentinel.read_bytes() == b"DO NOT DELETE"

        # Guard failures are exercised with genuine NTFS objects.
        link = temp / "hardlink.bin"
        os.link(sentinel, link)
        locked = temp / "in-use.bin"
        locked.write_bytes(b"LOCKED")
        junction = temp / "outside-junction"
        made = subprocess.run(
            ["cmd.exe", "/c", "mklink", "/J", str(junction), str(keep_dir)],
            capture_output=True, text=True, timeout=20, check=False)
        if made.returncode:
            raise RuntimeError("Could not create NTFS junction: " + made.stderr[:300])
        with locked.open("rb"):
            assert manager.clean_temp_files() == (0, 0), manager.last_result
            assert locked.read_bytes() == b"LOCKED"
        assert link.exists() and junction.exists()
        assert sentinel.read_bytes() == b"DO NOT DELETE"
        reasons = manager.last_result.skipped_counts
        assert reasons.get("hard_link", 0) >= 1, reasons
        assert sum(reasons.values()) >= 3, reasons

        # Ensure browser cache selection does not touch profile user data.
        cache_root = local / "Google" / "Chrome" / "User Data" / "Default"
        cache = cache_root / "Cache"
        cache.mkdir(parents=True)
        (cache / "cache-entry").write_bytes(b"cache")
        bookmarks = cache_root / "Bookmarks"
        bookmarks.write_bytes(b"saved-data")
        assert manager.clean_browser_caches() == (1, 5), manager.last_result
        assert bookmarks.read_bytes() == b"saved-data"
        assert sentinel.read_bytes() == b"DO NOT DELETE"
        return {"preview_files": 2, "preview_bytes": 8, "deleted_files": 2,
                "deleted_bytes": 8, "protected_guard_reasons": reasons,
                "browser_cache_entries_removed": 1, "out_of_scope_sentinel": "preserved"}
    finally:
        for key, old in saved.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old


def _kill_only_child(process):
    if process is None or process.poll() is not None:
        return
    # Kill only the PID started by THIS isolated probe and its children.
    try:
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       capture_output=True, text=True, timeout=20, check=False)
        process.wait(timeout=8)
    except (OSError, subprocess.TimeoutExpired):
        process.kill()
        process.wait(timeout=8)


def launch_visible_legacy(target: Path, *, popen=None, visible=None,
                          monotonic=time.monotonic, sleep=time.sleep, timeout=30.0):
    """Keep the genuine 2.0.2 GUI running during this *disposable* Windows swap.

    This helper is only called after require_disposable_runner() in main; never
    use it on the owner's computer. No UI buttons or maintenance are invoked.
    """
    if visible is None:
        from scripts.packaged_probe import usable_candidate_window
        visible = usable_candidate_window
    env = {**os.environ, "PYINSTALLER_RESET_ENVIRONMENT": "1"}
    process = (popen or subprocess.Popen)(
        [str(target)], cwd=str(target.parent), env=env,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = monotonic() + timeout
        while monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError("Published v2.0.2 GUI exited before the live-upgrade probe.")
            if visible(target) is not None:
                return process
            sleep(0.2)
        raise RuntimeError("Published v2.0.2 GUI did not show a visible window before upgrade.")
    except Exception:
        _kill_only_child(process)
        raise


def verified_upgrade_ready(target, result, digest, size, *, protected):
    """Use the actual updater readiness contract, not backup deletion as a proxy.

    An acknowledged new Qt image is ready even while the still-running old
    Windows image holds a mapped file handle to its recovery backup.
    """
    if protected:
        return update_install._operation_ready(target, result, digest, size)
    return not result.backup.exists() and not update_install.readiness_path(target).exists()


def real_image_replacement(root: Path, candidate: Path, legacy: Path, expected: str,
                           *, protected=False) -> dict:
    """Use actual v2.0.2 and V2 PE images; verify fail/rollback and real new boot ack."""
    if protected:
        from modules.update_install import _assert_admin_directory, _create_admin_workspace, _open_exclusive
        program_files = Path(os.environ["ProgramFiles"])
        _assert_admin_directory(program_files)
        target_dir = _create_admin_workspace(program_files)
        _assert_admin_directory(target_dir)
    else:
        target_dir = root / "portable-replacement"
        target_dir.mkdir(parents=True)
    target = target_dir / "Panacea.exe"
    started = None
    running_old = None
    try:
        if protected:
            with _open_exclusive(target, protected=True) as output:
                with legacy.open("rb") as source:
                    shutil.copyfileobj(source, output)
                output.flush()
                os.fsync(output.fileno())
        else:
            shutil.copyfile(legacy, target)
        old_sha = digest(target)
        assert old_sha == digest(legacy)
        # A candidate PE with a bad checksum must not replace old bytes.
        mismatch = update_install.install_verified(
            candidate, target, "0" * 64,
            lambda *_: (_ for _ in ()).throw(RuntimeError("must not launch")),
            protected=protected)
        assert not mismatch.success and digest(target) == old_sha, mismatch

        # Deliberate injected launch failure checks native renames + rollback.
        def cannot_launch(*_args):
            raise OSError("test-only simulated launch failure")
        failed = update_install.install_verified(
            candidate, target, expected, cannot_launch, protected=protected)
        assert not failed.success and failed.rolled_back, failed
        assert digest(target) == old_sha, "Rollback did not restore the real legacy image."
        assert not update_install.readiness_path(target).exists(), "Failed operation left an unacknowledged marker."

        if protected:
            # The actual 2.0.2 executable must still be running when the
            # in-place swap starts; this is the in-app update scenario.
            running_old = launch_visible_legacy(target)

        def launch(path, token):
            nonlocal started
            env = os.environ.copy()
            env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
            started = subprocess.Popen(
                [str(path), "--panacea-update-ready", token],
                cwd=str(path.parent), env=env, stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            return started
        installed = update_install.install_verified(
            candidate, target, expected, launch, protected=protected)
        assert installed.success, installed.error
        if running_old is not None and running_old.poll() is not None:
            raise RuntimeError("Original 2.0.2 GUI exited during live upgrade before Qt was ready.")
        deadline = time.monotonic() + 55
        acknowledged = False
        while time.monotonic() < deadline:
            if verified_upgrade_ready(target, installed, expected,
                                      candidate.stat().st_size, protected=protected):
                acknowledged = True
                break
            if started.poll() is not None:
                break
            time.sleep(0.4)
        if not acknowledged:
            marker = update_install.readiness_path(target)
            marker_ready = None
            if marker.is_file():
                try:
                    marker_ready = json.loads(marker.read_text(encoding="utf-8")).get("ready")
                except (OSError, ValueError):
                    marker_ready = "unreadable"
            raise RuntimeError("Qt startup readiness was not verified: "
                               f"marker_ready={marker_ready!r}, backup_exists={installed.backup.exists()}, "
                               f"new_process_exit={started.poll() if started else None}, "
                               f"old_process_exit={running_old.poll() if running_old else None}")
        assert digest(target) == expected
        assert installed.readiness_token
        if protected:
            # The actual production UI quits the old app after verified Qt
            # readiness. Emulate that only on this disposable runner and prove
            # the protected recovery backup can then be safely finalized.
            _kill_only_child(running_old)
            running_old = None
            if not update_install.finalize_ready(
                    target, token=installed.readiness_token, protected=True):
                raise RuntimeError("Protected old-image backup could not finalize after old GUI exit.")
            if installed.backup.exists() or update_install.readiness_path(target).exists():
                raise RuntimeError("Verified update left a backup or readiness marker after old GUI exit.")
        return {"path_mode": "protected" if protected else "portable-fixture",
                "legacy_sha256": old_sha, "candidate_sha256": expected,
                "invalid_digest_blocked": True, "launch_failure_rolled_back": True,
                "real_qt_image_started": True, "readiness_acknowledged": True,
                "old_v202_running_during_replacement": protected,
                "backup_finalized_after_old_exit": protected if protected else None}
    finally:
        _kill_only_child(started)
        _kill_only_child(running_old)
        # Only remove the uniquely created test directory on this disposable runner.
        shutil.rmtree(target_dir, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--checksum", type=Path, required=True)
    parser.add_argument("--legacy", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    base = require_disposable_runner()
    expected = parse_checksum(args.checksum.read_bytes())
    report = {"environment": "github-hosted-disposable-windows",
              "test_only": True, "source": "exact CI artifact and public v2.0.2 binary",
              "candidate_sha256": expected, "cases": {}, "unverified": [
                  "Legacy in-app v2.0.2 updater using live next-release metadata",
                  "End-to-end automatic helper re-fetch from an unpublished future release",
                  "Interactive UAC consent and refusal (hosted-runner UAC disabled)",
                  "System DPI changes, full Turbo, Resurrection and OS repairs",
                  "Long-running old image update, forced reboot and interrupted helper recovery"]}
    root = Path(tempfile.mkdtemp(prefix="panacea-disposable-probe-", dir=base))
    failure = None
    try:
        assert verify_file(args.candidate, expected, args.candidate.stat().st_size)
        legacy_sha = digest(args.legacy)
        assert verify_file(args.legacy, legacy_sha, args.legacy.stat().st_size)
        report["candidate_bytes"] = args.candidate.stat().st_size
        report["legacy_sha256"] = legacy_sha
        cases = [
            ("real_temp_cleanup_guarded", lambda: cleanup_fixture(root)),
            ("real_exe_portable_swap", lambda: real_image_replacement(
                root, args.candidate, args.legacy, expected, protected=False)),
            ("real_exe_protected_swap", lambda: real_image_replacement(
                root, args.candidate, args.legacy, expected, protected=True)),
        ]
        for name, work in cases:
            try:
                report["cases"][name] = {"status": "PASS", "evidence": work()}
                print(f"PASS: {name}", flush=True)
            except Exception as exc:
                failure = exc
                report["cases"][name] = {"status": "FAIL", "reason": str(exc),
                                          "trace": traceback.format_exc(limit=8)}
                print(f"FAIL: {name}: {exc}", flush=True)
                break
    except Exception as exc:
        failure = exc
        report["preflight_failure"] = str(exc)
    finally:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print("PROBE REPORT: " + str(args.output), flush=True)
        shutil.rmtree(root, ignore_errors=True)
    if failure:
        raise SystemExit(f"Isolated integration not yet accepted: {failure}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
