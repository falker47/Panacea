import ctypes
from types import SimpleNamespace
from modules.system_monitor import SystemMonitor
import modules.system_monitor as monitoring
import json
import os


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
    ('_fetch_ram_info', b'{"ConfiguredClockSpeed":3200,"SMBIOSMemoryType":26}', 'DDR4 @ 3200 MHz (1 module)'),
    ('_fetch_disk_model', b'Example Disk|SSD', 'SSD Example Disk'),
    ('get_windows_update_status', b'{"ResultCode":2,"Recommended":2,"Optional":1}', (2, 1, '2 recommended, 1 optional')),
])
def test_monitor_queries_launch_trusted_powershell_and_preserve_results(monkeypatch, method, output, expected):
    trusted = r'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
    monkeypatch.setenv('PATH', r'C:\Attacker\fakebin')
    monkeypatch.setattr(monitoring, 'system_executable', lambda name: trusted if name == 'powershell.exe' else r'C:\Windows\System32\cmd.exe', raising=False)
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


def test_failed_memory_api_is_unavailable_not_zero_usage(monkeypatch):
    def failed(pointer):
        # A failed API call can leave stale output fields: ignore them all.
        pointer._obj.ullTotalPhys = 16 * 1024**3
        pointer._obj.ullAvailPhys = 16 * 1024**3
        return 0
    monkeypatch.setattr(monitoring.ctypes, 'windll', SimpleNamespace(
        kernel32=SimpleNamespace(GlobalMemoryStatusEx=failed)), raising=False)
    assert bare_monitor().get_ram_usage() is None


@pytest.mark.parametrize('total,available,expected', [
    (16 * 1024**3, 4 * 1024**3, (16.0, 4.0, 75.0)),
    (0, 0, None),
    (4 * 1024**3, 8 * 1024**3, None),
])
def test_memory_metrics_reject_invalid_capacity(monkeypatch, total, available, expected):
    def read(pointer):
        pointer._obj.ullTotalPhys = total
        pointer._obj.ullAvailPhys = available
        return 1
    monkeypatch.setattr(monitoring.ctypes, 'windll', SimpleNamespace(
        kernel32=SimpleNamespace(GlobalMemoryStatusEx=read)), raising=False)
    assert bare_monitor().get_ram_usage() == expected


def test_failed_cpu_api_preserves_last_valid_baseline(monkeypatch):
    monitor = bare_monitor()
    monitor._prev_idle, monitor._prev_total = 100, 200
    monkeypatch.setattr(monitoring.ctypes, 'windll', SimpleNamespace(
        kernel32=SimpleNamespace(GetSystemTimes=lambda *args: 0)), raising=False)
    assert monitor.get_cpu_usage() is None
    assert (monitor._prev_idle, monitor._prev_total) == (100, 200)


@pytest.mark.parametrize('previous,idle,kernel,user,expected', [
    ((0, 0), 100, 200, 100, None),
    ((100, 300), 120, 260, 140, 80.0),
    ((100, 300), 100, 200, 100, None),
    ((100, 300), 99, 200, 110, None),
    ((100, 300), 200, 210, 100, None),
])
def test_cpu_delta_needs_valid_elapsed_ticks(monkeypatch, previous, idle, kernel, user, expected):
    monitor = bare_monitor()
    monitor._prev_idle, monitor._prev_total = previous
    def read(idle_pointer, kernel_pointer, user_pointer):
        idle_pointer._obj.value = idle
        kernel_pointer._obj.value = kernel
        user_pointer._obj.value = user
        return 1
    monkeypatch.setattr(monitoring.ctypes, 'windll', SimpleNamespace(
        kernel32=SimpleNamespace(GetSystemTimes=read)), raising=False)
    assert monitor.get_cpu_usage() == expected


