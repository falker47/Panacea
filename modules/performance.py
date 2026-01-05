import subprocess
from modules.logger import Logger

class PerformanceManager:
    def __init__(self):
        self.logger = Logger()
        
        # Power Plan GUIDs
        self.POWER_HIGH_PERF = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
        self.POWER_BALANCED = "381b4222-f694-41f0-9685-ff5bb260df2e"
        
    def _run_cmd(self, cmd, hide=True):
        """Run command silently"""
        try:
            flags = subprocess.CREATE_NO_WINDOW if hide else 0
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, creationflags=flags)
            return result.returncode == 0, result.stdout + result.stderr
        except Exception as e:
            return False, str(e)

    # --- Power Plan ---
    def get_power_plan(self):
        """Returns 'high' or 'balanced' or 'other'"""
        success, output = self._run_cmd("powercfg /getactivescheme")
        if self.POWER_HIGH_PERF in output:
            return "high"
        elif self.POWER_BALANCED in output:
            return "balanced"
        return "other"
    
    def set_power_plan(self, high_performance=True):
        guid = self.POWER_HIGH_PERF if high_performance else self.POWER_BALANCED
        return self._run_cmd(f"powercfg /setactive {guid}")

    # --- Services ---
    def get_service_status(self, service_name):
        """Returns True if running, False if stopped"""
        success, output = self._run_cmd(f"sc query {service_name}")
        return "RUNNING" in output
    
    def set_service(self, service_name, start=True):
        action = "start" if start else "stop"
        return self._run_cmd(f"sc {action} {service_name}")

    # --- Visual Effects ---
    def get_visual_effects(self):
        """Returns True if 'best appearance' (default), False if 'best performance'"""
        # Check registry: HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects
        # VisualFXSetting: 0=Custom, 1=Best Appearance, 2=Best Performance
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                                  r"Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects")
            value, _ = winreg.QueryValueEx(key, "VisualFXSetting")
            winreg.CloseKey(key)
            return value != 2  # True if NOT best performance
        except:
            return True  # Assume default (appearance)
    
    def set_visual_effects(self, enable_effects=True):
        """Set visual effects: True=Best Appearance, False=Best Performance"""
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                                  r"Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects",
                                  0, winreg.KEY_SET_VALUE)
            value = 1 if enable_effects else 2
            winreg.SetValueEx(key, "VisualFXSetting", 0, winreg.REG_DWORD, value)
            winreg.CloseKey(key)
            self.logger.log(f"Visual effects set to {'appearance' if enable_effects else 'performance'}")
            return True, "OK"
        except Exception as e:
            return False, str(e)

    # --- Convenience methods for specific services ---
    def get_sysmain_status(self):
        return self.get_service_status("SysMain")
    
    def set_sysmain(self, enable=True):
        return self.set_service("SysMain", start=enable)
    
    def get_wsearch_status(self):
        return self.get_service_status("WSearch")
    
    def set_wsearch(self, enable=True):
        return self.set_service("WSearch", start=enable)
    
    def get_spooler_status(self):
        return self.get_service_status("Spooler")
    
    def set_spooler(self, enable=True):
        return self.set_service("Spooler", start=enable)
