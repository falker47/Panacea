import os
import ctypes
from ctypes import wintypes
import struct
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

import modules.cleanup as cleanup


@pytest.fixture
def manager(tmp_path, monkeypatch):
    profile = tmp_path / 'profile'
    local = profile / 'AppData' / 'Local'
    temp = local / 'Temp'
    temp.mkdir(parents=True)
    monkeypatch.setenv('USERPROFILE', str(profile))
    monkeypatch.setenv('LOCALAPPDATA', str(local))
    monkeypatch.setenv('TEMP', str(temp))
    monkeypatch.setenv('SystemRoot', str(tmp_path / 'Windows'))
    monkeypatch.setattr(cleanup.CleanupManager, '_windows_root', staticmethod(lambda: str(tmp_path / 'Windows')))
    monkeypatch.setattr(cleanup, 'Logger', lambda: SimpleNamespace(log=lambda *args: None))
    return cleanup.CleanupManager(), temp


def test_unsafe_temp_root_preserves_profile_sentinel(manager, monkeypatch):
    subject, temp = manager
    profile = temp.parents[2]
    sentinel = profile / 'important.txt'
    sentinel.write_bytes(b'keep')
    monkeypatch.setenv('TEMP', str(profile))
    assert subject.clean_temp_files() == (0, 0)
    assert sentinel.read_bytes() == b'keep'
    assert subject.last_result.skipped


def test_nested_files_count_only_actual_deletions(manager):
    subject, temp = manager
    nested = temp / 'nested'
    nested.mkdir()
    (temp / 'one').write_bytes(b'123')
    (nested / 'two').write_bytes(b'12345')
    assert subject.clean_temp_files() == (2, 8)
    assert not (nested / 'two').exists()


def test_preview_reports_files_without_mutating(manager):
    subject, temp = manager
    (temp / 'one').write_bytes(b'123')
    assert callable(getattr(subject, 'preview_temp_files', None))
    assert subject.preview_temp_files() == (1, 3)
    assert (temp / 'one').read_bytes() == b'123'
    assert subject.last_result.preview


def test_junction_to_outside_preserves_sentinel(manager, tmp_path):
    subject, temp = manager
    outside = tmp_path / 'outside'
    outside.mkdir()
    sentinel = outside / 'important.txt'
    sentinel.write_bytes(b'keep')
    link = temp / 'linked'
    if os.name == 'nt':
        completed = subprocess.run(['cmd.exe', '/c', 'mklink', '/J', str(link), str(outside)], stdin=subprocess.DEVNULL, capture_output=True)
        if completed.returncode:
            pytest.skip('Fixture junction creation unavailable')
    else:
        link.symlink_to(outside, target_is_directory=True)
    assert subject.clean_temp_files() == (0, 0)
    assert sentinel.read_bytes() == b'keep'
    assert subject.last_result.skipped


def test_reparse_root_preserves_outside_sentinel(manager, tmp_path, monkeypatch):
    subject, temp = manager
    temp.rmdir()
    outside = tmp_path / 'outside'
    outside.mkdir()
    sentinel = outside / 'important.txt'
    sentinel.write_bytes(b'keep')
    if os.name == 'nt':
        completed = subprocess.run(['cmd.exe', '/c', 'mklink', '/J', str(temp), str(outside)], stdin=subprocess.DEVNULL, capture_output=True)
        if completed.returncode:
            pytest.skip('Fixture junction creation unavailable')
    else:
        temp.symlink_to(outside, target_is_directory=True)
    assert subject.clean_temp_files() == (0, 0)
    assert sentinel.read_bytes() == b'keep'


def test_locked_file_is_skipped_and_not_counted(manager):
    subject, temp = manager
    target = temp / 'locked'
    target.write_bytes(b'keep')
    if os.name != 'nt':
        pytest.skip('Windows deny-delete file sharing behavior')
    with target.open('rb'):
        assert subject.clean_temp_files() == (0, 0)
        assert target.read_bytes() == b'keep'
    assert subject.last_result.skipped


def test_browser_cleanup_only_touches_explicit_cache(manager):
    subject, temp = manager
    profile = temp.parent / 'Google' / 'Chrome' / 'User Data' / 'Default'
    cache = profile / 'Cache'
    cache.mkdir(parents=True)
    (cache / 'entry').write_bytes(b'123')
    sentinel = profile / 'Bookmarks'
    sentinel.write_bytes(b'keep')
    assert subject.clean_browser_caches() == (1, 3)
    assert sentinel.read_bytes() == b'keep'


