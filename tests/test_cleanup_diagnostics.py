"""Cleanup contracts using disposable paths only; no host cache is visited."""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path

import pytest

import modules.cleanup as cleanup
from test_cleanup import _try_convert_to_junction, manager  # noqa: F401


def test_confirmed_direct_cleanup_is_one_pass_without_preview(manager, monkeypatch):
    subject, temp = manager
    nested = temp / 'nested'
    nested.mkdir()
    (temp / 'one').write_bytes(b'abc')
    (nested / 'two').write_bytes(b'12345')
    def no_preview(*args, **kwargs):
        raise AssertionError('Direct cleanup must not run a pre-scan')
    monkeypatch.setattr(subject, 'preview_temp_files', no_preview)
    visited = []
    real_scandir = cleanup.os.scandir
    def scan(path):
        visited.append(Path(path))
        return real_scandir(path)
    monkeypatch.setattr(cleanup.os, 'scandir', scan)
    assert subject.clean_temp_files() == (2, 8)
    assert visited == [temp, nested]
    assert subject.last_result.ok
    assert not subject.last_result.preview


def test_clean_reexamines_changed_files_after_read_only_preview(manager):
    subject, temp = manager
    changed = temp / 'changed'
    removed = temp / 'removed'
    changed.write_bytes(b'12')
    removed.write_bytes(b'123')
    assert subject.preview_temp_files() == (2, 5)
    preview_result = subject.last_result
    assert changed.read_bytes() == b'12'
    assert removed.read_bytes() == b'123'
    changed.write_bytes(b'1234567')
    removed.unlink()
    (temp / 'added').write_bytes(b'1234')
    assert subject.clean_temp_files() == (2, 11)
    assert subject.last_result is not preview_result
    assert (preview_result.count, preview_result.bytes, preview_result.preview) == (2, 5, True)
    assert list(temp.iterdir()) == []


def test_preview_does_not_authorize_a_later_hardlink_replacement(manager, tmp_path):
    subject, temp = manager
    candidate = temp / 'candidate'
    candidate.write_bytes(b'123')
    assert subject.preview_temp_files() == (1, 3)
    candidate.unlink()
    sentinel = tmp_path / 'important'
    sentinel.write_bytes(b'keep')
    os.link(sentinel, candidate)
    assert subject.clean_temp_files() == (0, 0)
    assert sentinel.read_bytes() == b'keep'
    assert candidate.exists()
    assert subject.last_result.skipped_counts == {'hard_link': 1}


def test_native_locked_file_gives_provable_reason_and_preserves_full_detail(manager):
    subject, temp = manager
    locked = temp / 'locked'
    locked.write_bytes(b'keep')
    (temp / 'eligible').write_bytes(b'12345')
    with locked.open('rb'):
        assert subject.clean_temp_files() == (1, 5)
    result = subject.last_result
    assert not result.ok
    assert result.skipped_counts == {'locked': 1}
    assert result.error_counts == {}
    issue, = result.issues
    assert issue.kind == 'skipped'
    assert issue.reason == 'locked'
    assert issue.winerror == 32
    assert issue.path == str(locked)
    assert issue.detail == result.skipped[0]
    assert str(locked) in issue.detail
    assert locked.read_bytes() == b'keep'


def test_preview_skips_exclusively_open_file_and_changes_nothing(manager):
    subject, temp = manager
    target = temp / 'locked'
    target.write_bytes(b'keep')
    (temp / 'eligible').write_bytes(b'12345')
    kernel = cleanup._kernel_api()
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    handle = kernel.CreateFileW(str(target), 0x80000000, 0, None, 3, 0x80, None)
    assert handle != wintypes.HANDLE(-1).value
    try:
        assert subject.preview_temp_files() == (1, 5)
        assert subject.last_result.skipped_counts == {'locked': 1}
        assert subject.last_result.issues[0].winerror == 32
        assert not subject.last_result.ok
    finally:
        kernel.CloseHandle(handle)
    assert target.read_bytes() == b'keep'
    assert (temp / 'eligible').read_bytes() == b'12345'


def test_reparse_diagnostic_preserves_outside_sentinel(manager, tmp_path):
    subject, temp = manager
    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'sentinel').write_bytes(b'keep')
    link = temp / 'linked'
    link.mkdir()
    created, error = _try_convert_to_junction(link, outside)
    assert created, error
    assert subject.clean_temp_files() == (0, 0)
    assert subject.last_result.skipped_counts == {'reparse_point': 1}
    assert subject.last_result.issues[0].path == str(link)
    assert (outside / 'sentinel').read_bytes() == b'keep'