def test_disk_usage_queries_actual_windows_volume_not_c(monkeypatch):
    monkeypatch.setattr(monitoring, 'system_executable', lambda name: r'D:\Windows\System32\cmd.exe')
    requested = []
    def usage(path):
        requested.append(path)
        return 100 * 1024**3, 75 * 1024**3, 25 * 1024**3
    monkeypatch.setattr(monitoring.shutil, 'disk_usage', usage)
    monitor = bare_monitor()
    assert monitor.get_disk_usage() == (100.0, 25.0, 75.0)
    assert requested == ['D:\\']
    assert monitor.sample_fast()['system_drive'] == 'D:'


@pytest.mark.parametrize('capacity', [(0, 0, 0), (10, 20, -10), (10, 0, 20)])
def test_invalid_disk_capacity_is_unavailable(monkeypatch, capacity):
    monkeypatch.setattr(monitoring, 'system_executable', lambda name: r'D:\Windows\System32\cmd.exe')
    monkeypatch.setattr(monitoring.shutil, 'disk_usage', lambda path: capacity)
    assert bare_monitor().get_disk_usage() is None


def test_disk_failure_is_unavailable(monkeypatch):
    def denied(path):
        raise OSError('volume unavailable')
    monkeypatch.setattr(monitoring.shutil, 'disk_usage', denied)
    assert bare_monitor().get_disk_usage() is None


@pytest.mark.parametrize('output', [b'', b'0,0', b'null', b'{}',
    b'{"ResultCode":2,"Recommended":-1,"Optional":0}',
    b'{"ResultCode":2,"Recommended":true,"Optional":0}',
    b'{"ResultCode":2,"Recommended":0.0,"Optional":0}'])
def test_empty_or_invalid_update_result_is_never_success(monkeypatch, output):
    monitor = bare_monitor()
    monkeypatch.setattr(monitor, '_query_output', lambda *args, **kwargs: output)
    recommended, optional, status = monitor.get_windows_update_status()
    assert (recommended, optional) == (-1, -1)
    assert status != 'System Up to Date'


@pytest.mark.parametrize('code', [0, 1, 3, 4, 5])
def test_partial_or_failed_update_search_is_not_a_healthy_zero(monkeypatch, code):
    monitor = bare_monitor()
    output = json.dumps({'ResultCode': code, 'Recommended': 0, 'Optional': 0}).encode()
    monkeypatch.setattr(monitor, '_query_output', lambda *args, **kwargs: output)
    assert monitor.get_windows_update_status()[:2] == (-1, -1)


@pytest.mark.skipif(os.name != 'nt', reason='Isolated PowerShell fixture requires Windows')
@pytest.mark.parametrize('updates,expected', [
    ([], (0, 0, 'No available updates')),
    ([{'IsInstalled': False, 'IsHidden': False, 'BrowseOnly': False, 'AutoSelectOnWebSites': False},
      {'IsInstalled': False, 'IsHidden': False, 'BrowseOnly': True, 'AutoSelectOnWebSites': True},
      {'IsInstalled': False, 'IsHidden': True, 'BrowseOnly': False, 'AutoSelectOnWebSites': True},
      {'IsInstalled': True, 'IsHidden': False, 'BrowseOnly': False, 'AutoSelectOnWebSites': True}],
     (1, 1, '1 recommended, 1 optional')),
])
def test_actual_update_script_classifies_isolated_fixture_without_com(monkeypatch, updates, expected):
    monitor = bare_monitor()
    fixture = json.dumps({'ResultCode': 2, 'Updates': updates})
    prefix = """
$script:fixture = ConvertFrom-Json '%s'
$script:searcher = [pscustomobject]@{}
$script:searcher | Add-Member -MemberType ScriptMethod -Name Search -Value {
    param($criteria)
    if ($criteria -ne 'IsInstalled=0 and IsHidden=0') { throw 'Wrong search criteria' }
    return $script:fixture
}
function New-Object {
    param([string]$ComObject)
    if ($ComObject -ne 'Microsoft.Update.Session') { throw 'Unexpected COM request' }
    $session = [pscustomobject]@{}
    $session | Add-Member -MemberType ScriptMethod -Name CreateUpdateSearcher -Value { return $script:searcher }
    return $session
}
""" % fixture
    def isolated_query(arguments, timeout):
        try:
            result = monitoring.subprocess.run(arguments[:-1] + [prefix + arguments[-1]],
                capture_output=True, stdin=monitoring.subprocess.DEVNULL, timeout=timeout,
                creationflags=getattr(monitoring.subprocess, 'CREATE_NO_WINDOW', 0))
        except Exception as exc:
            pytest.fail(f'Cannot execute isolated PowerShell fixture: {exc!r}')
        if result.returncode:
            pytest.fail(f'Isolated PowerShell fixture failed: {result.stderr!r}')
        return result.stdout
    monkeypatch.setattr(monitor, '_query_output', isolated_query)
    assert monitor.get_windows_update_status() == expected