@pytest.mark.parametrize('vendor,browser', [('Google', 'Chrome'), ('Microsoft', 'Edge')])
def test_browser_cleanup_includes_numbered_profiles_and_preserves_user_data(manager, vendor, browser):
    subject, temp = manager
    user_data = temp.parent / vendor / browser / 'User Data'
    profile = user_data / 'Profile 2'
    cache = profile / 'Code Cache'
    cache.mkdir(parents=True)
    (cache / 'entry').write_bytes(b'12345')
    sentinel = profile / 'Login Data'
    sentinel.write_bytes(b'keep')
    other = user_data / 'Unrecognized Data' / 'Cache'
    other.mkdir(parents=True)
    (other / 'keep').write_bytes(b'keep')
    assert subject.clean_browser_caches() == (1, 5)
    assert not (cache / 'entry').exists()
    assert sentinel.read_bytes() == b'keep'
    assert (other / 'keep').read_bytes() == b'keep'


def test_browser_unknown_profile_location_is_not_reported_as_success(manager, monkeypatch):
    subject, _ = manager
    monkeypatch.delenv('LOCALAPPDATA')
    assert subject.clean_browser_caches() == (0, 0)
    assert not subject.last_result.ok


def test_temp_preview_counts_case_variant_root_only_once(manager, monkeypatch):
    subject, temp = manager
    (temp / 'one').write_bytes(b'123')
    # Model USER TEMP pointing at the Windows Temp root with different spelling.
    monkeypatch.setattr(subject, '_windows_root', lambda: str(temp.parent))
    monkeypatch.setenv('TEMP', str(temp).upper())
    assert subject.preview_temp_files() == (1, 3)
    assert (temp / 'one').read_bytes() == b'123'


def test_missing_temp_environment_still_previews_known_user_temp(manager, monkeypatch):
    subject, temp = manager
    (temp / 'one').write_bytes(b'123')
    monkeypatch.delenv('TEMP')
    assert subject.preview_temp_files() == (1, 3)


@pytest.mark.parametrize('items,query_code,success', [(1, 0, False), (0, 0, True), (0, -1, False)])
def test_unexpected_recycle_error_requires_verified_empty_bin(manager, monkeypatch, items, query_code, success):
    subject, _ = manager
    def query(root, info_pointer):
        info = info_pointer._obj
        info.i64NumItems = items
        return query_code
    shell = SimpleNamespace(SHEmptyRecycleBinW=lambda *args: -2147418113, SHQueryRecycleBinW=query)
    monkeypatch.setattr(cleanup.ctypes, 'windll', SimpleNamespace(shell32=shell))
    assert subject.empty_recycle_bin()[0] is success


def test_multiply_linked_file_preserves_outside_sentinel(manager, tmp_path):
    subject, temp = manager
    sentinel = tmp_path / 'important.txt'
    sentinel.write_bytes(b'keep')
    os.link(sentinel, temp / 'linked-file')
    assert subject.clean_temp_files() == (0, 0)
    assert sentinel.read_bytes() == b'keep'
    assert (temp / 'linked-file').exists()
    assert subject.last_result.skipped


def test_directory_rename_is_blocked_while_files_are_deleted(manager, monkeypatch):
    subject, temp = manager
    nested = temp / 'nested'
    nested.mkdir()
    (nested / 'one').write_bytes(b'123')
    original = subject._delete_file
    attempted = []
    def race(path, preview):
        try:
            nested.rename(temp / 'moved')
        except OSError:
            attempted.append('blocked')
        return original(path, preview)
    monkeypatch.setattr(subject, '_delete_file', race)
    assert subject.clean_temp_files() == (1, 3), (subject.last_result, attempted, (temp / 'moved').exists())
    assert attempted == ['blocked']
    assert not (temp / 'moved').exists()


def _try_convert_to_junction(directory, target, desired_access=0x40000000):
    """Fixture-only native conversion of an existing empty directory."""
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.DeviceIoControl.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID,
                                      wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
                                      ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateFileW(str(directory), desired_access, 7, None, 3, 0x02200000, None)
    if handle == wintypes.HANDLE(-1).value:
        return False, ctypes.get_last_error()
    try:
        substitute = ('\\??\\' + str(target)).encode('utf-16-le')
        printable = str(target).encode('utf-16-le')
        paths = substitute + b'\x00\x00' + printable + b'\x00\x00'
        data = struct.pack('<IHHHHHH', 0xA0000003, 8 + len(paths), 0,
                           0, len(substitute), len(substitute) + 2, len(printable)) + paths
        buffer = ctypes.create_string_buffer(data)
        returned = wintypes.DWORD()
        success = bool(kernel.DeviceIoControl(handle, 0x900A4, buffer, len(data), None, 0,
                                             ctypes.byref(returned), None))
        return success, 0 if success else ctypes.get_last_error()
    finally:
        kernel.CloseHandle(handle)


