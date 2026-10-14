import ctypes
import os
import platform
import shutil
import subprocess
import time
import threading
import logging
import json
import ntpath
from modules.commands import system_executable, validate_drive


_PS_QUERY_PREFIX = "$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false); "

class SystemMonitor:
    def __init__(self):
        self._query_lock = threading.Lock()
        self._query_processes = {}
        self._query_closed = threading.Event()
        self._close_lock = threading.Lock()
        self._query_reaper = None
        # Store previous CPU times for delta-based usage calculation
        self._prev_idle = 0
        self._prev_total = 0
        self.get_cpu_usage()  # Prime initial values so first real call has a delta
        # Cache for slow calls (wmic/PowerShell)
        self._cache = {}
        self._cache_ttl = 120  # seconds

    def _query_output(self, arguments, timeout):
        """Own each read-only query from atomic creation through process reap."""
        process = None
        reap_lock = threading.Lock()
        try:
            # Close's UI-side Event never waits on this lock. Its cancellation
            # thread waits until any in-flight CreateProcess is registered.
            with self._query_lock:
                if self._query_closed.is_set():
                    raise RuntimeError('System monitor is closed')
                process = subprocess.Popen(arguments, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                           stdin=subprocess.DEVNULL, shell=False,
                                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                self._query_processes[process] = reap_lock
            if self._query_closed.is_set():
                raise RuntimeError('System monitor is closed')
            output, error = process.communicate(timeout=timeout)
            if self._query_closed.is_set():
                raise RuntimeError('System monitor is closed')
            if process.returncode:
                raise subprocess.CalledProcessError(process.returncode, arguments, output=output, stderr=error)
            return output
        finally:
            if process is not None:
                self._reap_query(process, reap_lock)
                # Only the communicating worker closes its streams. A close
                # reaper must not race an active Windows pipe reader.
                if process.poll() is not None:
                    for stream in (process.stdin, process.stdout, process.stderr):
                        if stream is not None:
                            try:
                                stream.close()
                            except OSError:
                                logging.getLogger(__name__).exception('Cannot close owned monitor query pipe')

    def _reap_query(self, process, reap_lock):
        # Communication may finish concurrently with cancellation. Serialize
        # cleanup per handle, never block Tk, and never target an unowned PID.
        with reap_lock:
            try:
                if process.poll() is None:
                    try:
                        process.kill()
                    except OSError:
                        # It may have exited between poll and TerminateProcess.
                        if process.poll() is None:
                            raise
                process.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                logging.getLogger(__name__).exception('Cannot reap owned monitor query')
            finally:
                with self._query_lock:
                    self._query_processes.pop(process, None)

    def close(self):
        """Cancel only owned read-only queries without blocking the UI thread."""
        self._query_closed.set()
        with self._close_lock:
            if self._query_reaper is not None:
                return
            def cancel_owned():
                with self._query_lock:
                    owned = tuple(self._query_processes.items())
                for process, reap_lock in owned:
                    self._reap_query(process, reap_lock)
            # Keep interpreter shutdown alive just long enough to reap our
            # children after Tk closes; daemon query workers alone cannot do it.
            self._query_reaper = threading.Thread(target=cancel_owned, name='panacea-monitor-close', daemon=False)
            self._query_reaper.start()

    def _cached(self, key, func):
        """Return cached result if fresh, otherwise call func and cache it."""
        now = time.monotonic()
        if key in self._cache:
            val, ts = self._cache[key]
            if now - ts < self._cache_ttl:
                return val
        val = func()
        self._cache[key] = (val, time.monotonic())
        return val

    def sample_fast(self):
        """Only native, low-latency samples; hardware metadata runs independently."""
        return {"ram": self.get_ram_usage(), "disk": self.get_disk_usage(),
                "cpu": self.get_cpu_usage(), "uptime": self.get_system_uptime(),
                "battery": self.get_battery_status(), "system_drive": self.get_system_drive()}

    def sample_metadata(self):
        return {"os": self.get_os_info(), "cpu_name": self.get_cpu_info(),
                "ram_info": self.get_ram_info(), "disk_model": self.get_disk_model()}

    def get_ram_usage(self):
        """Return (total_gb, available_gb, percent_used), or None if unavailable."""
        try:
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                return None
            if stat.ullTotalPhys <= 0 or stat.ullAvailPhys > stat.ullTotalPhys:
                return None
            
            total_gb = stat.ullTotalPhys / (1024**3)
            avail_gb = stat.ullAvailPhys / (1024**3)
            # Calculate percent as float for decimal display
            percent = ((total_gb - avail_gb) / total_gb) * 100
            
            return round(total_gb, 1), round(avail_gb, 1), round(percent, 1)
        except Exception:
            return None

    def get_ram_info(self):
        """Return cached configured RAM details without guessing missing values."""
        return self._cached("ram_info", self._fetch_ram_info)

    def _fetch_ram_info(self):
        try:
            # wmic was removed in Windows 11 24H2+; use CIM via PowerShell.
            cmd = [system_executable('powershell.exe'), '-NoProfile', '-Command',
                   _PS_QUERY_PREFIX + "Get-CimInstance Win32_PhysicalMemory | "
                   "Select-Object ConfiguredClockSpeed, SMBIOSMemoryType | ConvertTo-Json -Compress"]
            output = self._query_output(cmd, timeout=15).decode('utf-8-sig').strip()

            if not output:
                return ""

            data = json.loads(output)
            # Single module: PowerShell returns an object, not an array
            if isinstance(data, dict):
                data = [data]
            if not data:
                return ""

            # SMBIOSMemoryType: 20=DDR, 21=DDR2, 24=DDR3, 26=DDR4, 34=DDR5
            type_map = {20: "DDR", 21: "DDR2", 24: "DDR3", 26: "DDR4", 34: "DDR5"}
            types = {type_map.get(int(module.get('SMBIOSMemoryType') or 0), 'Unknown type')
                     for module in data}
            speeds = {int(module.get('ConfiguredClockSpeed') or 0) for module in data}
            memory_type = next(iter(types)) if len(types) == 1 else 'Mixed types'
            if any(speed <= 0 for speed in speeds):
                speed = 'Unknown speed'
            elif len(speeds) > 1:
                speed = 'Mixed speeds'
            else:
                speed = f'{next(iter(speeds))} MHz'
            count = len(data)
            return f"{memory_type} @ {speed} ({count} {'module' if count == 1 else 'modules'})"
        except Exception:
            return ""

    def get_system_drive(self):
        """Resolve the actual Windows volume through the trusted native resolver."""
        try:
            return validate_drive(ntpath.splitdrive(system_executable('cmd.exe'))[0])
        except (OSError, ValueError, TypeError, AttributeError):
            return None

    def get_disk_usage(self):
        """Return system-volume capacity and usage, or None if unavailable."""
        try:
            drive = self.get_system_drive()
            if drive is None:
                return None
            total, used, free = shutil.disk_usage(drive + '\\')
            if total <= 0 or not 0 <= used <= total or not 0 <= free <= total:
                return None
            total_gb = total / (1024**3)
            free_gb = free / (1024**3)
            percent = (used / total) * 100
            return round(total_gb, 1), round(free_gb, 1), round(percent, 1)
        except Exception:
            return None

    def get_disk_model(self):
        """Returns disk model string e.g. 'SSD Samsung MZVLB1T0...' (cached)"""
        return self._cached("disk_model", self._fetch_disk_model)

    def _fetch_disk_model(self):
        try:
            drive = self.get_system_drive()
            if drive is None:
                return "Unknown Model"
            cmd = [system_executable('powershell.exe'), '-NoProfile', '-Command',
                   _PS_QUERY_PREFIX + f"Get-Partition -DriveLetter {drive[0]} | Get-Disk | "
                   "ForEach-Object { $_.FriendlyName + '|' + $_.MediaType }"]
            output = self._query_output(cmd, timeout=15).decode('utf-8-sig').strip()

            if '|' in output:
                model_name, media_type = output.rsplit('|', 1)
                model_name = model_name.strip()
                media_type = media_type.strip()
                if media_type in ("SSD", "HDD") and media_type not in model_name:
                    return f"{media_type} {model_name}"
                return model_name or "Unknown Model"

            return output or "Unknown Model"
        except Exception:
            return "Unknown Model"

    def get_cpu_info(self):
        """Returns CPU name with cores and frequency"""
        try:
            import winreg
            # Get CPU name from registry (more readable than platform.processor())
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                                  r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
            try:
                cpu_name, _ = winreg.QueryValueEx(key, "ProcessorNameString")
                mhz, _ = winreg.QueryValueEx(key, "~MHz")
            finally:
                winreg.CloseKey(key)
            
            cores = os.cpu_count() or 0
            
            # Format: "AMD Ryzen 7 5800X\n(8 Cores @ 3.8 GHz)"
            ghz = round(mhz / 1000, 1)
            return f"{cpu_name.strip()}\n({cores} logical processors @ {ghz} GHz)"
        except Exception:
            return platform.processor()
            
    def get_os_info(self):
        try:
            return f"{platform.system()} {platform.release()}"
        except Exception:
            return "Windows"

    def get_system_uptime(self):
        """Returns string 'D days, H hours, M mins'"""
        try:
            # GetTickCount64 returns milliseconds
            lib = ctypes.windll.kernel32
            lib.GetTickCount64.restype = ctypes.c_uint64
            t = lib.GetTickCount64()
            t = t / 1000
            days = t // 86400
            hours = (t % 86400) // 3600
            mins = (t % 3600) // 60
            return f"{int(days)}d {int(hours)}h {int(mins)}m"
        except Exception:
            return "Unknown"

    def get_cpu_usage(self):
        """Return native CPU delta percent, or None without a valid measurement."""
        try:
            kernel32 = ctypes.windll.kernel32
            groups = getattr(kernel32, 'GetActiveProcessorGroupCount', None)
            # GetSystemTimes covers only the calling thread's primary group.
            # Do not label a partial measurement as aggregate CPU usage.
            if groups is not None and groups() > 1:
                return None
            idle = ctypes.c_ulonglong()
            kernel = ctypes.c_ulonglong()
            user = ctypes.c_ulonglong()
            if not kernel32.GetSystemTimes(
                ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)
            ):
                return None
            idle_val = idle.value
            total_val = kernel.value + user.value

            if self._prev_total == 0:
                # An initial snapshot is a baseline, not a 0% usage measurement.
                self._prev_idle = idle_val
                self._prev_total = total_val
                return None

            d_idle = idle_val - self._prev_idle
            d_total = total_val - self._prev_total
            self._prev_idle = idle_val
            self._prev_total = total_val

            if d_total <= 0 or not 0 <= d_idle <= d_total:
                return None
            return round((1.0 - d_idle / d_total) * 100, 1)
        except Exception:
            return None

    def get_battery_status(self):
        """Returns (percent, is_plugged_str)"""
        class SYSTEM_POWER_STATUS(ctypes.Structure):
            _fields_ = [
                ('ACLineStatus', ctypes.c_ubyte),
                ('BatteryFlag', ctypes.c_ubyte),
                ('BatteryLifePercent', ctypes.c_ubyte),
                ('SystemStatusFlag', ctypes.c_ubyte),
                ('BatteryLifeTime', ctypes.c_uint32),
                ('BatteryFullLifeTime', ctypes.c_uint32),
            ]
        status = SYSTEM_POWER_STATUS()
        try:
            if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
                percent = status.BatteryLifePercent
                if percent > 100 or status.BatteryFlag & 128:
                    return (None, "Unknown")
                plugged = {0: "On Battery", 1: "Plugged In"}.get(status.ACLineStatus, "Unknown")
                return (percent, plugged)
        except (AttributeError, OSError):
            pass
        return (None, "Unknown")

    def get_windows_update_status(self):
        """Return (recommended, optional, status); -1 counts mean unverified.

        BrowseOnly identifies optional updates. AutoSelectOnWebSites only
        describes automatic selection and must not be called mandatory.
        """
        try:
            ps_script = _PS_QUERY_PREFIX + """
Set-StrictMode -Version 2.0
$session = New-Object -ComObject Microsoft.Update.Session
$searcher = $session.CreateUpdateSearcher()
$result = $searcher.Search('IsInstalled=0 and IsHidden=0')
$recommended = 0
$optional = 0
foreach ($update in $result.Updates) {
    if ($update.IsHidden -or $update.IsInstalled) { continue }
    if ($update.BrowseOnly) { $optional++ } else { $recommended++ }
}
[pscustomobject]@{ResultCode=[int]$result.ResultCode; Recommended=$recommended; Optional=$optional} | ConvertTo-Json -Compress
"""
            cmd = [system_executable('powershell.exe'), '-NoProfile', '-Command', ps_script]
            output = self._query_output(cmd, timeout=45).decode('utf-8-sig').strip()
            if not output:
                return -1, -1, "Check unavailable"
            result = json.loads(output)
            if not isinstance(result, dict):
                return -1, -1, "Parse Error"
            code = result.get('ResultCode')
            if type(code) is not int or code != 2:
                return -1, -1, "Check incomplete" if code == 3 else "Check Failed"
            recommended, optional = result.get('Recommended'), result.get('Optional')
            if any(type(count) is not int or count < 0 for count in (recommended, optional)):
                return -1, -1, "Parse Error"

            if recommended == optional == 0:
                return 0, 0, "No available updates"
            elif recommended > 0 and optional > 0:
                return recommended, optional, f"{recommended} recommended, {optional} optional"
            elif recommended > 0:
                return recommended, 0, f"{recommended} recommended updates"
            else:
                return 0, optional, f"{optional} optional updates"
                
        except subprocess.TimeoutExpired:
            return -1, -1, "Check Timed Out"
        except Exception:
            return -1, -1, "Check Failed"
