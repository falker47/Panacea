import ctypes
from ctypes import wintypes
import json
import re
from types import SimpleNamespace

import pytest

import modules.restore as restore


@pytest.fixture
def subject(monkeypatch):
    monkeypatch.setattr(restore, 'Logger', lambda: SimpleNamespace(log=lambda *args: None))
    return restore.RestoreManager()


@pytest.mark.parametrize('sequences', [[None, None], [None, 2], [1, None], [3, 3], [4, 3]])
def test_unverified_restore_point_never_succeeds(subject, monkeypatch, sequences):
    queries = iter(sequences)
    monkeypatch.setattr(subject, '_get_latest_restore_point_seq', lambda: next(queries))
    monkeypatch.setattr(subject, '_find_created_restore_point', lambda before, description: next(queries))
    monkeypatch.setattr(restore.subprocess, 'run', lambda *a, **k: SimpleNamespace(returncode=0, stdout='', stderr=''))
    assert subject.create_restore_point()[0] is False


def test_creation_does_not_implicitly_enable_restore(subject, monkeypatch):
    queries = iter([10, 11])
    calls = []
    monkeypatch.setattr(subject, '_get_latest_restore_point_seq', lambda: next(queries))
    monkeypatch.setattr(subject, '_find_created_restore_point', lambda before, description: 11)
    def run(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout='', stderr='')
    monkeypatch.setattr(restore.subprocess, 'run', run)
    assert subject.create_restore_point("Panacea's safe point")[0]
    assert len(calls) == 1
    assert 'Enable-ComputerRestore' not in calls[0][-1]
    assert "Panacea''s safe point" in calls[0][-1]


def test_enable_validates_drive_and_checks_exit(subject, monkeypatch):
    calls = []
    def run(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=1, stdout='', stderr='denied')
    monkeypatch.setattr(restore.subprocess, 'run', run)
    assert subject.ensure_restore_enabled("C:\\'; whoami; '") is False
    assert calls == []
    assert subject.ensure_restore_enabled('C:\\') is False


def test_empty_successful_query_can_verify_first_restore_point(subject, monkeypatch):
    created = []
    def run(args, **kwargs):
        script = args[-1]
        output = ''
        if 'Checkpoint-Computer' in script:
            created.append(re.search(r"-Description '([^']*)'", script).group(1))
        elif 'ConvertTo-Json' in script:
            output = json.dumps({'SequenceNumber': 1, 'Description': created[0]})
        return SimpleNamespace(returncode=0, stdout=output, stderr='')
    monkeypatch.setattr(restore.subprocess, 'run', run)
    assert subject.create_restore_point()[0]


def test_failed_sequence_query_does_not_attempt_creation(subject, monkeypatch):
    calls = []
    def denied(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=1, stdout='', stderr='denied')
    monkeypatch.setattr(restore.subprocess, 'run', denied)
    assert subject.create_restore_point()[0] is False
    assert len(calls) == 1
    assert 'Checkpoint-Computer' not in calls[0][-1]


def test_unrelated_concurrent_restore_point_cannot_satisfy_checkpoint(subject, monkeypatch):
    query_count = 0
    def run(args, **kwargs):
        nonlocal query_count
        script = args[-1]
        if 'Checkpoint-Computer' in script:
            return SimpleNamespace(returncode=0, stdout='', stderr='')
        if 'ExpandProperty SequenceNumber' in script:
            query_count += 1
            return SimpleNamespace(returncode=0, stdout='10' if query_count == 1 else '11', stderr='')
        return SimpleNamespace(returncode=0, stdout=json.dumps({'SequenceNumber': 11, 'Description': 'Unrelated installer'}), stderr='')
    monkeypatch.setattr(restore.subprocess, 'run', run)
    assert subject.create_restore_point('Panacea safe checkpoint')[0] is False


def test_restore_checkpoint_is_verified_by_unique_description_and_new_sequence(subject, monkeypatch):
    created = []
    def run(args, **kwargs):
        script = args[-1]
        if 'Checkpoint-Computer' in script:
            match = re.search(r"-Description '((?:[^']|'')*)'", script)
            created.append(match.group(1).replace("''", "'"))
            return SimpleNamespace(returncode=0, stdout='', stderr='')
        if 'ExpandProperty SequenceNumber' in script:
            return SimpleNamespace(returncode=0, stdout='10', stderr='')
        return SimpleNamespace(returncode=0, stdout=json.dumps([
            {'SequenceNumber': 11, 'Description': created[-1]},
            {'SequenceNumber': 12, 'Description': 'Unrelated installer'},
        ]), stderr='')
    monkeypatch.setattr(restore.subprocess, 'run', run)
    assert subject.create_restore_point("Panacea's checkpoint")[0] is True
    assert subject.create_restore_point("Panacea's checkpoint")[0] is True
    assert len(created) == 2 and created[0] != created[1]
    assert all("Panacea's checkpoint" in name and len(name) <= 256 for name in created)


def test_powershell_output_preserves_unicode_for_checkpoint_identity(subject):
    # Native fixture prints two characters only; no restore or host setting APIs.
    result = subject._run_powershell("Write-Output ([string][char]0x6b63 + [string][char]0x5e38)", timeout=10)
    assert result.returncode == 0
    assert result.stdout.strip() == '正常'


def test_powershell_runs_with_invalid_windowed_app_stdin(subject):
    # Simulate a --windowed EXE without a console, then restore this test's handle.
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetStdHandle.argtypes = [wintypes.DWORD]
    kernel.GetStdHandle.restype = wintypes.HANDLE
    kernel.SetStdHandle.argtypes = [wintypes.DWORD, wintypes.HANDLE]
    kernel.SetStdHandle.restype = wintypes.BOOL
    stdin_id = wintypes.DWORD(-10)
    original = kernel.GetStdHandle(stdin_id)
    try:
        assert kernel.SetStdHandle(stdin_id, wintypes.HANDLE(-1))
        result = subject._run_powershell("Write-Output 'fixture-only'", timeout=10)
        assert result.returncode == 0
        assert result.stdout.strip() == 'fixture-only'
    finally:
        assert kernel.SetStdHandle(stdin_id, original)
