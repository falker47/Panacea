import ctypes
from types import SimpleNamespace
from modules.system_monitor import SystemMonitor
import modules.system_monitor as monitoring


def bare_monitor():
    monitor = SystemMonitor.__new__(SystemMonitor)
    monitor._cache = {}
    monitor._cache_ttl = 120
    return monitor


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
    def check_output(arguments, **kwargs):
        calls.append((arguments, kwargs))
        return output
    monkeypatch.setattr(monitoring.subprocess, 'check_output', check_output)
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
    monkeypatch.setattr(monitoring.subprocess, 'check_output', lambda *args, **kwargs: calls.append(args))
    assert getattr(bare_monitor(), method)() == expected
    assert calls == []
