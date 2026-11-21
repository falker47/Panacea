import os
import threading
import subprocess
import sys

import pytest

from modules import history, logger
from modules import maintenance_guard as guards

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Uses the same native Windows fixtures as PR 16")


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setattr(logger, "known_folder", lambda _: tmp_path)
    boot = [101]
    guard = guards.MaintenanceGuard(tmp_path / "Panacea/maintenance-guard", lambda: f"windows-boot-id:{boot[0]}")
    return guard, boot


def test_clear_same_boot_previous_boot_verify_and_known_action(state):
    guard, boot = state
    assert guard.status()["code"] == "clear"
    with guard.operation() as permit:
        permit.describe("sfc")
        guard.mark_unknown()
    before = guard.status()
    assert (before["code"], before["action_id"], before["resolution"]) == (
        "unknown_completion_same_boot", "sfc", "restart_windows")
    assert before["since"] and not before["safe_to_clear"]
    assert guards.MaintenanceGuard(guard.state_path, guard._boot_identity).status()["action_id"] == "sfc"
    assert guard.verify_again() == before
    with pytest.raises(ValueError):
        guard.archive(before)
    boot[0] += 1
    state = guard.status()
    assert state["code"] == "unknown_completion_previous_boot" and state["safe_to_clear"]
    assert guard.state_path.exists()
    assert guard.verify_again()["code"] == "clear"
    assert not guard.is_blocked()
    assert any(guard.state_path.parent.glob("maintenance-archive-*"))


def test_interrupted_and_unverifiable_preserve_evidence_including_after_audit_failure(state, monkeypatch):
    guard, _ = state
    journal = guard._journal().state_path
    journal.mkdir(parents=True)
    assert guard.status()["code"] == "interrupted_journal"
    guard.state_path.mkdir()
    (guard.state_path / "unknown.json").write_bytes(b"damaged")
    assert guard.status()["code"] == "unverifiable_storage"
    assert not guard.verify_again()["safe_to_clear"]
    with monkeypatch.context() as local:
        def fail(row):
            raise OSError("Fixture disk full")
        local.setattr(history, "append", fail)
        with pytest.raises(OSError, match="Fixture disk full"):
            guard.archive(guard.status())
    assert guard.is_blocked()
    reopened = guards.MaintenanceGuard(guard.state_path, guard._boot_identity)
    assert reopened.is_blocked()
    assert reopened.archive(reopened.status())["code"] == "clear"
    archive, = guard.state_path.parent.glob("maintenance-archive-*")
    assert (archive / guard.state_path.name / "unknown.json").read_bytes() == b"damaged"
    assert (archive / journal.name).is_dir()
    assert history.page()["items"][0]["action"] == "archive_guard"


def test_recovery_refuses_changed_state_and_busy_owner(state):
    guard, _ = state
    guard._journal().state_path.mkdir(parents=True)
    preview = guard.status()
    running, finish = threading.Event(), threading.Event()
    def owner():
        with guards._maintenance_mutex(0):
            running.set()
            finish.wait(5)
    thread = threading.Thread(target=owner)
    thread.start()
    try:
        assert running.wait(3)
        assert guard.status()["code"] == "busy_other_instance"
        with pytest.raises(TimeoutError):
            guard.archive(preview)
    finally:
        finish.set()
        thread.join()
    assert guard.mark_unknown()
    with pytest.raises(ValueError):
        guard.archive(preview)
    assert not list(guard.state_path.parent.glob("maintenance-archive-*"))


def test_no_archive_through_junction(state, tmp_path):
    from test_cleanup import _try_convert_to_junction
    guard, _ = state
    guard.state_path.mkdir(parents=True)
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    ok, reason = _try_convert_to_junction(guard.state_path, outside, 0x100)
    assert ok, reason
    state = guard.status()
    assert state["code"] == "unverifiable_storage"
    with pytest.raises(OSError):
        guard.archive(state)
    assert guard.is_blocked()
    assert list(outside.iterdir()) == []


def test_second_process_cannot_archive_while_owner_holds_mutex(state):
    import json
    guard, _ = state
    guard._journal().state_path.mkdir(parents=True)
    snapshot = guard.status()
    script = """
import json, sys
from pathlib import Path
from modules import logger
from modules.maintenance_guard import MaintenanceGuard
path = Path(sys.argv[1])
logger.known_folder = lambda name: path.parent.parent
guard = MaintenanceGuard(path, lambda: "windows-boot-id:101")
assert guard.status()["code"] == "busy_other_instance"
try:
    guard.archive(json.loads(sys.argv[2]))
except TimeoutError:
    pass
else:
    raise AssertionError("Recovery acquired an occupied mutex")
"""
    with guards._maintenance_mutex(0):
        child = subprocess.run([sys.executable, "-c", script, str(guard.state_path), json.dumps(snapshot)],
                               capture_output=True, text=True, timeout=10)
    assert child.returncode == 0, child.stderr
    assert guard.status() == snapshot
    assert not (guard.state_path.parent / "maintenance-recovery-pending").exists()


def test_bad_advisory_action_never_changes_journal_decision(state):
    guard, boot = state
    with guard.operation() as permit:
        permit.describe("sfc")
    metadata = guard.state_path.parent / "maintenance-action.json"
    metadata.write_bytes(b"broken")
    reopened = guards.MaintenanceGuard(guard.state_path, guard._boot_identity)
    assert reopened.status()["code"] == "interrupted_journal"
    assert reopened.status()["action_id"] is None
    boot[0] += 1
    assert reopened.verify_again()["code"] == "clear"


def test_rollback_of_boot_counter_is_unverifiable_and_never_auto_clears(state):
    guard, boot = state
    assert guard.mark_unknown()
    boot[0] -= 1
    for subject in (guard, guards.MaintenanceGuard(guard.state_path, guard._boot_identity)):
        assert subject.status()["code"] == "unverifiable_storage"
        assert subject.verify_again()["blocked"]
