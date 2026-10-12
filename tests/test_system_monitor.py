import ctypes
from types import SimpleNamespace
from modules.system_monitor import SystemMonitor
import modules.system_monitor as monitoring


def bare_monitor():
    return SystemMonitor()


def test_fast_sample_does_not_wait_for_hardware_metadata():
    monitor = bare_monitor()
    monitor.get_ram_usage = lambda: (16, 8, 50)
    monitor.get_disk_usage = lambda: (512, 128, 75)
    monitor.get_cpu_usage = lambda: 12.5
    monitor.get_system_uptime = lambda: '2d 3h 4m'
    monitor.get_battery_status = lambda: (None, 'Unknown')
    def slow():
        raise AssertionError('fast sample fetched hardware metadata')
    monitor.get_ram_info = monitor.get_disk_model = monitor.get_cpu_info = slow
    sample = monitor.sample_fast()
    assert sample['cpu'] == 12.5
    assert sample['ram'] == (16, 8, 50)
    assert sample['uptime'] == '2d 3h 4m'


def test_cache_uses_monotonic_clock_and_stamps_after_fetch(monkeypatch):
    monitor = bare_monitor()
    tick = [10.0]
    monkeypatch.setattr(monitoring.time, 'monotonic', lambda: tick[0])
    monkeypatch.setattr(monitoring.time, 'time', lambda: -10000)
    calls = []
    def fetch():
        calls.append(True); tick[0] += 50
        return 'hardware'
    assert monitor._cached('hardware', fetch) == 'hardware'
    tick[0] = 170
    assert monitor._cached('hardware', fetch) == 'hardware'
    assert len(calls) == 1
    tick[0] = 181
    monitor._cached('hardware', fetch)
    assert len(calls) == 2


def test_uptime_sets_64_bit_windows_return_type(monkeypatch):
    class Tick:
        restype = None
        def __call__(self):
            return 5_000_000_000 if self.restype is ctypes.c_uint64 else 705_032_704
    tick = Tick()
    monkeypatch.setattr(monitoring.ctypes, 'windll', SimpleNamespace(kernel32=SimpleNamespace(GetTickCount64=tick)), raising=False)
    assert bare_monitor().get_system_uptime() == '57d 20h 53m'
    assert tick.restype is ctypes.c_uint64


def test_battery_unknown_unsigned_byte_is_not_negative(monkeypatch):
    def power_status(pointer):
        status = pointer._obj
        status.BatteryLifePercent = 255
        status.ACLineStatus = 255
        return 1
    monkeypatch.setattr(monitoring.ctypes, 'windll', SimpleNamespace(kernel32=SimpleNamespace(GetSystemPowerStatus=power_status)), raising=False)
    assert bare_monitor().get_battery_status() == (None, 'Unknown')


def test_battery_query_failure_reports_unknown(monkeypatch):
    monkeypatch.setattr(monitoring.ctypes, 'windll', SimpleNamespace(kernel32=SimpleNamespace(GetSystemPowerStatus=lambda pointer: 0)), raising=False)
    assert bare_monitor().get_battery_status() == (None, 'Unknown')

import pytest


@pytest.mark.parametrize('method,output,expected', [
    ('_fetch_ram_info', b'{"Speed":3200,"SMBIOSMemoryType":26}', 'DDR4 @ 3200 MHz (1 modules)'),
    ('_fetch_disk_model', b'Example Disk|SSD', 'SSD Example Disk'),
    ('get_windows_update_status', b'2,1', (2, 1, '2 Required, 1 Optional')),
])
def test_monitor_queries_launch_trusted_powershell_and_preserve_results(monkeypatch, method, output, expected):
    trusted = r'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
    monkeypatch.setenv('PATH', r'C:\Attacker\fakebin')
    monkeypatch.setattr(monitoring, 'system_executable', lambda name: trusted if name == 'powershell.exe' else None, raising=False)
    monkeypatch.setattr(monitoring.subprocess, 'CREATE_NO_WINDOW', 0, raising=False)
    calls = []
    def popen(arguments, **kwargs):
        calls.append((arguments, kwargs))
        class FinishedQuery:
            returncode = 0
            stdout = stderr = stdin = None
            def communicate(self, timeout):
                return output, b''
            def poll(self):
                return 0
            def wait(self, timeout):
                return 0
        return FinishedQuery()
    monkeypatch.setattr(monitoring.subprocess, 'Popen', popen)
    result = getattr(bare_monitor(), method)()
    assert calls[0][0][0] == trusted
    assert calls[0][0][1:3] == ['-NoProfile', '-Command']
    assert calls[0][1].get('shell', False) is False
    assert result == expected


