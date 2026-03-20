import ctypes
import os
import platform
import shutil
import subprocess
import time

class SystemMonitor:
    def __init__(self):
        # Store previous CPU times for delta-based usage calculation
        self._prev_idle = 0
        self._prev_total = 0
        self.get_cpu_usage()  # Prime initial values so first real call has a delta
        # Cache for slow calls (wmic/PowerShell)
        self._cache = {}
        self._cache_ttl = 120  # seconds

    def _cached(self, key, func):
        """Return cached result if fresh, otherwise call func and cache it."""
        now = time.time()
        if key in self._cache:
            val, ts = self._cache[key]
            if now - ts < self._cache_ttl:
                return val
        val = func()
        self._cache[key] = (val, now)
        return val

    def get_ram_usage(self):
        """Returns (total_gb, available_gb, percent_used)"""
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
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            
            total_gb = stat.ullTotalPhys / (1024**3)
            avail_gb = stat.ullAvailPhys / (1024**3)
            # Calculate percent as float for decimal display
            percent = ((total_gb - avail_gb) / total_gb) * 100 if total_gb > 0 else 0
            
            return round(total_gb, 1), round(avail_gb, 1), round(percent, 1)
        except Exception:
            return 0, 0, 0

    def get_ram_info(self):
        """Returns RAM details string like 'DDR4 @ 3200 MHz (2 Moduli)' (cached)"""
        return self._cached("ram_info", self._fetch_ram_info)

    def _fetch_ram_info(self):
        try:
            cmd = 'wmic memorychip get Speed,SMBIOSMemoryType /format:csv'
            output = subprocess.check_output(cmd, shell=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW).decode()
            lines = [l.strip() for l in output.split('\n') if l.strip()]
            
            if len(lines) < 2:
                # Should be at least header + 1 data line
                return ""
            
            # Header line: Node,SMBIOSMemoryType,Speed (order may vary)
            header = lines[0].split(',')
            
            # Identify columns
            speed_idx = -1
            type_idx = -1
            
            for i, col in enumerate(header):
                if "Speed" in col: speed_idx = i
                if "SMBIOSMemoryType" in col: type_idx = i
            
            if speed_idx == -1 or type_idx == -1:
                return ""

            # Data lines
            data_lines = lines[1:]
            module_count = len(data_lines)
            
            # Parse first module
            parts = data_lines[0].split(',')
            
            if len(parts) <= max(speed_idx, type_idx):
                return ""
                
            speed = parts[speed_idx]
            try:
                smbios_type = int(parts[type_idx])
            except (ValueError, IndexError):
                smbios_type = 0
            
            # SMBIOSMemoryType: 20=DDR, 21=DDR2, 24=DDR3, 26=DDR4, 34=DDR5
            type_map = {20: "DDR", 21: "DDR2", 24: "DDR3", 26: "DDR4", 34: "DDR5"}
            ddr_type = type_map.get(smbios_type, "DDR")
            
            return f"{ddr_type} @ {speed} MHz ({module_count} Moduli)"
        except Exception as e:
            return ""

    def get_disk_usage(self):
        """Returns (total_gb, free_gb, percent_used) for C:"""
        try:
            total, used, free = shutil.disk_usage("C:\\")
            total_gb = total / (1024**3)
            free_gb = free / (1024**3)
            percent = (used / total) * 100 if total > 0 else 0
            return round(total_gb, 1), round(free_gb, 1), round(percent, 1)
        except Exception:
            return 0, 0, 0

    def get_disk_model(self):
        """Returns disk model string e.g. 'SSD Samsung MZVLB1T0...' (cached)"""
        return self._cached("disk_model", self._fetch_disk_model)

    def _fetch_disk_model(self):
        try:
            cmd = ['powershell', '-NoProfile', '-Command',
                   "Get-Partition -DriveLetter C | Get-Disk | ForEach-Object { $_.FriendlyName + '|' + $_.MediaType }"]
            output = subprocess.check_output(cmd, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW).decode().strip()

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
            cpu_name, _ = winreg.QueryValueEx(key, "ProcessorNameString")
            mhz, _ = winreg.QueryValueEx(key, "~MHz")
            winreg.CloseKey(key)
            
            cores = os.cpu_count() or 0
            
            # Format: "AMD Ryzen 7 5800X\n(8 Cores @ 3.8 GHz)"
            ghz = round(mhz / 1000, 1)
            return f"{cpu_name.strip()}\n({cores} Cores @ {ghz} GHz)"
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
            t = lib.GetTickCount64()
            t = t / 1000
            days = t // 86400
            hours = (t % 86400) // 3600
            mins = (t % 3600) // 60
            return f"{int(days)}d {int(hours)}h {int(mins)}m"
        except Exception:
            return "Unknown"

    def get_cpu_usage(self):
        """Returns CPU usage percent using GetSystemTimes (no subprocess overhead)."""
        try:
            idle = ctypes.c_ulonglong()
            kernel = ctypes.c_ulonglong()
            user = ctypes.c_ulonglong()
            ctypes.windll.kernel32.GetSystemTimes(
                ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)
            )
            idle_val = idle.value
            total_val = kernel.value + user.value

            if self._prev_total == 0:
                # First call — no delta yet, return 0
                self._prev_idle = idle_val
                self._prev_total = total_val
                return 0.0

            d_idle = idle_val - self._prev_idle
            d_total = total_val - self._prev_total
            self._prev_idle = idle_val
            self._prev_total = total_val

            if d_total == 0:
                return 0.0
            return round((1.0 - d_idle / d_total) * 100, 1)
        except Exception:
            return 0.0

    def get_battery_status(self):
        """Returns (percent, is_plugged_str)"""
        class SYSTEM_POWER_STATUS(ctypes.Structure):
            _fields_ = [
                ('ACLineStatus', ctypes.c_byte),
                ('BatteryFlag', ctypes.c_byte),
                ('BatteryLifePercent', ctypes.c_byte),
                ('SystemStatusFlag', ctypes.c_byte),
                ('BatteryLifeTime', ctypes.c_ulong),
                ('BatteryFullLifeTime', ctypes.c_ulong),
            ]
        status = SYSTEM_POWER_STATUS()
        if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
            percent = status.BatteryLifePercent
            plugged = "Plugged In" if status.ACLineStatus == 1 else "On Battery"
            if percent == 255: return (0, "Unknown")
            return (percent, plugged)
        return (0, "Unknown")

    def get_windows_update_status(self):
        """Returns (mandatory_count, optional_count, status_str)"""
        try:
            # PowerShell script to count mandatory vs optional updates
            # AutoSelectOnWebSites = True means mandatory (security, critical), False means optional (driver, feature)
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
            cmd = ['powershell', '-NoProfile', '-Command', ps_script]
            output = subprocess.check_output(cmd, creationflags=subprocess.CREATE_NO_WINDOW, timeout=45).decode().strip()
            
            lines = output.splitlines()
            if not lines: return 0, 0, "Unknown"
            
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
            return -1, -1, "Check Failed"
