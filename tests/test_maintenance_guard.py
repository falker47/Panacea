import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

import modules.maintenance_guard as guard


BOOT_A = 'windows-boot-id:101'
BOOT_B = 'windows-boot-id:102'


def test_absent_marker_creates_nothing_and_never_queries_boot(tmp_path):
    path = tmp_path / 'Panacea' / 'maintenance-guard'
    def unexpected_query():
        raise AssertionError('No marker means no boot query is needed')
    subject = guard.MaintenanceGuard(path, unexpected_query)
    assert not subject.is_blocked()
    assert subject.last_error == ''
    assert list(tmp_path.iterdir()) == []


def test_timeout_marker_survives_new_manager_and_requires_different_boot(tmp_path):
    path = tmp_path / 'Panacea' / 'maintenance-guard'
    assert guard.MaintenanceGuard(path, lambda: BOOT_A).mark_unknown()
    same_boot = guard.MaintenanceGuard(path, lambda: BOOT_A)
    assert same_boot.is_blocked()
    assert 'restart' in same_boot.last_error.lower()
    assert not guard.MaintenanceGuard(path, lambda: BOOT_B).is_blocked()
    assert guard.MaintenanceGuard(path, lambda: BOOT_B).mark_unknown()
    assert guard.MaintenanceGuard(path, lambda: BOOT_B).is_blocked()


def test_unknown_boot_at_timeout_never_becomes_proof_of_reboot(tmp_path):
    path = tmp_path / 'guard'
    def denied():
        raise OSError('Boot provider denied access')
    assert guard.MaintenanceGuard(path, denied).mark_unknown()
    assert guard.MaintenanceGuard(path, lambda: BOOT_B).is_blocked()
    assert guard.MaintenanceGuard(path, lambda: BOOT_B).mark_unknown()
    assert guard.MaintenanceGuard(path, lambda: BOOT_B).is_blocked()


@pytest.mark.parametrize('payload', [b'', b'{incomplete', b'[]', b'{"version":9}', b'x' * 5000])
def test_unverifiable_existing_marker_blocks_without_mutation(tmp_path, payload):
    path = tmp_path / 'guard'
    path.mkdir()
    marker = path / 'unknown.json'
    marker.write_bytes(payload)
    subject = guard.MaintenanceGuard(path, lambda: BOOT_B)
    assert subject.is_blocked()
    assert subject.last_error
    assert marker.read_bytes() == payload


@pytest.mark.parametrize('error', [subprocess.TimeoutExpired('read-only boot query', 5),
                                 FileNotFoundError('PowerShell unavailable')])
def test_boot_query_failure_does_not_clear_valid_marker(tmp_path, error):
    path = tmp_path / 'guard'
    assert guard.MaintenanceGuard(path, lambda: BOOT_A).mark_unknown()
    def unavailable():
        raise error
    subject = guard.MaintenanceGuard(path, unavailable)
    assert subject.is_blocked()
    assert subject.last_error


def test_concurrent_writers_preserve_same_boot_and_unknown_records(tmp_path):
    path = tmp_path / 'guard'
    assert guard.MaintenanceGuard(path, lambda: None).mark_unknown()
    def writer(index):
        query = (lambda: BOOT_A) if index % 2 else (lambda: None)
        return guard.MaintenanceGuard(path, query).mark_unknown()
    with ThreadPoolExecutor(max_workers=4) as workers:
        results = list(workers.map(writer, range(8)))
    assert any(results)
    subject = guard.MaintenanceGuard(path, lambda: BOOT_B)
    assert subject.is_blocked()
    records = [json.loads(item.read_text()) for item in path.iterdir()]
    assert {'version': 1, 'boot_id': None} in records
    assert {'version': 1, 'boot_id': BOOT_A} in records


def test_interrupted_write_leaves_fail_closed_record(tmp_path, monkeypatch):
    path = tmp_path / 'guard'
    def interrupted(*args):
        raise OSError('Fixture interrupted before payload flush')
    monkeypatch.setattr(guard, 'write_bytes', interrupted)
    subject = guard.MaintenanceGuard(path, lambda: BOOT_A)
    assert not subject.mark_unknown()
    assert subject.is_blocked()
    assert guard.MaintenanceGuard(path, lambda: BOOT_B).is_blocked()


