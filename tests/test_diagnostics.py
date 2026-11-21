import json
from pathlib import Path
from unittest.mock import Mock
from zipfile import ZipFile

import pytest

from modules import diagnostics, history, logger
from modules.maintenance_guard import _state


@pytest.fixture
def folders(tmp_path, monkeypatch):
    local = tmp_path / "local"
    downloads = tmp_path / "downloads"
    logs = local / "Panacea" / "logs"
    logs.mkdir(parents=True)
    downloads.mkdir()
    monkeypatch.setattr(logger, "known_folder", {"local": local, "downloads": downloads}.__getitem__)
    marker = tmp_path / "install" / "Panacea.exe.update-ready.json"
    marker.parent.mkdir()
    monkeypatch.setattr(diagnostics, "_marker_path", lambda: marker)
    return logs, downloads, marker


def test_preview_is_exact_archive_and_private_fields_never_leave(folders):
    logs, downloads, marker = folders
    secret = "PRIVATE-BROWSER-TOKEN"
    private = f"C:/Users/private/Documents/{secret}"
    (marker.parent / "Panacea.exe").write_bytes(b"MZ" + secret.encode())
    marker.write_text(json.dumps({"ready": True, "protected": True, "token": secret, "backup": private,
                                 "arbitrary_key": secret}))
    (logs.parent / "settings.json").write_text(json.dumps({"autoCheck": False, "languageChoice": "it",
                                                           "releaseNotes": secret, "reduceMotion": private}))
    stamp = "2026-10-19 09:11:21,123 - "
    (logs / "panacea.log.1").write_text(stamp + "WARNING - Qt warning: " + private)
    (logs / "panacea.log").write_text(stamp + "ERROR - " + secret + "\n" + private)
    for name in ("browser.sqlite", "recent.exe", "log.txt", "crash-marker.log", "panacea.log.6"):
        (logs / name).write_text(secret)
    (logs / "crash-marker.log").write_text("Windows fatal exception: " + secret + "\n" + private)
    history.append(history.operation_record("sfc", 1, {"status": "failed", "message": secret}))
    guard = {**_state("interrupted_journal"), "message": private, "action_id": secret}
    path = diagnostics.export(guard, "en")
    assert path.parent == downloads and path.name.startswith("Panacea-diagnostics-")
    with ZipFile(path) as archive:
        assert archive.testzip() is None
        assert tuple(archive.namelist()) == diagnostics.FILES == (
            "system.json", "guard.json", "logs.txt", "history.jsonl", "update-readiness.json", "settings.json")
        assert all(secret.encode() not in archive.read(name) and private.encode() not in archive.read(name)
                   for name in archive.namelist())
        assert b"qt_warning" in archive.read("logs.txt") and b"application_event" in archive.read("logs.txt")
        assert json.loads(archive.read("history.jsonl"))["action"] == "sfc"
        assert json.loads(archive.read("system.json"))["last_crash"] == "native_fault"
        assert json.loads(archive.read("settings.json")) == {"state": "present", "language": "en",
                                                            "languageChoice": "it", "autoCheck": False}
        assert json.loads(archive.read("update-readiness.json")) == {"state": "present", "ready": True, "protected": True}
        assert json.loads(archive.read("guard.json"))["action_id"] is None


def test_hardlinked_input_is_never_opened_as_diagnostics(folders, tmp_path):
    logs, _, marker = folders
    outside = tmp_path / "other"
    outside.write_text('{"ready":true,"autoCheck":true}')
    for target in (marker, logs.parent / "settings.json", logs / "panacea.log"):
        target.hardlink_to(outside)
    with ZipFile(diagnostics.export(_state("clear"), "it")) as archive:
        assert json.loads(archive.read("update-readiness.json")) == {"state": "unavailable"}
        assert json.loads(archive.read("settings.json")) == {"state": "unavailable", "language": "it"}
        assert archive.read("logs.txt") == b"log_unavailable\n"


def test_linked_log_directory_and_foreign_zip_selection_refused(folders, tmp_path, monkeypatch):
    import os
    logs, downloads, _ = folders
    logs.rmdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "panacea.log").write_text("2026-01-01 10:00:00,000 - WARNING - Qt warning: sentinel")
    if os.name == "nt":
        from test_cleanup import _try_convert_to_junction
        logs.mkdir()
        ok, why = _try_convert_to_junction(logs, outside, 0x100)
        assert ok, why
    else:
        logs.symlink_to(outside, target_is_directory=True)
    path = diagnostics.export(_state("clear"), "it")
    with ZipFile(path) as archive:
        assert b"qt_warning" not in archive.read("logs.txt")
    start = Mock()
    resolver = Mock(return_value=str(tmp_path / "Windows/System32/explorer.exe"))
    monkeypatch.setattr(diagnostics, "system_executable", resolver)
    monkeypatch.setattr(diagnostics.subprocess, "Popen", start)
    diagnostics.reveal(path)
    resolver.assert_called_once_with("explorer.exe")
    start.assert_called_once_with([str(tmp_path / "Windows/explorer.exe"), "/select,", str(path)], shell=False)
    with pytest.raises(ValueError):
        diagnostics.reveal(downloads / "../arbitrary.exe")


def test_log_tail_and_both_zip_budgets(folders, monkeypatch):
    logs, downloads, _ = folders
    (logs / "panacea.log").write_bytes(b"2026-11-01 12:00:00,000 - INFO - anything\n" * 65000)
    path = diagnostics.export(_state("clear"), "it")
    with ZipFile(path) as archive:
        assert archive.getinfo("logs.txt").file_size <= diagnostics.LOG_BYTES
        assert sum(i.file_size for i in archive.infolist()) <= diagnostics.MAX_BYTES
    assert 0 < path.stat().st_size <= diagnostics.MAX_BYTES
    monkeypatch.setattr(diagnostics, "MAX_BYTES", 1)
    with pytest.raises(OSError):
        diagnostics.export(_state("clear"), "it")
    assert list(downloads.iterdir()) == [path]
