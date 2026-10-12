import json
import os
import subprocess
import threading
import time
import sys
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

import modules.performance as performance
import modules.protected_files as protected_files
from test_cleanup import _try_convert_to_junction


CUSTOM_GUID = '12345678-1111-2222-3333-123456789abc'
REAL_RUN_CMD = performance.PerformanceManager._run_cmd


@pytest.fixture
def environment(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    monkeypatch.setattr(performance, 'Logger', lambda: SimpleNamespace(log=lambda *args: None))
    machine = {'power': CUSTOM_GUID, 'SysMain': False, 'WSearch': True, 'Spooler': True, 'visual': 3}
    calls = []
    def command(self, cmd, hide=True):
        args = cmd.split() if isinstance(cmd, str) else list(cmd)
        calls.append(args)
        tool = args[0].lower().rsplit('\\', 1)[-1].removesuffix('.exe')
        if tool == 'powercfg' and args[1] == '/getactivescheme':
            return True, 'Power Scheme GUID: ' + machine['power']
        if tool == 'powercfg' and args[1] == '/setactive':
            machine['power'] = args[2]
            return True, ''
        if tool == 'sc' and args[1] == 'query':
            return True, 'STATE : 4 RUNNING' if machine[args[2]] else 'STATE : 1 STOPPED'
        if tool == 'sc' and args[1] in ('start', 'stop'):
            machine[args[2]] = args[1] == 'start'
            return True, ''
        raise AssertionError(f'Unexpected OS command: {args}')
    monkeypatch.setattr(performance.PerformanceManager, '_run_cmd', command)
    key = SimpleNamespace(__enter__=lambda self: self, __exit__=lambda *args: None)
    class RegistryKey:
        def __enter__(self): return self
        def __exit__(self, *args): return False
    registry = SimpleNamespace(HKEY_CURRENT_USER=1, KEY_SET_VALUE=2, REG_DWORD=4,
        OpenKey=lambda *a: RegistryKey(),
        QueryValueEx=lambda *a: (machine['visual'], 4),
        SetValueEx=lambda key, name, zero, kind, value: machine.__setitem__('visual', value))
    monkeypatch.setitem(sys.modules, 'winreg', registry)
    return machine, calls, tmp_path


def test_custom_power_plan_restored_after_restart(environment):
    machine, calls, _ = environment
    first = performance.PerformanceManager()
    assert first.set_power_plan(True)[0]
    assert machine['power'] == first.POWER_HIGH_PERF
    restarted = performance.PerformanceManager()
    assert restarted.set_power_plan(False)[0]
    assert machine['power'] == CUSTOM_GUID


def test_originally_stopped_service_stays_stopped_on_restore(environment):
    machine, calls, _ = environment
    subject = performance.PerformanceManager()
    assert subject.set_sysmain(False)[0]
    assert subject.set_sysmain(True)[0]
    assert machine['SysMain'] is False


def test_visual_custom_value_restored_exactly(environment):
    machine, _, _ = environment
    subject = performance.PerformanceManager()
    assert subject.set_visual_effects(False)[0]
    assert machine['visual'] == 2
    assert performance.PerformanceManager().set_visual_effects(True)[0]
    assert machine['visual'] == 3


def test_unknown_service_status_is_none(environment, monkeypatch):
    subject = performance.PerformanceManager()
    monkeypatch.setattr(subject, '_run_cmd', lambda *a, **k: (False, 'access denied'))
    assert subject.get_sysmain_status() is None
    assert subject.set_sysmain(False)[0] is False


def test_unapproved_service_does_not_reach_os(environment):
    _, calls, _ = environment
    subject = performance.PerformanceManager()
    assert subject.set_service('SysMain & whoami', False)[0] is False
    assert calls == []


def test_snapshot_write_failure_prevents_mutation(environment, monkeypatch):
    machine, _, _ = environment
    subject = performance.PerformanceManager()
    assert callable(getattr(subject, '_save_state', None))
    def fail_save(): raise PermissionError('denied')
    monkeypatch.setattr(subject, '_save_state', fail_save)
    assert subject.set_power_plan(True)[0] is False
    assert machine['power'] == CUSTOM_GUID


def test_master_turbo_restores_all_originals(environment):
    machine, _, _ = environment
    subject = performance.PerformanceManager()
    assert callable(getattr(subject, 'set_turbo', None))
    assert subject.set_turbo(True)[0]
    assert machine['power'] == subject.POWER_HIGH_PERF
    assert machine['SysMain'] is False and machine['WSearch'] is False
    assert performance.PerformanceManager().set_turbo(False)[0]
    assert machine == {'power': CUSTOM_GUID, 'SysMain': False, 'WSearch': True, 'Spooler': True, 'visual': 3}


def test_missing_recovery_record_makes_master_state_unknown(environment):
    machine, _, _ = environment
    machine.update(power=performance.PerformanceManager.POWER_HIGH_PERF,
                   SysMain=False, WSearch=False, Spooler=False, visual=2)
    subject = performance.PerformanceManager()
    assert subject.is_turbo_active() is None


def test_corrupt_recovery_record_blocks_changes(environment):
    machine, _, location = environment
    path = location / 'Panacea' / 'turbo-state.json'
    path.parent.mkdir()
    path.write_text('{invalid', encoding='utf-8')
    subject = performance.PerformanceManager()
    assert subject.set_power_plan(True)[0] is False
    assert machine['power'] == CUSTOM_GUID
    assert subject.is_turbo_active() is None


def test_failed_mutation_retains_original_for_retry(environment, monkeypatch):
    machine, _, _ = environment
    subject = performance.PerformanceManager()
    original_runner = subject._run_cmd
    monkeypatch.setattr(subject, '_run_cmd', lambda cmd, **kw: (False, 'denied') if cmd[1] == '/setactive' else original_runner(cmd, **kw))
    assert subject.set_power_plan(True)[0] is False
    assert machine['power'] == CUSTOM_GUID
    assert performance.PerformanceManager().set_power_plan(False)[0]
    assert machine['power'] == CUSTOM_GUID


def test_unknown_visual_registry_does_not_mutate(environment, monkeypatch):
    machine, _, _ = environment
    registry = sys.modules['winreg']
    def denied(*args): raise PermissionError('denied')
    monkeypatch.setattr(registry, 'QueryValueEx', denied)
    subject = performance.PerformanceManager()
    assert subject.get_visual_effects() is None
    assert subject.set_visual_effects(False)[0] is False
    assert machine['visual'] == 3


def test_turbo_command_uses_explicit_arguments_without_shell(environment, monkeypatch):
    calls = []
    def run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout='ok', stderr='')
    monkeypatch.setattr(performance.subprocess, 'run', run)
    assert REAL_RUN_CMD(performance.PerformanceManager(), ['powercfg', '/getactivescheme'])[0]
    assert calls[0][0][0].lower().endswith('powercfg.exe')
    assert calls[0][0][1:] == ['/getactivescheme']
    assert calls[0][1]['shell'] is False