@pytest.mark.skipif(os.name != 'nt', reason='Isolated PowerShell fixture requires Windows')
def test_disk_model_script_targets_same_actual_system_volume(monkeypatch):
    monitor = bare_monitor()
    trusted_resolver = monitoring.system_executable
    monkeypatch.setattr(monitoring, 'system_executable', lambda name:
        r'D:\Windows\System32\cmd.exe' if name == 'cmd.exe' else trusted_resolver(name))
    prefix = """
function Get-Partition { param([string]$DriveLetter)
    if ($DriveLetter -ne 'D') { throw 'Wrong Windows volume' }
    [pscustomobject]@{DiskNumber=7}
}
function Get-Disk { process { [pscustomobject]@{FriendlyName='Fixture disk'; MediaType='SSD'} } }
"""
    def isolated_query(arguments, timeout):
        try:
            result = monitoring.subprocess.run(arguments[:-1] + [prefix + arguments[-1]],
                capture_output=True, stdin=monitoring.subprocess.DEVNULL, timeout=timeout,
                creationflags=getattr(monitoring.subprocess, 'CREATE_NO_WINDOW', 0))
        except Exception as exc:
            pytest.fail(f'Cannot execute isolated PowerShell fixture: {exc!r}')
        if result.returncode:
            pytest.fail(f'Isolated PowerShell fixture failed: {result.stderr!r}')
        return result.stdout
    monkeypatch.setattr(monitor, '_query_output', isolated_query)
    assert monitor.get_disk_model() == 'SSD Fixture disk'


@pytest.mark.parametrize('modules,expected', [
    ([{'ConfiguredClockSpeed': 2400, 'Speed': 3200, 'SMBIOSMemoryType': 26}],
     'DDR4 @ 2400 MHz (1 module)'),
    ([{'ConfiguredClockSpeed': 0, 'SMBIOSMemoryType': 0}],
     'Unknown type @ Unknown speed (1 module)'),
    ([{'ConfiguredClockSpeed': 3200, 'SMBIOSMemoryType': 26},
      {'ConfiguredClockSpeed': 4800, 'SMBIOSMemoryType': 34}],
     'Mixed types @ Mixed speeds (2 modules)'),
    ([{'ConfiguredClockSpeed': 3200, 'SMBIOSMemoryType': 26},
      {'ConfiguredClockSpeed': 0, 'SMBIOSMemoryType': 26}],
     'DDR4 @ Unknown speed (2 modules)'),
])
def test_ram_metadata_uses_configured_values_and_does_not_invent_type(monkeypatch, modules, expected):
    monitor = bare_monitor()
    monkeypatch.setattr(monitor, '_query_output', lambda *args, **kwargs: json.dumps(modules).encode())
    assert monitor.get_ram_info() == expected


