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
            percent = stat.dwMemoryLoad
            
            return round(total_gb, 1), round(avail_gb, 1), percent
        except:
            return 0, 0, 0

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

    def get_cpu_info(self):
        """Returns CPU name"""
        try:
            return platform.processor()
        except:
            return "Unknown CPU"
            
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
