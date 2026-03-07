import ctypes
import ctypes.wintypes as wintypes
import os
import platform
import shutil
import subprocess
import winreg
from modules.logger import Logger
from modules.utils import NO_WINDOW, SUBPROCESS_TIMEOUT

_UPDATE_CHECK_TIMEOUT = 45  # seconds – Windows Update search is slow


# ---------------------------------------------------------------------------
# ctypes structures (defined once at module level, not per-call)
# ---------------------------------------------------------------------------
class _MEMORYSTATUSEX(ctypes.Structure):
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


class _SYSTEM_POWER_STATUS(ctypes.Structure):
    _fields_ = [
        ('ACLineStatus', ctypes.c_byte),
        ('BatteryFlag', ctypes.c_byte),
        ('BatteryLifePercent', ctypes.c_byte),
        ('SystemStatusFlag', ctypes.c_byte),
        ('BatteryLifeTime', ctypes.c_ulong),
        ('BatteryFullLifeTime', ctypes.c_ulong),
    ]


class _FILETIME(ctypes.Structure):
    _fields_ = [
        ("dwLowDateTime", wintypes.DWORD),
        ("dwHighDateTime", wintypes.DWORD),
    ]


def _filetime_to_int(ft: _FILETIME) -> int:
    return (ft.dwHighDateTime << 32) | ft.dwLowDateTime