def test_reparse_recovery_directory_does_not_write_outside(environment):
    machine, _, location = environment
    outside = location / 'outside'
    outside.mkdir()
    link = location / 'Panacea'
    if os.name != 'nt':
        pytest.skip('Windows recovery path guards')
    completed = subprocess.run(['cmd.exe', '/c', 'mklink', '/J', str(link), str(outside)],
                               stdin=subprocess.DEVNULL, capture_output=True)
    if completed.returncode:
        pytest.skip('Fixture junction unavailable')
    subject = performance.PerformanceManager()
    assert subject.set_power_plan(True)[0] is False
    assert machine['power'] == CUSTOM_GUID
    assert list(outside.iterdir()) == []


def test_master_unknown_original_prevents_every_mutation(environment, monkeypatch):
    machine, _, _ = environment
    subject = performance.PerformanceManager()
    original = subject._run_cmd
    monkeypatch.setattr(subject, '_run_cmd', lambda args, **kw: (False, 'denied')
                        if args == ['sc', 'query', 'WSearch'] else original(args, **kw))
    assert subject.set_turbo(True)[0] is False
    assert machine == {'power': CUSTOM_GUID, 'SysMain': False, 'WSearch': True, 'Spooler': True, 'visual': 3}


def test_conflicting_power_changes_are_serialized(environment, monkeypatch):
    machine, _, _ = environment
    subject = performance.PerformanceManager()
    started = threading.Event()
    release = threading.Event()
    original = subject._run_cmd
    outcomes = []
    def delayed(args, **kwargs):
        if args == ['powercfg', '/setactive', subject.POWER_HIGH_PERF]:
            started.set()
            assert release.wait(3)
        return original(args, **kwargs)
    monkeypatch.setattr(subject, '_run_cmd', delayed)
    first = threading.Thread(target=lambda: outcomes.append(subject.set_power_plan(True)))
    second = threading.Thread(target=lambda: outcomes.append(subject.set_power_plan(False)))
    first.start()
    assert started.wait(3)
    second.start()
    release.set()
    first.join(3)
    second.join(3)
    assert not first.is_alive() and not second.is_alive()
    assert len(outcomes) == 2 and all(result[0] for result in outcomes)
    assert machine['power'] == CUSTOM_GUID


