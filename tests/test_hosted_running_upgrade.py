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
                                    sleep=lambda _: None, timeout=30)
    assert stopped == [process]