def test_inplace_junction_conversion_is_blocked_by_live_directory_guard(manager, tmp_path):
    subject, temp = manager
    outside = tmp_path / 'outside'
    outside.mkdir()
    sentinel = outside / 'sentinel.txt'
    sentinel.write_bytes(b'keep')
    control = tmp_path / 'control'
    control.mkdir()
    converted, error = _try_convert_to_junction(control, outside)
    assert converted, f'Fixture conversion control failed: {error}'
    assert [entry.name for entry in control.iterdir()] == ['sentinel.txt']
    guarded = temp / 'guarded'
    guarded.mkdir()
    with cleanup._guard_path(guarded):
        converted, error = _try_convert_to_junction(guarded, outside)
        assert converted is False
        assert error == 32  # FILE_SHARE_WRITE denied while the guard is held.
        assert list(guarded.iterdir()) == []
    assert sentinel.read_bytes() == b'keep'


def test_inplace_junction_conversion_is_blocked_during_preview(manager, tmp_path, monkeypatch):
    subject, temp = manager
    outside = tmp_path / 'outside'
    outside.mkdir()
    sentinel = outside / 'sentinel.txt'
    sentinel.write_bytes(b'keep')
    guarded = temp / 'guarded'
    guarded.mkdir()
    (temp / 'allowed.txt').write_bytes(b'123')
    original = subject._walk_directory
    attempts = []
    def race(directory, preview, callback):
        if Path(directory) == guarded:
            attempts.append(_try_convert_to_junction(guarded, outside))
        return original(directory, preview, callback)
    monkeypatch.setattr(subject, '_walk_directory', race)
    assert subject.preview_temp_files() == (1, 3)
    assert attempts == [(False, 32)]
    assert (temp / 'allowed.txt').read_bytes() == b'123'
    assert sentinel.read_bytes() == b'keep'


@pytest.mark.parametrize('desired_access', [0, 0x80, 0x100, 0x10, 0x2, 0x4, 0x10000, 0x40000000])
def test_alternate_reparse_access_masks_never_escape_live_guard(tmp_path, desired_access):
    # Both endpoints and the sentinel are disposable fixture paths. No deletion.
    outside = tmp_path / 'outside'
    outside.mkdir()
    sentinel = outside / 'sentinel.txt'
    sentinel.write_bytes(b'keep')
    control = tmp_path / 'control'
    control.mkdir()
    control_success, control_error = _try_convert_to_junction(control, outside, desired_access)
    guarded = tmp_path / 'guarded'
    guarded.mkdir()
    with cleanup._guard_path(guarded):
        success, error = _try_convert_to_junction(guarded, outside, desired_access)
        if success:
            # Attribute-only opens cannot be excluded by share flags. The invariant
            # is that no redirected object can be accepted for a deletion handle.
            with pytest.raises(cleanup.UnsafePath):
                with cleanup._windows_handle(guarded / 'sentinel.txt', delete=True):
                    pass
        else:
            assert error in (5, 32), f'Unexpected rejection {error}, control={control_success}/{control_error}'
            assert list(guarded.iterdir()) == []
    assert sentinel.read_bytes() == b'keep'


@pytest.mark.parametrize('preview', [True, False])
def test_attribute_conversion_during_enumeration_cannot_delete_or_count_outside(manager, tmp_path, monkeypatch, preview):
    subject, temp = manager
    outside = tmp_path / 'outside'
    outside.mkdir()
    sentinel = outside / 'sentinel.txt'
    sentinel.write_bytes(b'keep')
    guarded = temp / 'race'
    guarded.mkdir()
    (temp / 'allowed.txt').write_bytes(b'123')
    original_scandir = cleanup.os.scandir
    conversions = []
    def racing_scandir(path, *args, **kwargs):
        if Path(path) == guarded and not conversions:
            conversions.append(_try_convert_to_junction(guarded, outside, 0x100))
        return original_scandir(path, *args, **kwargs)
    monkeypatch.setattr(cleanup.os, 'scandir', racing_scandir)
    count, size = subject.preview_temp_files() if preview else subject.clean_temp_files()
    assert conversions == [(True, 0)]
    assert count == 1 and size == 3
    assert sentinel.read_bytes() == b'keep'
    assert subject.last_result.skipped or subject.last_result.errors