_CHILD_TRANSACTION = r'''
import contextlib, json, sys, time
from pathlib import Path
from types import SimpleNamespace
from modules.performance import PerformanceManager
state, ready, release = map(Path, sys.argv[1:4])
mode = sys.argv[4]
subject = PerformanceManager(logger=SimpleNamespace(log=lambda *a: None), state_path=state)
machine = {'power': '12345678-1111-2222-3333-123456789abc'}
def mock_command(args, **kwargs):
    if args[1] == '/getactivescheme':
        return True, 'Power Scheme GUID: ' + machine['power']
    if args[1] == '/setactive':
        machine['power'] = args[2]
        return True, ''
    raise AssertionError('Only mocked power operations are permitted')
subject._run_cmd = mock_command
def wait_release():
    ready.write_text('ready', encoding='utf-8')
    deadline = time.monotonic() + 10
    while not release.exists() and time.monotonic() < deadline:
        time.sleep(0.02)
if mode == 'race':
    save = subject._save_state
    def delayed_save():
        wait_release()
        save()
    subject._save_state = delayed_save
    success, message = subject.set_power_plan(True)
    if not success:
        raise AssertionError(message)
else:
    with getattr(subject, '_transaction', contextlib.nullcontext)():
        subject._state = {'power': machine['power']}
        subject._save_state()
        wait_release()
'''


