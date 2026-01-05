import ctypes
import os
import platform
import shutil
import subprocess
import threading
import time

class SystemMonitor:
    def __init__(self):
        pass

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
        except:
            return 0, 0, 0

    def get_ram_info(self):
        """Returns RAM details string like 'DDR4 @ 3200 MHz (2 Moduli)'"""
        try:
            import subprocess
            # Query WMI for memory modules - use comma without space
            cmd = 'wmic memorychip get Speed,SMBIOSMemoryType'
            output = subprocess.check_output(cmd, shell=True, creationflags=subprocess.CREATE_NO_WINDOW).decode()
            lines = [l.strip() for l in output.split('\n') if l.strip()]
            
            # Skip header line
            data_lines = [l for l in lines if not l.startswith('SMBIOS') and not l.startswith('Speed')]
            if not data_lines:
                return ""
            
            module_count = len(data_lines)
            
            # Parse first module - format is "Speed  SMBIOSMemoryType" like "3200  26"
            parts = data_lines[0].split()
            speed = parts[0] if parts else "?"
            smbios_type = int(parts[-1]) if len(parts) > 0 else 0
            
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
            percent = (used / total) * 100
            return round(total_gb, 1), round(free_gb, 1), round(percent, 1)
        except:
            return 0, 0, 0

    def get_disk_model(self):
        """Returns disk model string e.g. 'SSD Samsung MZVLB1T0...'"""
        try:
            import subprocess
            # 1. Get FriendlyName (Model) reliably
            cmd_model = ['powershell', '-Command', "Get-Partition -DriveLetter C | Get-Disk | Select-Object -ExpandProperty FriendlyName"]
            try:
                model_name = subprocess.check_output(cmd_model, creationflags=subprocess.CREATE_NO_WINDOW).decode().strip()
            except:
                return "Unknown Model"

            if not model_name: return "Unknown Model"

            # 2. Try to get MediaType separately (Non-critical)
            try:
                cmd_type = ['powershell', '-Command', "Get-Partition -DriveLetter C | Get-Disk | Select-Object -ExpandProperty MediaType"]
                media_type = subprocess.check_output(cmd_type, creationflags=subprocess.CREATE_NO_WINDOW).decode().strip() # SSD or HDD
                
                # If media type is known and not in name, prepend it
                if media_type in ["SSD", "HDD"] and media_type not in model_name:
                    return f"{media_type} {model_name}"
            except:
                pass # If media type fails, just return model name

            return model_name
        except:
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
            
            # Get core count
            import os
            cores = os.cpu_count() or 0
            
            # Format: "AMD Ryzen 7 5800X\n(8 Cores @ 3.8 GHz)"
            ghz = round(mhz / 1000, 1)
            return f"{cpu_name.strip()}\n({cores} Cores @ {ghz} GHz)"
        except:
            # Fallback
            return platform.processor()
            
    def get_os_info(self):
        try:
            return f"{platform.system()} {platform.release()}"
        except:
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
        except:
            return "Unknown"

    def get_cpu_usage(self):
        """Returns int cpu percent. Tries typeperf (fast) then wmic (reliable)."""
        # Try typeperf first (English locale usually)
        try:
            cmd = ['typeperf', r'\Processor(_Total)\% Processor Time', '-sc', '1']
            output = subprocess.check_output(cmd, creationflags=subprocess.CREATE_NO_WINDOW).decode()
            lines = output.strip().split('\n')
            if len(lines) > 1:
                val = lines[-1].split(',')[-1].replace('"', '')
                return float(val)
        except:
            pass
            
        # Fallback to wmic (Locale independent usually)
        # wmic cpu get loadpercentage
        try:
            cmd = ['wmic', 'cpu', 'get', 'loadpercentage']
            output = subprocess.check_output(cmd, creationflags=subprocess.CREATE_NO_WINDOW).decode()
            # Output:
            # LoadPercentage
            # 12
            lines = [l.strip() for l in output.split('\n') if l.strip()]
            if len(lines) > 1 and lines[1].isdigit():
                return float(lines[1])
        except:
            pass
            
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
            cmd = ['powershell', '-Command', ps_script]
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