@pytest.mark.parametrize('returned_length', [0, 32768])
def test_unverifiable_final_path_fails_closed(manager, monkeypatch, returned_length):
    subject, temp = manager
    sentinel = temp / 'keep.txt'
    sentinel.write_bytes(b'keep')
    original = cleanup._kernel_api
    def unavailable():
        kernel = original()
        kernel.GetFinalPathNameByHandleW = lambda *args: returned_length
        return kernel
    monkeypatch.setattr(cleanup, '_kernel_api', unavailable)
    assert subject.clean_temp_files() == (0, 0)
    assert sentinel.read_bytes() == b'keep'
    assert subject.last_result.skipped


def test_case_sensitive_directory_refused_before_case_folded_binding(manager):
    subject, temp = manager
    kernel = cleanup._kernel_api()
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    handle = kernel.CreateFileW(str(temp), 0x100, 7, None, 3, 0x02000000, None)
    assert handle != wintypes.HANDLE(-1).value
    try:
        flags = wintypes.DWORD(1)
        assert kernel.SetFileInformationByHandle(handle, 23, ctypes.byref(flags), ctypes.sizeof(flags)), ctypes.get_last_error()
    finally:
        kernel.CloseHandle(handle)
    (temp / 'Keep.txt').write_bytes(b'keep')
    assert subject.clean_temp_files() == (0, 0)
    assert (temp / 'Keep.txt').read_bytes() == b'keep'
    assert any('Case-sensitive' in item for item in subject.last_result.skipped)


def test_ordinary_mixed_case_names_remain_supported(manager):
    subject, temp = manager
    nested = temp / 'MixedCase'
    nested.mkdir()
    (nested / 'Sample.TXT').write_bytes(b'123')
    assert subject.clean_temp_files() == (1, 3)


def test_firefox_profile_discovery_rejects_live_attribute_retarget(manager, tmp_path, monkeypatch):
    subject, temp = manager
    profiles = temp.parent / 'Mozilla' / 'Firefox' / 'Profiles'
    profiles.mkdir(parents=True)
    outside = tmp_path / 'outside'
    cache = outside / 'foreign' / 'cache2'
    cache.mkdir(parents=True)
    sentinel = cache / 'keep.txt'
    sentinel.write_bytes(b'keep')
    original = cleanup.os.listdir
    attempts = []
    def retarget(path):
        if Path(path) == profiles and not attempts:
            attempts.append(_try_convert_to_junction(profiles, outside, 0x100))
        return original(path)
    monkeypatch.setattr(cleanup.os, 'listdir', retarget)
    assert subject.clean_browser_caches() == (0, 0)
    assert attempts == [(True, 0)]
    assert sentinel.read_bytes() == b'keep'
    assert subject.last_result.skipped


@pytest.mark.parametrize('preview', [False, True])
def test_live_nonempty_ancestor_cannot_be_made_case_sensitive(manager, monkeypatch, preview):
    subject, temp = manager
    original_file = temp / 'sentinel.txt'
    original_file.write_bytes(b'123')
    original_delete = subject._delete_file
    attempts = []
    def retarget(path, dry_run):
        kernel = cleanup._kernel_api()
        kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                      wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        kernel.CreateFileW.restype = wintypes.HANDLE
        handle = kernel.CreateFileW(str(temp.parent), 0x100, 7, None, 3, 0x02000000, None)
        assert handle != wintypes.HANDLE(-1).value
        try:
            flags = wintypes.DWORD(1)
            success = bool(kernel.SetFileInformationByHandle(handle, 23, ctypes.byref(flags), ctypes.sizeof(flags)))
            attempts.append((success, 0 if success else ctypes.get_last_error()))
        finally:
            kernel.CloseHandle(handle)
        # ERROR_DIR_NOT_EMPTY: an ancestor contains its continuously held child.
        assert attempts == [(False, 145)]
        return original_delete(path, dry_run)
    monkeypatch.setattr(subject, '_delete_file', retarget)
    result = subject.preview_temp_files() if preview else subject.clean_temp_files()
    assert attempts == [(False, 145)], subject.last_result
    assert result == (1, 3)
    assert original_file.exists() is preview