def test_unexpected_file_error_preserves_other_completed_deletions(manager, monkeypatch):
    subject, temp = manager
    good = temp / 'eligible'
    bad = temp / 'unexpected'
    good.write_bytes(b'12345')
    bad.write_bytes(b'keep')
    real_delete = subject._delete_file
    def delete(path, preview):
        if Path(path) == bad:
            raise RuntimeError('Fixture transport failure')
        return real_delete(path, preview)
    monkeypatch.setattr(subject, '_delete_file', delete)
    assert subject.clean_temp_files() == (1, 5)
    assert subject.last_result.error_counts == {'unexpected_error': 1}
    assert subject.last_result.issues[0].detail == subject.last_result.errors[0]
    assert not subject.last_result.ok
    assert not good.exists()
    assert bad.read_bytes() == b'keep'


@pytest.mark.parametrize('code,reason', [(5, 'access_denied'), (32, 'locked'), (33, 'locked'),
                                      (2, 'disappeared'), (1117, 'filesystem_error')])
def test_native_error_code_controls_reason_not_localized_message(manager, monkeypatch, code, reason):
    subject, temp = manager
    target = temp / 'not-deleted'
    target.write_bytes(b'keep')
    error = ctypes.WinError(code)
    def rejected(*args):
        raise error
    monkeypatch.setattr(subject, '_delete_file', rejected)
    assert subject.clean_temp_files() == (0, 0)
    result = subject.last_result
    assert result.skipped_counts == {reason: 1}
    assert result.issues[0].winerror == code
    assert str(error) in result.issues[0].detail
    assert target.read_bytes() == b'keep'


def test_unapproved_root_has_explicit_reason_and_original_diagnostic(manager, monkeypatch):
    subject, temp = manager
    monkeypatch.setenv('TEMP', str(temp.parent))
    assert subject.clean_temp_files() == (0, 0)
    assert subject.last_result.skipped_counts == {'unapproved_root': 1}
    assert subject.last_result.issues[0].detail == subject.last_result.skipped[0]


def test_directory_enumeration_failure_is_error_and_not_an_invented_file_count(manager, monkeypatch):
    subject, temp = manager
    (temp / 'keep').write_bytes(b'123')
    def denied(path):
        raise ctypes.WinError(5)
    monkeypatch.setattr(cleanup.os, 'scandir', denied)
    assert subject.clean_temp_files() == (0, 0)
    result = subject.last_result
    assert not result.ok
    assert result.skipped_counts == {}
    assert result.error_counts == {'access_denied': 1}
    assert result.issues[0].kind == 'error'
    assert (temp / 'keep').read_bytes() == b'123'


def test_preview_progress_reports_real_candidates_and_never_claims_deletion(manager):
    subject, temp = manager
    for index in range(101):
        (temp / str(index)).write_bytes(b'123')
    messages = []
    assert subject.preview_temp_files(progress_callback=messages.append) == (101, 303)
    assert str(temp) in messages[0]
    assert messages[1:] == ['Found 50 eligible files...', 'Found 100 eligible files...']
    assert all('Deleted' not in message for message in messages)
    assert len(list(temp.iterdir())) == 101
    assert subject.last_result.preview


def test_progress_callback_failure_preserves_real_result_and_error_diagnostic(manager):
    subject, temp = manager
    (temp / 'one').write_bytes(b'123')
    def broken(message):
        raise RuntimeError('Fixture progress observer failed')
    assert subject.clean_temp_files(progress_callback=broken) == (1, 3)
    assert not (temp / 'one').exists()
    result = subject.last_result
    assert not result.ok
    assert result.error_counts == {'progress_callback': 1}
    assert 'Fixture progress observer failed' in result.errors[0]


@pytest.mark.parametrize('preview', [False, True])
def test_absent_approved_temp_root_is_empty_no_op(manager, preview):
    subject, temp = manager
    temp.rmdir()
    assert (subject.preview_temp_files() if preview else subject.clean_temp_files()) == (0, 0)
    assert subject.last_result.ok
    assert not temp.exists()


def test_unknown_temp_locations_do_not_report_successful_empty_cleanup(manager, monkeypatch):
    subject, _ = manager
    monkeypatch.delenv('TEMP')
    monkeypatch.delenv('LOCALAPPDATA')
    monkeypatch.setattr(subject, '_windows_root', lambda: None)
    assert subject.clean_temp_files() == (0, 0)
    assert not subject.last_result.ok
    assert subject.last_result.skipped_counts == {'location_unavailable': 1}


def test_legacy_string_diagnostics_keep_unknown_counts_without_guessing():
    result = cleanup.CleanupResult(skipped=['could be locked, but no error code'], errors=['legacy error'])
    assert result.skipped_counts == {'unknown': 1}
    assert result.error_counts == {'unknown': 1}