@pytest.mark.parametrize('method,expected', [
    ('_fetch_ram_info', ''),
    ('_fetch_disk_model', 'Unknown Model'),
    ('get_windows_update_status', (-1, -1, 'Check Failed')),
])
def test_monitor_query_resolution_failure_never_falls_back_to_path(monkeypatch, method, expected):
    def fail_resolution(name):
        raise OSError('Trusted Windows directory unavailable')
    monkeypatch.setattr(monitoring, 'system_executable', fail_resolution, raising=False)
    monkeypatch.setattr(monitoring.subprocess, 'CREATE_NO_WINDOW', 0, raising=False)
    calls = []
    monkeypatch.setattr(monitoring.subprocess, 'Popen', lambda *args, **kwargs: calls.append(args))
    assert getattr(bare_monitor(), method)() == expected
    assert calls == []

import threading
import time
import sys


class BlockingQueryProcess:
    def __init__(self):
        self.returncode = None
        self.communicating = threading.Event()
        self.killed = threading.Event()
        self.waited = threading.Event()
        self.kill_thread = None
        self.stdout = self.stderr = self.stdin = None

    def communicate(self, timeout):
        self.communicating.set()
        assert self.killed.wait(3), 'test query was never cancelled'
        return b'', b''

    def poll(self):
        return self.returncode

    def kill(self):
        self.kill_thread = threading.get_ident()
        self.returncode = -1
        self.killed.set()

    def wait(self, timeout):
        assert self.killed.wait(timeout)
        self.waited.set()
        return self.returncode


def lifecycle_monitor():
    subject = SystemMonitor()
    assert hasattr(subject, '_query_output'), 'Monitor queries need owned process lifecycle'
    assert hasattr(subject, 'close'), 'Monitor needs nonblocking query cancellation'
    return subject


def run_query_in_thread(subject, args=('trusted.exe',), timeout=30):
    results = []
    def run():
        try:
            results.append(subject._query_output(list(args), timeout=timeout))
        except Exception as exc:
            results.append(exc)
    worker = threading.Thread(target=run)
    worker.start()
    return worker, results


def test_close_cancels_and_reaps_owned_query_off_calling_thread(monkeypatch):
    subject = lifecycle_monitor()
    process = BlockingQueryProcess()
    monkeypatch.setattr(monitoring.subprocess, 'Popen', lambda *args, **kwargs: process)
    worker, results = run_query_in_thread(subject)
    try:
        assert process.communicating.wait(2)
        started = time.monotonic()
        subject.close()
        assert time.monotonic() - started < 0.2
        assert process.waited.wait(2)
        worker.join(2)
        assert not worker.is_alive()
        assert process.kill_thread != threading.get_ident()
        assert results and isinstance(results[0], Exception)
    finally:
        if not process.killed.is_set():
            process.kill()
        worker.join(3)


def test_closed_monitor_never_launches_another_query(monkeypatch):
    subject = lifecycle_monitor()
    calls = []
    monkeypatch.setattr(monitoring.subprocess, 'Popen', lambda *args, **kwargs: calls.append(args))
    subject.close()
    with pytest.raises(RuntimeError, match='closed'):
        subject._query_output(['trusted.exe'], timeout=1)
    assert calls == []


def test_close_during_atomic_process_creation_cancels_resulting_child(monkeypatch):
    subject = lifecycle_monitor()
    entered, release = threading.Event(), threading.Event()
    process = BlockingQueryProcess()
    def create(*args, **kwargs):
        entered.set()
        assert release.wait(3)
        return process
    monkeypatch.setattr(monitoring.subprocess, 'Popen', create)
    worker, results = run_query_in_thread(subject)
    try:
        assert entered.wait(2)
        started = time.monotonic()
        subject.close()
        assert time.monotonic() - started < 0.2
        assert not process.killed.is_set()
        release.set()
        assert process.waited.wait(2)
        worker.join(2)
        assert not worker.is_alive()
        assert results and isinstance(results[0], Exception)
        with pytest.raises(RuntimeError, match='closed'):
            subject._query_output(['trusted.exe'], timeout=1)
    finally:
        release.set()
        if not process.killed.is_set():
            process.kill()
        worker.join(3)


