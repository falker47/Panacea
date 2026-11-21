"""History and the maintenance finally boundary, using only fixture backends."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from modules import history, logger
from qt_app.maintenance import MaintenanceService


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(logger, "known_folder", lambda name: tmp_path)
    return tmp_path / "Panacea"


def record(action="temp_clean"):
    return history.operation_record(action, 1, {"status": "completed", "success": True, "count": 3,
                                              "bytes": 42, "message": "private-path"})


def test_read_only_missing_then_durable_record(root):
    assert history.page()["items"] == []
    assert not root.exists()
    row = record()
    history.append(row)
    assert history.page()["items"] == [row]
    assert row["app_version"] and row["bytes"] == 42 and row["count"] == 3
    assert b"private-path" not in (root / "history.jsonl").read_bytes()


def test_real_rotation_boundary_and_filter_across_generations(root):
    import json
    root.mkdir()
    old, current = record(), record("sfc")
    old["status"] = "partial"
    (root / "history.jsonl").write_bytes((json.dumps(old).encode() + b"\n") * 2000)
    history.append(current)
    assert history.MAX_ENTRIES == 2000
    assert len((root / "history.1.jsonl").read_bytes().splitlines()) == 2000
    assert history.page(0, 2)["items"] == [current, old]
    assert history.page(1999, 8, "partial") == {"items": [old], "total": 2000, "corrupt": 0,
                                                "has_more": False, "unavailable": False}


def test_torn_and_corrupt_lines_do_not_hide_later_records(root):
    root.mkdir()
    path = root / "history.jsonl"
    path.write_bytes(b"\xff\n" + b"x" * 3000 + b"\n" + b'{"broken"')
    row = record()
    history.append(row)
    assert history.page()["corrupt"] == 3
    assert history.page()["items"] == [row]


def test_concurrent_appends_survive_rotation(root, monkeypatch):
    monkeypatch.setattr(history, "MAX_ENTRIES", 12)
    rows = [record() for _ in range(24)]
    with ThreadPoolExecutor(max_workers=5) as executor:
        list(executor.map(history.append, rows))
    page = history.page(0, 50)
    assert {item["id"] for item in page["items"]} == {row["id"] for row in rows}
    assert page["corrupt"] == 0


@contextmanager
def lease():
    yield SimpleNamespace(resolve=lambda: None)


@pytest.mark.parametrize("fault", ["operation_record", "append"])
@pytest.mark.parametrize("backend_fails", [True, False])
def test_history_fault_never_changes_result_or_exception(root, monkeypatch, fault, backend_fails):
    guard = SimpleNamespace(operation=lease)
    service = MaintenanceService(factories={"guard": lambda: guard}, platform="nt", is_admin=lambda: True)
    outcome = {"status": "partial", "success": False, "bytes": 3}
    original_error = RuntimeError("fixture original")
    monkeypatch.setattr(service, "_dispatch", Mock(return_value=outcome, side_effect=original_error if backend_fails else None))
    monkeypatch.setattr(history, fault, Mock(side_effect=BaseException("fixture audit fault")))
    nonce = service.prepare("temp_clean")["nonce"]
    if backend_fails:
        with pytest.raises(RuntimeError) as error:
            service.execute(nonce)
        assert error.value is original_error
    else:
        assert service.execute(nonce) is outcome
        assert outcome == {"status": "partial", "success": False, "bytes": 3}
    assert not service._active
    assert getattr(history, fault).called


def test_error_and_restart_history_record_omit_messages(root, monkeypatch):
    service = MaintenanceService(platform="nt", is_admin=lambda: False)
    with pytest.raises(PermissionError):
        service.execute(service.prepare("sfc")["nonce"])
    row = history.page()["items"][0]
    assert (row["error_code"], row["success"]) == ("permission_denied", False)
    restart = history.operation_record("sfc", 2, {"status": "unknown", "success": False})
    assert restart["restart_required"] and restart["error_code"] == "completion_unknown"


def test_independent_writers_create_and_append_without_loss(root):
    import subprocess
    import sys
    script = """
import sys
from pathlib import Path
from modules import logger, history
logger.known_folder = lambda _: Path(sys.argv[1])
for _ in range(6):
    history.append(history.operation_record("sfc", 1, {"status": "completed", "success": True}))
"""
    children = [subprocess.Popen([sys.executable, "-c", script, str(root.parent)],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(3)]
    for child in children:
        _, err = child.communicate(timeout=15)
        assert child.returncode == 0, err
    result = history.page()
    assert result["corrupt"] == 0 and len({r["id"] for r in result["items"]}) == 18


def test_dispatch_exception_keeps_unverified_outcome_and_original_error(root, monkeypatch):
    guard = SimpleNamespace(operation=lease)
    service = MaintenanceService(factories={"guard": lambda: guard}, platform="nt", is_admin=lambda: True)
    original = OSError("private fixture path")
    monkeypatch.setattr(service, "_dispatch", Mock(side_effect=original))
    with pytest.raises(OSError) as error:
        service.execute(service.prepare("sfc")["nonce"])
    assert error.value is original
    row, = history.page()["items"]
    assert row["status"] == "unknown" and row["restart_required"]
    assert row["error_code"] == "storage_unavailable" and not row["success"]
