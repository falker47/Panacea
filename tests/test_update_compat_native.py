"""Read helper telemetry without launching a process, importing PYZ code, or installing."""

import pytest

from scripts.update_compat.installed import check_status


def transitions(names, times):
    return [{"status": name, "at": at} for name, at in zip(names.split(), times, strict=True)]


def test_ack_budget_excludes_preparation_and_accepts_at_most_15_seconds():
    events = transitions("preparing installing waiting_ready ready", [0, 100, 102, 115])
    report = {}
    check_status("good", {"status": "ready"}, events, 0, report)
    assert report["install_to_ready_seconds"] == 15
    events[-1]["at"] += 0.001
    with pytest.raises(RuntimeError, match="15 second"):
        check_status("good", {"status": "ready"}, events, 0, report)
    assert report["install_to_ready_seconds"] > 15


@pytest.mark.parametrize(("case", "names", "message"), [
    ("exit", "preparing installing failed", "The new application exited before it acknowledged readiness."),
    ("exit", "preparing installing waiting_ready failed", "The new application exited before startup readiness."),
    ("timeout", "preparing installing waiting_ready failed", "The new application did not acknowledge startup readiness in time."),
])
def test_rollback_requires_expected_failure_and_sequence(case, names, message):
    events = transitions(names, range(len(names.split())))
    state = {"status": "failed", "message": message}
    check_status(case, state, events, 1, {})
    with pytest.raises(RuntimeError, match="rollback reason"):
        check_status(case, {**state, "message": "Permission denied"}, events, 1, {})
    with pytest.raises(RuntimeError, match="sequence"):
        check_status(case, state, events[1:], 1, {})
    with pytest.raises(RuntimeError, match="failed status"):
        check_status(case, state, events, 0, {})
