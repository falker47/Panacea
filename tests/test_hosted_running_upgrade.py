"""Inert tests of the disposable-runner-only live v2.0.2 upgrade probe."""
from pathlib import Path
from types import SimpleNamespace
import pytest

from scripts import hosted_windows_release_probe as probe


class FakeProcess:
    def __init__(self):
        self.kill_count = 0
    def poll(self):
        return None


def test_live_upgrade_probe_starts_exact_original_exe_without_hiding_its_window(tmp_path):
    target = tmp_path / "Panacea.exe"
    target.write_bytes(b"fake-process-only")
    process = FakeProcess()
    called = []
    def fake_popen(argv, **kwargs):
        called.append((argv, kwargs))
        return process
    instance = probe.launch_visible_legacy(target, popen=fake_popen,
                                           visible=lambda _: {"pid": 1234},
                                           monotonic=lambda: 0,
                                           sleep=lambda _: None)
    assert instance is process
    assert called[0][0] == [str(target)]
    assert called[0][1]["cwd"] == str(target.parent)
    assert called[0][1].get("startupinfo") is None


def test_live_upgrade_probe_does_not_leave_process_running_on_timeout(tmp_path, monkeypatch):
    target = tmp_path / "Panacea.exe"
    process = FakeProcess()
    stopped = []
    monkeypatch.setattr(probe, "_kill_only_child", lambda p: stopped.append(p))
    with pytest.raises(RuntimeError, match="visible|window"):
        probe.launch_visible_legacy(target, popen=lambda *_a, **_k: process,
                                    visible=lambda _: None,
                                    monotonic=lambda: 31,
                                    sleep=lambda _: None, timeout=0)
    assert stopped == [process]


def test_durable_ready_marker_counts_as_success_while_old_executable_is_locked(tmp_path, monkeypatch):
    # The old running Windows image can keep its backup locked even after
    # the new Qt application has durably acknowledged the update.
    from types import SimpleNamespace
    from modules import update_install
    target = tmp_path / "Panacea.exe"
    backup = tmp_path / "old-backup.exe"
    backup.write_bytes(b"old-image-mapped")
    result = SimpleNamespace(backup=backup, readiness_token="a" * 64)
    calls = []
    monkeypatch.setattr(update_install, "_operation_ready",
                        lambda target, result, digest, size: calls.append((target, result, digest, size)) or True)
    assert probe.verified_upgrade_ready(target, result, "b" * 64, 200, protected=True)
    assert backup.exists()
    assert calls == [(target, result, "b" * 64, 200)]


def test_portable_upgrade_probe_still_requires_finalized_backup_and_marker(tmp_path):
    from types import SimpleNamespace
    from modules import update_install
    target = tmp_path / "Panacea.exe"
    backup = tmp_path / "Panacea.exe.old"
    backup.write_bytes(b"keep")
    result = SimpleNamespace(backup=backup)
    assert not probe.verified_upgrade_ready(target, result, "c" * 64, 200, protected=False)
    backup.unlink()
    assert probe.verified_upgrade_ready(target, result, "c" * 64, 200, protected=False)
