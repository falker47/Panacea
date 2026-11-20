"""Exercise same-runner sampling with synthetic rows. No executable is launched."""
import json
from pathlib import Path
import sys
from unittest.mock import Mock, call

import pytest

from scripts import packaged_probe as probe


CANDIDATE = Path("candidate/Panacea.exe")
BASELINE = Path("v2.1.1/Panacea.exe")
PATHS = {"candidate": CANDIDATE, "v2.1.1": BASELINE}


def row(seconds, **changes):
    return {"mapped_window_seconds": seconds, "window": {"pid": 8100, "client_pixels": [1020, 680]},
            "gui_peak_working_set_bytes": 135544832, "loader_peak_working_set_bytes": 9027584,
            "total_smoke_seconds": 32.611, "exit_code": 0, **changes}


def fake_samples(monkeypatch, candidate, baseline):
    rows = {CANDIDATE: iter(candidate), BASELINE: iter(baseline)}
    smoke = Mock(side_effect=lambda path: next(rows[path]).copy())
    monkeypatch.setattr(probe, "smoke_sample", smoke)
    report = {"runs": {label: {"samples": []} for label in PATHS}, "baseline_anomalies": []}
    return smoke, report


def test_baseline_flake_recovers_inside_its_slot_and_preserves_full_row(monkeypatch):
    anomaly = row(15.674296500000082, exit_code=1)
    candidates = [row(2.242), row(2.252), row(2.246)]
    smoke, report = fake_samples(monkeypatch, candidates, [row(5.77), row(7.63), anomaly, row(6.42)])

    probe.measure_startup(PATHS, 3, report)

    assert smoke.call_args_list == [call(path) for path in (
        CANDIDATE, BASELINE, BASELINE, CANDIDATE, CANDIDATE, BASELINE, BASELINE)]
    assert report["baseline_anomalies"] == [{**anomaly, "sample": 3, "attempt": 1}]
    baseline = report["runs"]["v2.1.1"]
    assert len(baseline["samples"]) == 3
    assert baseline["samples"][-1]["attempt"] == 2
    assert baseline["median_mapped_window_seconds"] == 6.42
    assert report["runs"]["candidate"]["median_mapped_window_seconds"] == 2.246
    assert report["comparison"]["passed"] is True


def test_two_retries_and_three_valid_slots_are_sufficient(monkeypatch):
    no_window = row(None, window=None)
    no_memory = row(1, gui_peak_working_set_bytes=None)
    bad = row(0.01, exit_code=1, gui_peak_working_set_bytes=999999999)
    # Slots one and two are exhausted. Slot three recovers on its last allowed attempt.
    smoke, report = fake_samples(monkeypatch, [row(2)] * 5,
                                 [bad] * 6 + [no_window, no_memory, row(8), row(4), row(6)])

    probe.measure_startup(PATHS, 5, report)

    baseline = report["runs"]["v2.1.1"]
    assert [(r["sample"], r["attempt"]) for r in baseline["samples"]] == [(3, 3), (4, 1), (5, 1)]
    assert baseline["median_mapped_window_seconds"] == 6
    assert baseline["peak_working_set_bytes"] == 135544832
    assert len(report["baseline_anomalies"]) == 8
    assert report["baseline_anomalies"][-2:] == [
        {**no_window, "sample": 3, "attempt": 1}, {**no_memory, "sample": 3, "attempt": 2}]
    assert smoke.call_args_list.count(call(CANDIDATE)) == 5
    assert report["comparison"]["passed"] is True


@pytest.mark.parametrize("valid_count", [0, 2])
def test_unstable_baseline_is_inconclusive_after_all_candidate_samples(monkeypatch, valid_count):
    bad = row(1, exit_code=1)
    smoke, report = fake_samples(monkeypatch, [row(2)] * 5, [row(6)] * valid_count + [bad] * ((5 - valid_count) * 3))

    with pytest.raises(RuntimeError, match=r"(?i)inconclusive.*baseline was unstable"):
        probe.measure_startup(PATHS, 5, report)

    assert smoke.call_args_list.count(call(CANDIDATE)) == 5
    assert [(r["sample"], r["attempt"]) for r in report["baseline_anomalies"]] == [
        (sample, attempt) for sample in range(valid_count + 1, 6) for attempt in (1, 2, 3)]
    assert report["runs"]["candidate"]["median_mapped_window_seconds"] == 2
    assert report["runs"]["v2.1.1"].get("median_mapped_window_seconds") is None
    assert report["comparison"]["result"] == "inconclusive"
    assert report["comparison"]["passed"] is False
    assert report["comparison"]["valid_baseline_samples"] == valid_count
    assert "candidate_to_baseline_ratio" not in report["comparison"]


@pytest.mark.parametrize("bad", [
    row(2, exit_code=1), row(2, window=None), row(2, window={}), row(None), row(2, gui_peak_working_set_bytes=0),
])
def test_invalid_candidate_fails_immediately_without_retry(monkeypatch, bad):
    smoke, report = fake_samples(monkeypatch, [row(2), bad], [row(4), row(4)])

    with pytest.raises(RuntimeError, match="candidate failed native smoke sample 2"):
        probe.measure_startup(PATHS, 5, report)

    assert smoke.call_args_list == [call(CANDIDATE), call(BASELINE), call(BASELINE), call(CANDIDATE)]
    assert report["runs"]["candidate"]["samples"][-1]["sample"] == 2
    assert report["baseline_anomalies"] == []
    assert "comparison" not in report


def test_ratio_above_budget_still_fails_after_baseline_retry(monkeypatch):
    _, report = fake_samples(monkeypatch, [row(11.01)] * 3, [row(50, exit_code=1)] + [row(10)] * 3)

    with pytest.raises(RuntimeError, match="exceeds 110%"):
        probe.measure_startup(PATHS, 3, report)

    assert report["comparison"]["maximum_ratio"] == 1.1
    assert report["comparison"]["candidate_to_baseline_ratio"] == pytest.approx(1.101)
    assert report["comparison"]["passed"] is False


def test_candidate_only_cli_keeps_single_sample_report(tmp_path, monkeypatch):
    candidate = tmp_path / "fixture.bin"
    candidate.write_bytes(b"inert test data")
    output = tmp_path / "packaged.json"
    monkeypatch.setattr(probe, "smoke_sample", lambda _: row(1.5))
    monkeypatch.setattr(sys, "argv", ["probe", "--exe", str(candidate), "--output", str(output), "--samples", "1"])

    probe.main()

    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["samples"] == report["runs"]["candidate"]["samples"]
    assert report["median_mapped_window_seconds"] == 1.5
    assert report["baseline_anomalies"] == []
    assert "comparison" not in report
