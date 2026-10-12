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
    monkeypatch.setattr(restore.subprocess, 'run', lambda *a, **k: SimpleNamespace(returncode=0, stdout='', stderr=''))
    assert subject.create_restore_point()[0] is False


def test_creation_does_not_implicitly_enable_restore(subject, monkeypatch):
    queries = iter([10, 11])
    calls = []
    monkeypatch.setattr(subject, '_get_latest_restore_point_seq', lambda: next(queries))
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
    responses = iter([
        SimpleNamespace(returncode=0, stdout='', stderr=''),
        SimpleNamespace(returncode=0, stdout='', stderr=''),
        SimpleNamespace(returncode=0, stdout='1', stderr=''),
    ])
    monkeypatch.setattr(restore.subprocess, 'run', lambda *a, **k: next(responses))
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