class SystemMonitor:
    def __init__(self):
        self.logger = Logger()

        # Caches for static hardware info (never changes at runtime)
        self._cpu_info: str | None = None
        self._os_info: str | None = None
        self._ram_info: str | None = None
        self._disk_model: str | None = None

        # CPU usage via GetSystemTimes (delta between two calls)
        self._prev_idle: int = 0
        self._prev_kernel: int = 0
        self._prev_user: int = 0
        self._cpu_initialized = False

    # -------------------------------------------------------------------
    # RAM
    # -------------------------------------------------------------------
    def get_ram_usage(self) -> tuple[float, float, float]:
        """Returns (total_gb, available_gb, percent_used)."""
        try:
            stat = _MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))

            total_gb = stat.ullTotalPhys / (1024 ** 3)
            avail_gb = stat.ullAvailPhys / (1024 ** 3)
            percent = ((total_gb - avail_gb) / total_gb) * 100 if total_gb > 0 else 0
            return round(total_gb, 1), round(avail_gb, 1), round(percent, 1)
        except Exception as e:
            self.logger.log(f"get_ram_usage failed: {e}", "WARNING")
            return 0, 0, 0

    def get_ram_info(self) -> str:
        """Returns RAM details like 'DDR4 @ 3200 MHz (2 Moduli)'. Cached."""
        if self._ram_info is not None:
            return self._ram_info
        try:
            cmd = 'wmic memorychip get Speed,SMBIOSMemoryType /format:csv'
            output = subprocess.check_output(
                cmd, shell=True, creationflags=NO_WINDOW, timeout=SUBPROCESS_TIMEOUT
            ).decode()
            lines = [l.strip() for l in output.split('\n') if l.strip()]
            if len(lines) < 2:
                return ""

            header = lines[0].split(',')
            speed_idx = type_idx = -1
            for i, col in enumerate(header):
                if "Speed" in col:
                    speed_idx = i
                if "SMBIOSMemoryType" in col:
                    type_idx = i
            if speed_idx == -1 or type_idx == -1:
                return ""

            data_lines = lines[1:]
            module_count = len(data_lines)
            parts = data_lines[0].split(',')
            if len(parts) <= max(speed_idx, type_idx):
                return ""

            speed = parts[speed_idx]
            try:
                smbios_type = int(parts[type_idx])
            except (ValueError, IndexError):
                smbios_type = 0

            type_map = {20: "DDR", 21: "DDR2", 24: "DDR3", 26: "DDR4", 34: "DDR5"}
            ddr_type = type_map.get(smbios_type, "DDR")

            self._ram_info = f"{ddr_type} @ {speed} MHz ({module_count} Moduli)"
            return self._ram_info
        except Exception as e:
            self.logger.log(f"get_ram_info failed: {e}", "WARNING")
            return ""

    # -------------------------------------------------------------------
    # Disk
    # -------------------------------------------------------------------
    def get_disk_usage(self) -> tuple[float, float, float]:
        """Returns (total_gb, free_gb, percent_used) for C:."""
        try:
            total, used, free = shutil.disk_usage("C:\\")
            total_gb = total / (1024 ** 3)
            free_gb = free / (1024 ** 3)
            percent = (used / total) * 100
            return round(total_gb, 1), round(free_gb, 1), round(percent, 1)
        except Exception as e:
            self.logger.log(f"get_disk_usage failed: {e}", "WARNING")
            return 0, 0, 0

    def get_disk_model(self) -> str:
        """Returns disk model string. Cached after first call."""
        if self._disk_model is not None:
            return self._disk_model
        try:
            # Single PowerShell call for both FriendlyName and MediaType
            cmd = [
                'powershell', '-Command',
                "Get-Partition -DriveLetter C | Get-Disk | "
                "Select-Object FriendlyName, MediaType | ConvertTo-Json"
            ]
            output = subprocess.check_output(
                cmd, creationflags=NO_WINDOW, timeout=SUBPROCESS_TIMEOUT
            ).decode().strip()

            if not output:
                return "Unknown Model"

            import json
            data = json.loads(output)
            model_name = data.get("FriendlyName", "").strip()
            media_type = data.get("MediaType", "").strip()

            if not model_name:
                return "Unknown Model"

            if media_type in ("SSD", "HDD") and media_type not in model_name:
                self._disk_model = f"{media_type} {model_name}"
            else:
                self._disk_model = model_name
            return self._disk_model
        except Exception as e:
            self.logger.log(f"get_disk_model failed: {e}", "WARNING")
            return "Unknown Model"

    # -------------------------------------------------------------------
    # CPU
    # -------------------------------------------------------------------
    def get_cpu_info(self) -> str:
        """Returns CPU name with cores and frequency. Cached."""
        if self._cpu_info is not None:
            return self._cpu_info
        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
            cpu_name, _ = winreg.QueryValueEx(key, "ProcessorNameString")
            mhz, _ = winreg.QueryValueEx(key, "~MHz")
            winreg.CloseKey(key)

            cores = os.cpu_count() or 0
            ghz = round(mhz / 1000, 1)
            self._cpu_info = f"{cpu_name.strip()}\n({cores} Cores @ {ghz} GHz)"
            return self._cpu_info
        except Exception as e:
            self.logger.log(f"get_cpu_info failed: {e}", "WARNING")
            return platform.processor()

    def get_cpu_usage(self) -> float:
        """Returns CPU usage percent using native GetSystemTimes (no subprocess)."""
        try:
            idle, kernel, user = _FILETIME(), _FILETIME(), _FILETIME()
            ctypes.windll.kernel32.GetSystemTimes(
                ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user))

            idle_val = _filetime_to_int(idle)
            kernel_val = _filetime_to_int(kernel)
            user_val = _filetime_to_int(user)

            if not self._cpu_initialized:
                self._prev_idle = idle_val
                self._prev_kernel = kernel_val
                self._prev_user = user_val
                self._cpu_initialized = True
                return 0.0

            d_idle = idle_val - self._prev_idle
            d_kernel = kernel_val - self._prev_kernel
            d_user = user_val - self._prev_user

            self._prev_idle = idle_val
            self._prev_kernel = kernel_val
            self._prev_user = user_val

            # kernel time includes idle time
            total = d_kernel + d_user
            if total == 0:
                return 0.0

            usage = ((total - d_idle) / total) * 100
            return round(max(0.0, min(100.0, usage)), 1)
        except Exception as e:
            self.logger.log(f"get_cpu_usage (native) failed: {e}", "WARNING")
            return 0.0

    # -------------------------------------------------------------------
    # OS / Uptime
    # -------------------------------------------------------------------
    def get_os_info(self) -> str:
        """Returns OS string. Cached."""
        if self._os_info is not None:
            return self._os_info
        try:
            self._os_info = f"{platform.system()} {platform.release()}"
            return self._os_info
        except Exception as e:
            self.logger.log(f"get_os_info failed: {e}", "WARNING")
            return "Windows"

    def get_system_uptime(self) -> str:
        """Returns string 'Dd Hh Mm'."""
        try:
            t = ctypes.windll.kernel32.GetTickCount64() / 1000
            days = int(t // 86400)
            hours = int((t % 86400) // 3600)
            mins = int((t % 3600) // 60)
            return f"{days}d {hours}h {mins}m"
        except Exception as e:
            self.logger.log(f"get_system_uptime failed: {e}", "WARNING")
            return "Unknown"

    # -------------------------------------------------------------------
    # Battery
    # -------------------------------------------------------------------
    def get_battery_status(self) -> tuple[int, str]:
        """Returns (percent, is_plugged_str)."""
        try:
            status = _SYSTEM_POWER_STATUS()
            if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
                percent = status.BatteryLifePercent
                plugged = "Plugged In" if status.ACLineStatus == 1 else "On Battery"
                if percent == 255:
                    return (0, "Unknown")
                return (percent, plugged)
        except Exception as e:
            self.logger.log(f"get_battery_status failed: {e}", "WARNING")
        return (0, "Unknown")

    # -------------------------------------------------------------------
    # Windows Updates
    # -------------------------------------------------------------------
    def get_windows_update_status(self) -> tuple[int, int, str]:
        """Returns (mandatory_count, optional_count, status_str)."""
        try:
            ps_script = """
$session = New-Object -ComObject Microsoft.Update.Session
$searcher = $session.CreateUpdateSearcher()
$result = $searcher.Search('IsInstalled=0')
$mandatory = 0
$optional = 0
foreach ($update in $result.Updates) {
    if ($update.AutoSelectOnWebSites) { $mandatory++ } else { $optional++ }
}
Write-Output "$mandatory,$optional"
"""
            cmd = ['powershell', '-Command', ps_script]
            output = subprocess.check_output(
                cmd, creationflags=NO_WINDOW, timeout=_UPDATE_CHECK_TIMEOUT
            ).decode().strip()

            lines = output.splitlines()
            if not lines:
                return 0, 0, "Unknown"

            parts = lines[-1].split(',')
            if len(parts) == 2:
                mandatory = int(parts[0])
                optional = int(parts[1])
            else:
                return -1, -1, "Parse Error"

            if mandatory == 0 and optional == 0:
                return 0, 0, "System Up to Date"
            elif mandatory > 0 and optional > 0:
                return mandatory, optional, f"{mandatory} Required, {optional} Optional"
            elif mandatory > 0:
                return mandatory, 0, f"{mandatory} Required Updates"
            else:
                return 0, optional, f"{optional} Optional Updates"

        except subprocess.TimeoutExpired:
            return -1, -1, "Check Timed Out"
        except Exception as e:
            self.logger.log(f"get_windows_update_status failed: {e}", "WARNING")
            return -1, -1, "Check Failed"