def test_query_timeout_kills_and_waits_before_preserving_timeout(monkeypatch):
    subject = lifecycle_monitor()
    process = BlockingQueryProcess()
    def timeout(timeout):
        raise monitoring.subprocess.TimeoutExpired('trusted.exe', timeout)
    process.communicate = timeout
    monkeypatch.setattr(monitoring.subprocess, 'Popen', lambda *args, **kwargs: process)
    with pytest.raises(monitoring.subprocess.TimeoutExpired):
        subject._query_output(['trusted.exe'], timeout=0.1)
    assert process.killed.is_set()
    assert process.waited.is_set()
    subject.close()


def test_failed_process_creation_does_not_poison_registry_or_shutdown(monkeypatch):
    subject = lifecycle_monitor()
    def fail(*args, **kwargs):
        raise OSError('creation failed')
    monkeypatch.setattr(monitoring.subprocess, 'Popen', fail)
    with pytest.raises(OSError, match='creation failed'):
        subject._query_output(['trusted.exe'], timeout=1)
    subject.close()
    with pytest.raises(RuntimeError, match='closed'):
        subject._query_output(['trusted.exe'], timeout=1)


def test_native_sleeping_fixture_is_reaped_by_monitor_close(tmp_path, monkeypatch):
    subject = lifecycle_monitor()
    real_popen = monitoring.subprocess.Popen
    processes = []
    def native_fixture(arguments, **kwargs):
        assert arguments[0] == sys.executable
        kwargs['cwd'] = str(tmp_path)
        process = real_popen(arguments, **kwargs)
        processes.append(process)
        return process
    monkeypatch.setattr(monitoring.subprocess, 'Popen', native_fixture)
    child_script = tmp_path / 'sleeping_fixture.py'
    ready_file = tmp_path / 'ready.txt'
    child_script.write_text('import pathlib,sys,time\npathlib.Path(sys.argv[1]).write_text("ready")\ntime.sleep(30)\n')
    worker, results = run_query_in_thread(subject, (sys.executable, str(child_script), str(ready_file)), timeout=30)
    try:
        deadline = time.monotonic() + 3
        while not ready_file.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert ready_file.exists(), 'native fixture did not start'
        subject.close()
        worker.join(3)
        assert not worker.is_alive()
        assert results and isinstance(results[0], Exception)
        assert len(processes) == 1
        assert processes[0].poll() is not None
        assert processes[0].wait(timeout=1) is not None
    finally:
        subject.close()
        for process in processes:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=3)
        worker.join(3)


def test_query_communication_error_still_kills_and_waits(monkeypatch):
    subject = lifecycle_monitor()
    process = BlockingQueryProcess()
    def fail(timeout):
        raise OSError('pipe read failed')
    process.communicate = fail
    monkeypatch.setattr(monitoring.subprocess, 'Popen', lambda *args, **kwargs: process)
    with pytest.raises(OSError, match='pipe read failed'):
        subject._query_output(['trusted.exe'], timeout=1)
    assert process.killed.is_set()
    assert process.waited.is_set()
    subject.close()


def test_native_timeout_reaps_fixture_and_closes_its_pipes(tmp_path, monkeypatch):
    subject = lifecycle_monitor()
    real_popen = monitoring.subprocess.Popen
    processes = []
    def native_fixture(arguments, **kwargs):
        assert arguments[0] == sys.executable
        kwargs['cwd'] = str(tmp_path)
        process = real_popen(arguments, **kwargs)
        processes.append(process)
        return process
    monkeypatch.setattr(monitoring.subprocess, 'Popen', native_fixture)
    child_script = tmp_path / 'sleeping_fixture.py'
    child_script.write_text('import time\ntime.sleep(30)\n')
    try:
        with pytest.raises(monitoring.subprocess.TimeoutExpired):
            subject._query_output([sys.executable, str(child_script)], timeout=0.1)
        assert len(processes) == 1
        assert processes[0].poll() is not None
        assert processes[0].stdout.closed
        assert processes[0].stderr.closed
    finally:
        subject.close()
        for process in processes:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=3)
            process.stdout.close()
            process.stderr.close()
