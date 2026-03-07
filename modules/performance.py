import subprocess
import winreg
from modules.logger import Logger
from modules.utils import NO_WINDOW, SUBPROCESS_TIMEOUT


class PerformanceManager:
    # Power Plan GUIDs
    _POWER_HIGH_PERF = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
    _POWER_BALANCED = "381b4222-f694-41f0-9685-ff5bb260df2e"

    def __init__(self):
        self.logger = Logger()

    def _run_cmd(self, cmd: str) -> tuple[bool, str]:
        """Run a shell command silently with timeout."""
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                creationflags=NO_WINDOW, timeout=SUBPROCESS_TIMEOUT,
            )
            return result.returncode == 0, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return False, "Command timed out"
        except Exception as e:
            return False, str(e)

    # --- Power Plan ---
    def get_power_plan(self) -> str:
        """Returns 'high', 'balanced', or 'other'."""
        _, output = self._run_cmd("powercfg /getactivescheme")
        if self._POWER_HIGH_PERF in output:
            return "high"
        if self._POWER_BALANCED in output:
            return "balanced"
        return "other"

    def set_power_plan(self, high_performance: bool = True) -> tuple[bool, str]:
        guid = self._POWER_HIGH_PERF if high_performance else self._POWER_BALANCED
        return self._run_cmd(f"powercfg /setactive {guid}")

    # --- Services ---
    def get_service_status(self, service_name: str) -> bool:
        """Returns True if the service is running."""
        _, output = self._run_cmd(f"sc query {service_name}")
        return "RUNNING" in output

    def set_service(self, service_name: str, start: bool = True) -> tuple[bool, str]:
        action = "start" if start else "stop"
        return self._run_cmd(f"sc {action} {service_name}")

    # --- Visual Effects ---
    def get_visual_effects(self) -> bool:
        """Returns True if 'best appearance' (default), False if 'best performance'."""
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects",
            )
            try:
                value, _ = winreg.QueryValueEx(key, "VisualFXSetting")
            finally:
                winreg.CloseKey(key)
            return value != 2
        except OSError:
            return True  # Assume default (appearance)

    def set_visual_effects(self, enable_effects: bool = True) -> tuple[bool, str]:
        """Set visual effects: True = Best Appearance, False = Best Performance."""
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects",
                0, winreg.KEY_SET_VALUE,
            )
            try:
                value = 1 if enable_effects else 2
                winreg.SetValueEx(key, "VisualFXSetting", 0, winreg.REG_DWORD, value)
            finally:
                winreg.CloseKey(key)
            self.logger.log(
                f"Visual effects set to {'appearance' if enable_effects else 'performance'}")
            return True, "OK"
        except Exception as e:
            return False, str(e)

    # --- Convenience methods for specific services ---
    def get_sysmain_status(self) -> bool:
        return self.get_service_status("SysMain")

    def set_sysmain(self, enable: bool = True) -> tuple[bool, str]:
        return self.set_service("SysMain", start=enable)

    def get_wsearch_status(self) -> bool:
        return self.get_service_status("WSearch")

    def set_wsearch(self, enable: bool = True) -> tuple[bool, str]:
        return self.set_service("WSearch", start=enable)

    def get_spooler_status(self) -> bool:
        return self.get_service_status("Spooler")

    def set_spooler(self, enable: bool = True) -> tuple[bool, str]:
        return self.set_service("Spooler", start=enable)