def _launch_transaction_holder(subject, location, mode):
    ready, release = location / 'ready', location / 'release'
    child = subprocess.Popen([sys.executable, '-c', _CHILD_TRANSACTION, str(subject.state_path),
                              str(ready), str(release), mode], stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    deadline = time.monotonic() + 5
    while not ready.exists() and child.poll() is None and time.monotonic() < deadline:
        time.sleep(0.02)
    if not ready.exists():
        child.kill()
        _, error = child.communicate(timeout=3)
        pytest.fail('Fixture holder could not start: ' + error.decode(errors='replace'))
    return child, release


def _stop_transaction_holder(child, release):
    release.write_text('release', encoding='utf-8')
    try:
        _, error = child.communicate(timeout=4)
    except subprocess.TimeoutExpired:
        child.kill()
        _, error = child.communicate(timeout=3)
    if child.returncode != 0:
        pytest.fail('Fixture holder failed: ' + error.decode(errors='replace'))


def test_two_processes_preserve_both_originals_and_reload_stale_manager(environment):
    machine, calls, location = environment
    subject = performance.PerformanceManager()
    child, release = _launch_transaction_holder(subject, location, 'race')
    results = []
    worker = threading.Thread(target=lambda: results.append(subject.set_wsearch(False)))
    try:
        worker.start()
        time.sleep(0.15)
        assert results == []  # The other process owns the entire snapshot/mutation transaction.
        assert calls == []  # No OS setting query or change occurs outside the transaction.
    finally:
        _stop_transaction_holder(child, release)
        worker.join(3)
    assert not worker.is_alive()
    assert results[0][0]
    original = json.loads(subject.state_path.read_text(encoding='utf-8'))['original']
    assert original == {'power': CUSTOM_GUID, 'WSearch': True}
    assert machine['WSearch'] is False


def test_abandoned_process_lock_releases_and_preserves_recovery(environment):
    machine, _, location = environment
    subject = performance.PerformanceManager()
    child, release = _launch_transaction_holder(subject, location, 'hold')
    machine['power'] = subject.POWER_HIGH_PERF  # Simulated settings left by a terminated app.
    results = []
    worker = threading.Thread(target=lambda: results.append(subject.set_power_plan(False)))
    try:
        worker.start()
        time.sleep(0.15)
        assert results == []
    finally:
        child.kill()
        child.communicate(timeout=3)
        worker.join(3)
    assert not worker.is_alive()
    assert results[0][0]
    assert machine['power'] == CUSTOM_GUID
    assert json.loads(subject.state_path.read_text(encoding='utf-8'))['original'] == {}


def test_process_lock_timeout_prevents_queries_and_mutation(environment):
    machine, calls, location = environment
    subject = performance.PerformanceManager()
    subject._lock_timeout_ms = 75
    child, release = _launch_transaction_holder(subject, location, 'hold')
    try:
        result = subject.set_wsearch(False)
        assert result[0] is False
        assert 'lock' in result[1].lower()
        assert calls == []
        assert machine['WSearch'] is True
    finally:
        _stop_transaction_holder(child, release)


@pytest.mark.parametrize('existing_directory', [False, True])
def test_live_attribute_retarget_cannot_create_recovery_outside(environment, monkeypatch, existing_directory):
    machine, _, location = environment
    base = location / 'local'
    base.mkdir()
    outside = location / 'outside'
    outside.mkdir()
    state = base / 'Panacea' / 'turbo-state.json'
    if existing_directory:
        state.parent.mkdir()
    subject = performance.PerformanceManager(state_path=state)
    original_guard = performance._guard_path
    attempts = []
    @contextmanager
    def retarget(path):
        with original_guard(path) as held:
            if not attempts:
                attempts.append(_try_convert_to_junction(path, outside, 0x100))
            yield held
    monkeypatch.setattr(performance, '_guard_path', retarget)
    result = subject.set_power_plan(True)
    assert attempts == [(True, 0)]
    assert result[0] is False
    assert machine['power'] == CUSTOM_GUID
    assert list(outside.iterdir()) == []


def test_snapshot_read_does_not_accept_retargeted_foreign_record(environment, monkeypatch):
    _, _, location = environment
    state = location / 'Panacea' / 'turbo-state.json'
    state.parent.mkdir()
    state.write_text(json.dumps({'version': 1, 'original': {'power': CUSTOM_GUID}}), encoding='utf-8')
    outside = location / 'outside'
    outside.mkdir()
    foreign = {'version': 1, 'original': {'power': performance.PerformanceManager.POWER_HIGH_PERF}}
    (outside / state.name).write_text(json.dumps(foreign), encoding='utf-8')
    (location / 'original-record.json').write_bytes(state.read_bytes())
    original_guard = performance._guard_path
    attempts = []
    @contextmanager
    def retarget(path):
        with original_guard(path) as held:
            if not attempts:
                state.unlink()
                attempts.append(_try_convert_to_junction(path, outside, 0x100))
            yield held
    monkeypatch.setattr(performance, '_guard_path', retarget)
    subject = performance.PerformanceManager(state_path=state)
    assert attempts == [(True, 0)]
    assert subject._state_error is not None
    assert subject._state != foreign['original']
    assert json.loads((outside / state.name).read_text(encoding='utf-8')) == foreign


@pytest.mark.parametrize('existing_directory', [False, True])
def test_retarget_after_parent_validation_never_creates_an_outside_entry(environment, monkeypatch, existing_directory):
    machine, _, location = environment
    base = location / 'local'
    base.mkdir()
    outside = location / 'outside'
    outside.mkdir()
    state = base / 'Panacea' / 'turbo-state.json'
    if existing_directory:
        state.parent.mkdir()
    subject = performance.PerformanceManager(state_path=state)
    original = protected_files._validate_handle
    attempts = []
    def retarget(kernel, handle, path):
        info = original(kernel, handle, path)
        if not attempts:
            attempts.append(_try_convert_to_junction(path, outside, 0x100))
        return info
    monkeypatch.setattr(protected_files, '_validate_handle', retarget)
    result = subject.set_power_plan(True)
    assert attempts == [(True, 0)]
    assert result[0] is False
    assert machine['power'] == CUSTOM_GUID
    assert list(outside.iterdir()) == []


def test_failed_snapshot_write_disposes_only_continuously_owned_temp(environment, monkeypatch):
    machine, _, location = environment
    subject = performance.PerformanceManager()
    assert subject.set_power_plan(True)[0]
    snapshot = subject.state_path.read_bytes()
    original = performance.write_bytes
    def fail(kernel, handle, payload):
        original(kernel, handle, payload)
        raise OSError('Fixture interrupted after payload write')
    monkeypatch.setattr(performance, 'write_bytes', fail)
    assert subject.set_wsearch(False)[0] is False
    assert machine['WSearch'] is True
    assert subject.state_path.read_bytes() == snapshot
    assert sorted(path.name for path in subject.state_path.parent.iterdir()) == ['turbo-state.json']


def test_exclusive_temp_collision_preserves_foreign_file_and_previous_snapshot(environment, monkeypatch):
    machine, _, _ = environment
    subject = performance.PerformanceManager()
    assert subject.set_power_plan(True)[0]
    snapshot = subject.state_path.read_bytes()
    foreign = subject.state_path.parent / ('turbo-' + 'a' * 32 + '.tmp')
    foreign.write_bytes(b'foreign')
    monkeypatch.setattr(performance.secrets, 'token_hex', lambda size: 'a' * 32)
    assert subject.set_wsearch(False)[0] is False
    assert machine['WSearch'] is True
    assert subject.state_path.read_bytes() == snapshot
    assert foreign.read_bytes() == b'foreign'