def test_incomplete_guard_directory_blocks_without_querying_boot(tmp_path):
    path = tmp_path / 'guard'
    path.mkdir()
    subject = guard.MaintenanceGuard(path, lambda: BOOT_B)
    assert subject.is_blocked()


def test_failure_after_directory_creation_keeps_reopened_app_blocked(tmp_path, monkeypatch):
    path = tmp_path / 'guard'
    real_handle = guard.relative_handle
    @contextmanager
    def denied_file(parent, name, directory=False):
        if not directory:
            raise PermissionError('Fixture marker creation denied')
        with real_handle(parent, name, directory=True) as opened:
            yield opened
    monkeypatch.setattr(guard, 'relative_handle', denied_file)
    assert not guard.MaintenanceGuard(path, lambda: BOOT_A).mark_unknown()
    assert path.is_dir() and not list(path.iterdir())
    assert guard.MaintenanceGuard(path, lambda: BOOT_B).is_blocked()


def test_new_process_reads_persisted_timeout_marker(tmp_path):
    path = tmp_path / 'guard'
    assert guard.MaintenanceGuard(path, lambda: BOOT_A).mark_unknown()
    script = ('import sys; from modules.maintenance_guard import MaintenanceGuard; '
              'print(MaintenanceGuard(sys.argv[1], lambda: sys.argv[2]).is_blocked())')
    result = subprocess.run([sys.executable, '-c', script, str(path), BOOT_A],
                            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=10,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'True'


def test_junction_parent_blocks_and_never_writes_outside(tmp_path):
    from test_cleanup import _try_convert_to_junction
    parent = tmp_path / 'parent'
    outside = tmp_path / 'outside'
    parent.mkdir()
    outside.mkdir()
    success, error = _try_convert_to_junction(parent, outside, 0x100)
    assert success, error
    subject = guard.MaintenanceGuard(parent / 'guard', lambda: BOOT_A)
    assert subject.is_blocked()
    assert not subject.mark_unknown()
    assert list(outside.iterdir()) == []


def test_marker_hardlink_is_refused_and_target_preserved(tmp_path):
    path = tmp_path / 'guard'
    path.mkdir()
    target = tmp_path / 'outside.json'
    payload = b'{"version":1,"boot_id":null}'
    target.write_bytes(payload)
    (path / 'unknown.json').hardlink_to(target)
    subject = guard.MaintenanceGuard(path, lambda: BOOT_A)
    assert subject.is_blocked()
    assert not subject.mark_unknown()
    assert target.read_bytes() == payload


def test_boot_query_uses_documented_counter_read_only(monkeypatch):
    captured = []
    class Key:
        def __enter__(self): return self
        def __exit__(self, *args): return False
    def open_key(*args):
        captured.append(args)
        return Key()
    registry = SimpleNamespace(HKEY_LOCAL_MACHINE=1, KEY_READ=2, KEY_WOW64_64KEY=4, REG_DWORD=4,
                               OpenKey=open_key, QueryValueEx=lambda *args: (101, 4))
    monkeypatch.setitem(sys.modules, 'winreg', registry)
    assert guard.windows_boot_identity() == BOOT_A
    assert captured == [(1, r'SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management\PrefetchParameters', 0, 6)]
    for value, kind in [('101', 4), (True, 4), (-1, 4), (2 ** 32, 4), (101, 1)]:
        registry.QueryValueEx = lambda *args: (value, kind)
        with pytest.raises(ValueError):
            guard.windows_boot_identity()


def test_counter_rollback_does_not_count_as_verified_reboot(tmp_path):
    path = tmp_path / 'guard'
    assert guard.MaintenanceGuard(path, lambda: BOOT_B).mark_unknown()
    assert guard.MaintenanceGuard(path, lambda: BOOT_A).is_blocked()


def test_legacy_wall_clock_marker_cannot_automatically_clear(tmp_path):
    import hashlib
    path = tmp_path / 'guard'
    path.mkdir()
    timestamp = '2026-10-13T01:02:03.1234567Z'
    name = 'boot-' + hashlib.sha256(timestamp.encode('ascii')).hexdigest() + '.json'
    (path / name).write_text(json.dumps({'version': 1, 'boot_id': timestamp}))
    assert guard.MaintenanceGuard(path, lambda: '2026-10-14T01:02:03.1234567Z').is_blocked()
