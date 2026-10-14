import io
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

import pytest

import modules.commands as commands
import modules.disk as disk


@pytest.fixture
def captured(monkeypatch):
    calls = []
    real_read = commands._read_pipe_available
    monkeypatch.setattr(commands, '_read_pipe_available', lambda stream:
                        stream.readline() if isinstance(stream, io.BytesIO) else real_read(stream))
    def popen(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(stdout=io.BytesIO(b'progress\n'), poll=lambda: 0,
                               wait=lambda **kwargs: 0)
    for module in (commands, disk):
        monkeypatch.setattr(module, 'Logger', lambda: SimpleNamespace(log=lambda *args: None))
    monkeypatch.setattr(commands.subprocess, 'Popen', popen)
    return calls


@pytest.mark.parametrize('command', ['sfc /scannow & whoami', 'ipconfig /flushdns | whoami', 'cmd /c whoami', 'sfc /scannow\nwhoami', 'chkdsk C: /scan /perf & del C:\\sentinel'])
def test_injected_command_rejected_without_launch(command, captured):
    assert commands.CommandRunner().run_command_stream(command, 'test', lambda _: None) is False
    assert captured == []


def test_allowlisted_command_launches_direct_executable(captured):
    lines = []
    assert commands.CommandRunner().run_command_stream('DISM /Online /Cleanup-Image /CheckHealth', 'test', lines.append)
    args, options = captured[0]
    assert args[0].lower().endswith('dism.exe')
    assert args[1:] == ['/Online', '/Cleanup-Image', '/CheckHealth', '/NoRestart']
    assert options['shell'] is False
    assert lines == ['progress']


def test_nonzero_command_exit_reports_failure(captured, monkeypatch):
    monkeypatch.setattr(commands.subprocess, 'Popen', lambda *a, **k: SimpleNamespace(stdout=io.BytesIO(b'failed\n'), poll=lambda: 5, wait=lambda **kwargs: 5))
    lines = []
    assert commands.CommandRunner().run_command_stream('sfc /scannow', 'test', lines.append) is False
    assert any('exit code 5' in line for line in lines)


@pytest.mark.parametrize('drive', ['C: & whoami', 'C:\\', 'CC:', '', 'C:\n', 'C: /D'])
def test_invalid_drive_rejected_without_launch(drive, captured):
    assert disk.DiskOptimizer().analyze_optimize_drive(drive) is False
    assert captured == []


def test_disk_without_callback_drains_output_and_returns_success(captured):
    assert disk.DiskOptimizer().analyze_optimize_drive('C:') is True
    args, options = captured[0]
    assert args[0].lower().endswith('defrag.exe')
    assert args[1:] == ['C:', '/O']
    assert options['shell'] is False


@pytest.mark.parametrize('operation', ['command', 'disk'])
def test_silent_maintenance_process_times_out_and_is_reaped(captured, monkeypatch, operation):
    # captured replaced Popen already; restore the actual class for this fixture-only child.
    real_popen = _REAL_POPEN
    children = []
    def fixture_process(*args, **kwargs):
        child = real_popen([sys.executable, '-c', 'import time; time.sleep(30)'],
                           stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        children.append(child)
        return child
    monkeypatch.setattr(commands.subprocess, 'Popen', fixture_process)
    lines = []
    start = time.monotonic()
    if operation == 'command':
        success = commands.CommandRunner().run_command_stream('sfc /scannow', 'test', lines.append, timeout=0.1)
    else:
        success = disk.DiskOptimizer().analyze_optimize_drive('C:', lines.append, timeout=0.1)
    assert success is False
    assert time.monotonic() - start < 5
    assert children and children[0].poll() is not None
    assert children[0].stdout.closed
    assert any('timed out' in line.lower() for line in lines)


_REAL_POPEN = subprocess.Popen


@pytest.mark.parametrize('operation', ['command', 'disk'])
def test_output_read_failure_reaps_the_started_process(captured, monkeypatch, operation):
    events = []
    class BrokenOutput:
        def fileno(self):
            raise OSError('output pipe failed')
        def close(self):
            events.append('closed')
    process = SimpleNamespace(stdout=BrokenOutput(), poll=lambda: None,
                              kill=lambda: events.append('killed'),
                              wait=lambda **kwargs: events.append('reaped') or 1)
    monkeypatch.setattr(commands.subprocess, 'Popen', lambda *a, **k: process)
    if operation == 'command':
        subject = commands.CommandRunner()
        success = subject.run_command_stream('sfc /scannow', 'test', None)
    else:
        subject = disk.DiskOptimizer()
        success = subject.analyze_optimize_drive('C:')
    assert success is False
    assert subject.completion_unknown is True
    assert 'killed' in events and 'reaped' in events and 'closed' in events


@pytest.mark.parametrize('action', ['CheckHealth', 'RestoreHealth', 'StartComponentCleanup'])
def test_dism_never_requests_a_restart_or_interactive_input(captured, action):
    assert commands.CommandRunner().run_command_stream(f'DISM /Online /Cleanup-Image /{action}', 'test', None)
    assert '/NoRestart' in captured[0][0]
    assert captured[0][1]['stdin'] == subprocess.DEVNULL


@pytest.mark.parametrize('command,expected', [('DISM /Online /Cleanup-Image /RestoreHealth', True), ('sfc /scannow', False)])
def test_dism_restart_required_is_reported_without_treating_unrelated_exit_as_success(captured, monkeypatch, command, expected):
    monkeypatch.setattr(commands.subprocess, 'Popen', lambda *a, **k: SimpleNamespace(
        stdout=io.BytesIO(b'done\n'), poll=lambda: 3010, wait=lambda **kwargs: 3010))
    lines = []
    runner = commands.CommandRunner()
    assert runner.run_command_stream(command, 'test', lines.append) is expected
    if expected:
        assert any('restart required' in line.lower() for line in lines)


def test_utf16_command_output_preserves_non_ascii_text_across_lines(captured, monkeypatch):
    output = '\ufeffFile verification: 正常\r\nIntegrità verificata.\r\n'.encode('utf-16-le')
    monkeypatch.setattr(commands.subprocess, 'Popen', lambda *a, **k: SimpleNamespace(
        stdout=io.BytesIO(output), poll=lambda: 0, wait=lambda **kwargs: 0))
    lines = []
    assert commands.CommandRunner().run_command_stream('sfc /scannow', 'test', lines.append)
    assert lines == ['File verification: 正常', 'Integrità verificata.']


def test_deadline_is_not_extended_by_descendant_inheriting_output(monkeypatch):
    # Both parent and descendant are finite fixture-only Python processes.
    script = (
        "import subprocess,sys,time; "
        "subprocess.Popen([sys.executable,'-c','import time; time.sleep(3)'], "
        "stdin=subprocess.DEVNULL,stdout=sys.stdout,stderr=sys.stderr); "
        "print('descendant started',flush=True); time.sleep(30)"
    )
    parents = []
    def track(args, **kwargs):
        process = _REAL_POPEN(args, **kwargs)
        parents.append(process)
        return process
    monkeypatch.setattr(commands.subprocess, 'Popen', track)
    threads_before = {thread.ident for thread in threading.enumerate()}
    lines = []
    started = time.monotonic()
    try:
        with pytest.raises(subprocess.TimeoutExpired):
            commands.run_process_stream([sys.executable, '-c', script], lines.append, timeout=0.5)
        elapsed = time.monotonic() - started
        assert 'descendant started' in lines, 'Fixture must create inherited writer before timeout'
        assert elapsed < 1.75, f'Descendant extended deadline: {elapsed:.3f}s'
        assert parents[0].poll() is not None
        assert parents[0].stdout.closed
        assert {thread.ident for thread in threading.enumerate()} <= threads_before
    finally:
        # The fixture descendant exits naturally; never terminate an OS process tree.
        time.sleep(max(0, 3.5 - (time.monotonic() - started)))


@pytest.mark.parametrize('exit_code,expected', [(1, True), (2, False), (3, False)])
def test_chkdsk_repaired_errors_are_success_but_incomplete_scan_is_not(captured, monkeypatch, exit_code, expected):
    monkeypatch.setattr(commands.subprocess, 'Popen', lambda *a, **k: SimpleNamespace(
        stdout=io.BytesIO(b''), poll=lambda: exit_code, wait=lambda **kwargs: exit_code))
    lines = []
    assert commands.CommandRunner().run_command_stream('chkdsk C: /scan /perf', 'Disk scan', lines.append) is expected
    if expected:
        assert any('errors repaired' in line.lower() for line in lines)


@pytest.mark.parametrize('operation', ['command', 'disk'])
def test_timeout_marks_unknown_completion_and_next_run_resets_it(captured, monkeypatch, operation):
    subject = commands.CommandRunner() if operation == 'command' else disk.DiskOptimizer()
    module = commands if operation == 'command' else disk
    def invoke():
        return (subject.run_command_stream('sfc /scannow', 'test', None) if operation == 'command'
                else subject.analyze_optimize_drive('C:'))
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired('fixture', 0.1)
    monkeypatch.setattr(module, 'run_process_stream', timeout)
    assert invoke() is False
    assert subject.completion_unknown is True
    monkeypatch.setattr(module, 'run_process_stream', lambda *args, **kwargs: 0)
    assert invoke() is True
    assert subject.completion_unknown is False


def test_native_chunked_utf16_output_including_final_unterminated_line():
    payload = '\ufeffFile verification: 正常\r\nIntegrità verificata.'.encode('utf-16-le')
    script = (
        'import os,time; payload=' + repr(payload) + '; '
        'os.write(1,payload[:7]); time.sleep(0.03); os.write(1,payload[7:])'
    )
    lines = []
    assert commands.run_process_stream([sys.executable, '-c', script], lines.append, timeout=5) == 0
    assert lines == ['File verification: 正常', 'Integrità verificata.']
