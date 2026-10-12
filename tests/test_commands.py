import io
from types import SimpleNamespace

import pytest

import modules.commands as commands
import modules.disk as disk


@pytest.fixture
def captured(monkeypatch):
    calls = []
    def popen(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(stdout=io.BytesIO(b'progress\n'), poll=lambda: 0,
                               wait=lambda: 0)
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
    assert args[1:] == ['/Online', '/Cleanup-Image', '/CheckHealth']
    assert options['shell'] is False
    assert lines == ['progress']


def test_nonzero_command_exit_reports_failure(captured, monkeypatch):
    monkeypatch.setattr(commands.subprocess, 'Popen', lambda *a, **k: SimpleNamespace(stdout=io.BytesIO(b'failed\n'), poll=lambda: 5, wait=lambda: 5))
    assert commands.CommandRunner().run_command_stream('sfc /scannow', 'test', lambda _: None) is False


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