def test_cpu_registry_handle_closes_when_frequency_lookup_fails(monkeypatch):
    key = object()
    closed = []
    def read(handle, name):
        if name == '~MHz':
            raise OSError('frequency unavailable')
        return 'Fixture CPU', 1
    monkeypatch.setitem(sys.modules, 'winreg', SimpleNamespace(HKEY_LOCAL_MACHINE=1,
        OpenKey=lambda *args: key, QueryValueEx=read, CloseKey=lambda handle: closed.append(handle)))
    monkeypatch.setattr(monitoring.platform, 'processor', lambda: 'Fallback CPU')
    assert bare_monitor().get_cpu_info() == 'Fallback CPU'
    assert closed == [key]


def test_cpu_does_not_present_one_processor_group_as_whole_system(monkeypatch):
    monitor = bare_monitor()
    monitor._prev_idle, monitor._prev_total = 100, 300
    def read(idle_pointer, kernel_pointer, user_pointer):
        idle_pointer._obj.value = 120
        kernel_pointer._obj.value = 260
        user_pointer._obj.value = 140
        return 1
    monkeypatch.setattr(monitoring.ctypes, 'windll', SimpleNamespace(kernel32=SimpleNamespace(
        GetActiveProcessorGroupCount=lambda: 2, GetSystemTimes=read)), raising=False)
    assert monitor.get_cpu_usage() is None


@pytest.mark.skipif(os.name != 'nt', reason='Isolated PowerShell fixture requires Windows')
def test_ram_query_selects_configured_clock_from_isolated_cim_fixture(monkeypatch):
    monitor = bare_monitor()
    prefix = """
function Get-CimInstance { param([string]$ClassName)
    if ($ClassName -ne 'Win32_PhysicalMemory') { throw 'Unexpected CIM class' }
    [pscustomobject]@{ConfiguredClockSpeed=2400; Speed=3200; SMBIOSMemoryType=26}
}
"""
    def isolated_query(arguments, timeout):
        try:
            result = monitoring.subprocess.run(arguments[:-1] + [prefix + arguments[-1]],
                capture_output=True, stdin=monitoring.subprocess.DEVNULL, timeout=timeout,
                creationflags=getattr(monitoring.subprocess, 'CREATE_NO_WINDOW', 0))
        except Exception as exc:
            pytest.fail(f'Cannot execute isolated PowerShell fixture: {exc!r}')
        if result.returncode:
            pytest.fail(f'Isolated PowerShell fixture failed: {result.stderr!r}')
        return result.stdout
    monkeypatch.setattr(monitor, '_query_output', isolated_query)
    assert monitor.get_ram_info() == 'DDR4 @ 2400 MHz (1 module)'



def test_windows_product_edition_from_registry_without_spawning_processes(monkeypatch):
    from contextlib import nullcontext
    import sys
    class Registry:
        HKEY_LOCAL_MACHINE = object()
        @staticmethod
        def OpenKey(root, path):
            assert 'CurrentVersion' in path
            return nullcontext(object())
        @staticmethod
        def QueryValueEx(key, name):
            return {'ProductName': ('Windows 10 Pro', 1),
                    'CurrentBuildNumber': ('22631', 1),
                    'EditionID': ('Professional', 1)}[name]
    monkeypatch.setitem(sys.modules, 'winreg', Registry)
    assert bare_monitor().get_os_info() == 'Windows 11 Pro'


def test_battery_flag_distinguishes_actively_charging_from_plugged_in(monkeypatch):
    def make_query(flag):
        def query(pointer):
            pointer._obj.BatteryLifePercent = 52
            pointer._obj.ACLineStatus = 1
            pointer._obj.BatteryFlag = flag
            return 1
        return query
    api = SimpleNamespace()
    monkeypatch.setattr(monitoring.ctypes, 'windll',
                        SimpleNamespace(kernel32=api), raising=False)
    api.GetSystemPowerStatus = make_query(8)
    assert bare_monitor().get_battery_status() == (52, 'Charging')
    api.GetSystemPowerStatus = make_query(0)
    assert bare_monitor().get_battery_status() == (52, 'Plugged In')
