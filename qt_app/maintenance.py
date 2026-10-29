"""Qt Quick maintenance gateway. No raw command or path is accepted from QML.

An action must be prepared and explicitly confirmed; its nonce is consumed once.
All Windows mutations reuse the validated V2 backend, not new shell commands.
"""
from __future__ import annotations

import ctypes
import ntpath
import os
from pathlib import Path
import secrets
import subprocess
import threading

from modules.commands import system_executable, validate_drive
from modules.operations import OperationStep, run_sequence
from modules.quick_cleanup import run_quick_cleanup


COMMANDS = {
    "sfc": ("sfc /scannow", "System file scan"),
    "dism_check": ("DISM /Online /Cleanup-Image /CheckHealth", "Windows image check"),
    "dism_restore": ("DISM /Online /Cleanup-Image /RestoreHealth", "Windows image restore"),
    "component_cleanup": ("DISM /Online /Cleanup-Image /StartComponentCleanup", "Component store cleanup"),
    "dns_flush": ("ipconfig /flushdns", "DNS cache flush"),
    "winsock_reset": ("netsh winsock reset", "Winsock reset"),
}
SETTINGS = {
    "apps_settings": "ms-settings:appsfeatures",
    "startup_settings": "ms-settings:startupapps",
    "windows_update": "ms-settings:windowsupdate",
    "windows_optional": "ms-settings:windowsupdate-optionalupdates",
}
TURBO = {
    "turbo_on": ("set_turbo", True), "turbo_off": ("set_turbo", False),
    "power_on": ("set_power_plan", True), "power_off": ("set_power_plan", False),
    "visual_on": ("set_visual_effects", False), "visual_off": ("set_visual_effects", True),
    "sysmain_on": ("set_sysmain", False), "sysmain_off": ("set_sysmain", True),
    "wsearch_on": ("set_wsearch", False), "wsearch_off": ("set_wsearch", True),
    "spooler_on": ("set_spooler", False), "spooler_off": ("set_spooler", True),
}
CLEANUPS = frozenset({"temp_clean", "browser_clean", "recycle_empty", "quick_cleanup"})
DRIVE_ACTIONS = frozenset({"drive_optimize", "chkdsk"})
OPEN_ACTIONS = frozenset({*SETTINGS, "appwiz", "open_cleanmgr", "open_defrag"})
ACTIONS = frozenset({
    *COMMANDS, *SETTINGS, *TURBO, *CLEANUPS, *DRIVE_ACTIONS, "appwiz",
    "open_cleanmgr", "open_defrag", "restore_point", "resurrection",
    "battery_report",
})
DANGEROUS = frozenset({*CLEANUPS, "resurrection", "winsock_reset", "component_cleanup"})
WARNINGS = {
    "temp_clean": "Permanently delete eligible temporary files. Locked/protected files are skipped. This cannot be undone.",
    "browser_clean": "Permanently delete eligible browser caches. Close browsers first; this cannot be undone.",
    "recycle_empty": "Permanently empty the entire Recycle Bin. This cannot be undone.",
    "quick_cleanup": "Delete temp files, empty the entire Recycle Bin, run component-store DISM; then open Windows Disk Cleanup for manual choices. Deletion is irreversible.",
    "resurrection": "Ten maintenance steps: verified restore point first; then irreversible cache, temp and Recycle Bin deletion, network reset and Windows checks. Save work. Cancellation only between steps.",
    "winsock_reset": "Network connections may be interrupted and Windows may require a restart.",
    "component_cleanup": "Remove superseded Windows components with DISM. This may require a restart.",
}


def _default_factory(name):
    if name == "guard":
        from modules.maintenance_guard import MaintenanceGuard
        return MaintenanceGuard()
    modules = {
        "commands": ("modules.commands", "CommandRunner"),
        "cleanup": ("modules.cleanup", "CleanupManager"),
        "disk": ("modules.disk", "DiskOptimizer"),
        "restore": ("modules.restore", "RestoreManager"),
        "performance": ("modules.performance", "PerformanceManager"),
    }
    from importlib import import_module
    module_name, class_name = modules[name]
    return getattr(import_module(module_name), class_name)()


def _admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def _strict_pair(value):
    if isinstance(value, tuple) and len(value) == 2 and type(value[0]) is bool:
        return value
    return False, "Backend returned an unverified result"


class MaintenanceService:
    """Serial, explicit-confirmation gateway; safe to test without Windows."""

    def __init__(self, *, factories=None, is_admin=None, platform=None):
        self._factories = dict(factories or {})
        self._instances = {}
        self._is_admin = is_admin or _admin
        self._platform = os.name if platform is None else platform
        self._lock = threading.Lock()
        self._active = False
        self._pending = None
        self._closed = False
        self._cancel = threading.Event()

    def _manager(self, name):
        if name not in self._instances:
            factory = self._factories.get(name)
            self._instances[name] = factory() if factory else _default_factory(name)
        return self._instances[name]

    def prepare(self, action, drive=""):
        """No mutation: return a one-use nonce and an informed confirmation."""
        if not isinstance(action, str) or action not in ACTIONS:
            raise ValueError("Action is not in the approved maintenance allowlist")
        if action in DRIVE_ACTIONS:
            drive = validate_drive(drive)
        elif drive:
            raise ValueError("Drive argument is accepted only by disk operations")
        with self._lock:
            if self._closed or self._active:
                raise RuntimeError("Maintenance is already running or closing")
            nonce = secrets.token_urlsafe(24)
            self._pending = (nonce, action, drive)
        warning = WARNINGS.get(action, "This changes Windows settings. Save work; the operation may take time or require a restart.")
        if action in OPEN_ACTIONS:
            warning = "Open a native Windows utility. Changes there require separate Windows interaction."
        if action in TURBO:
            warning = "Change Windows power, visual or service state. Original values are saved and restoration may fail if Windows policies intervene."
        return {"nonce": nonce, "title": action.replace("_", " ").title(),
                "details": warning + (f"\nSelected drive: {drive}" if drive else "")}

    def reject(self):
        with self._lock:
            self._pending = None

    def cancel(self):
        """Cooperative: never assume a running Windows command has terminated."""
        self._cancel.set()

    def close(self):
        with self._lock:
            self._closed = True
            self._pending = None
        self._cancel.set()

    def _completion_unknown(self):
        return any(getattr(self._instances.get(name), "completion_unknown", False) is True
                   for name in ("commands", "disk"))

    def _validate_fixed_drive(self, drive):
        drive = validate_drive(drive)
        rows = self._manager("disk").get_drive_info()
        if not any(row.get("letter", "").upper() == drive.upper() and row.get("available") is True
                   for row in rows):
            raise ValueError("Selected drive is not an available fixed drive")
        return drive

    def _cleanup_result(self, action, *, log):
        cleanup = self._manager("cleanup")
        if action == "temp_clean":
            count, size = cleanup.clean_temp_files(progress_callback=log)
        elif action == "browser_clean":
            count, size = cleanup.clean_browser_caches()
        else:
            raise ValueError("Unsupported cleanup action")
        result = cleanup.last_result
        if result is None or getattr(result, "preview", True) or type(count) is not int or type(size) is not int or count < 0 or size < 0:
            return {"status": "failed", "success": False, "message": "Cleanup result could not be verified"}
        skipped, errors = len(getattr(result, "skipped", ())), len(getattr(result, "errors", ()))
        status = "failed" if errors and not count else "partial" if skipped or errors else "completed"
        return {"status": status, "success": status == "completed",
                "message": f"{count} files; {size} logical bytes; {skipped} skipped; {errors} errors",
                "count": count, "bytes": size, "skipped": skipped, "errors": errors}

    def _command(self, action, log):
        cmd, description = COMMANDS[action]
        runner = self._manager("commands")
        success = runner.run_command_stream(cmd, description, log) is True
        return success, ("Restart required. See command output." if runner.restart_required and success
                         else "See command output for details.")

    def _resurrection(self, log, progress):
        restore = self._manager("restore")
        cleanup = self._manager("cleanup")
        disk = self._manager("disk")
        runner = self._manager("commands")
        system_drive = validate_drive(ntpath.splitdrive(system_executable("cmd.exe"))[0])

        def cleanup_step(action):
            result = self._cleanup_result(action, log=log)
            return result["success"], result["message"]

        def command_step(command, description):
            ok = runner.run_command_stream(command, description, log) is True
            return ok, "Restart required." if runner.restart_required and ok else "See command output."

        steps = [
            OperationStep("Restore point", lambda: restore.create_restore_point("Panacea Resurrection restore point"), True),
            OperationStep("Browser caches", lambda: cleanup_step("browser_clean")),
            OperationStep("Temporary files", lambda: cleanup_step("temp_clean")),
            OperationStep("Recycle Bin", cleanup.empty_recycle_bin),
            OperationStep("DNS cache", lambda: command_step("ipconfig /flushdns", "DNS flush")),
            OperationStep("Network reset", lambda: command_step("netsh winsock reset", "Network reset")),
            OperationStep("Drive optimization", lambda: (disk.analyze_optimize_drive(system_drive, progress_callback=log) is True, "See drive output.")),
            OperationStep("Disk health scan", lambda: command_step(f"chkdsk {system_drive} /scan /perf", "Disk health scan")),
            OperationStep("Windows image health", lambda: command_step("DISM /Online /Cleanup-Image /CheckHealth", "Image health")),
            OperationStep("System file scan", lambda: command_step("sfc /scannow", "System file scan")),
        ]

        def done(finished, total, result):
            log(f"{result.name}: {'completed' if result.success else 'failed'} · {result.message}")
            if progress:
                progress(finished, total, result.name)

        result = run_sequence(steps, cancel=lambda: self._cancel.is_set() or self._completion_unknown(),
                              progress=done)
        status = result.status
        if self._completion_unknown():
            status = "unknown"
        return {"status": status, "success": status == "completed",
                "message": f"{len(result.steps)}/{len(steps)} steps; {result.error or status}",
                "steps": [{"name": row.name, "success": row.success, "message": row.message}
                          for row in result.steps], "total": len(steps)}

    def _dispatch(self, action, drive, log, progress):
        if action in COMMANDS:
            return _strict_pair(self._command(action, log))
        if action == "chkdsk":
            drive = self._validate_fixed_drive(drive)
            runner = self._manager("commands")
            return _strict_pair((runner.run_command_stream(f"chkdsk {drive} /scan /perf", "Disk health scan", log) is True,
                                 "Restart required." if runner.restart_required else "See command output."))
        if action == "drive_optimize":
            drive = self._validate_fixed_drive(drive)
            disk = self._manager("disk")
            return disk.analyze_optimize_drive(drive, progress_callback=log) is True, "See drive output."
        if action in ("temp_clean", "browser_clean"):
            return self._cleanup_result(action, log=log)
        if action == "recycle_empty":
            return _strict_pair(self._manager("cleanup").empty_recycle_bin())
        if action == "quick_cleanup":
            result = run_quick_cleanup(self._manager("cleanup"), self._manager("commands"), log,
                                       cancel=self._cancel, progress=progress)
            opened = False
            if len(result.steps) == 3 and not self._cancel.is_set() and not self._completion_unknown():
                opened = self._manager("cleanup").open_disk_cleanup() is True
            status = result.status
            if not opened and status == "completed":
                status = "partial"
            return {"status": status, "success": status == "completed",
                    "message": f"{len(result.steps)}/3 steps; " + ("Windows Disk Cleanup opened; select categories manually."
                    if opened else "Windows Disk Cleanup not opened."),
                    "steps": [{"name": x.name, "success": x.success, "message": x.message}
                              for x in result.steps], "total": 3}
        if action == "resurrection":
            return self._resurrection(log, progress)
        if action in TURBO:
            name, value = TURBO[action]
            return _strict_pair(getattr(self._manager("performance"), name)(value))
        if action == "restore_point":
            return _strict_pair(self._manager("restore").create_restore_point("Panacea Manual Point"))
        if action == "open_cleanmgr":
            return self._manager("cleanup").open_disk_cleanup() is True, "Windows Disk Cleanup opened for manual choices."
        if action == "open_defrag":
            return self._manager("disk").open_optimize_gui() is True, "Windows drive optimization opened."
        if action in SETTINGS:
            os.startfile(SETTINGS[action])
            return True, "Windows Settings opened; further changes are managed in Windows."
        if action == "appwiz":
            subprocess.Popen([system_executable("control.exe"), "appwiz.cpl"], shell=False)
            return True, "Installed programs opened in Windows."
        if action == "battery_report":
            base = os.environ.get("USERPROFILE")
            if not base:
                raise RuntimeError("Windows profile folder is unavailable")
            path = Path(base) / "battery_report.html"
            subprocess.run([system_executable("powercfg.exe"), "/batteryreport", "/output", str(path)],
                           stdin=subprocess.DEVNULL, shell=False, check=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                           capture_output=True, timeout=60)
            return True, f"Battery report saved to {path}"
        raise AssertionError("Maintenance action allowlist incomplete")

    def execute(self, nonce, *, log=None, progress=None):
        """Call only in a worker after the user accepts the QML confirmation."""
        with self._lock:
            if self._pending is None or not secrets.compare_digest(str(nonce), self._pending[0]):
                raise ValueError("Missing or expired explicit confirmation")
            if self._closed or self._active:
                raise RuntimeError("Maintenance is already running or closing")
            _, action, drive = self._pending
            self._pending = None
            self._active = True
            self._cancel.clear()
        try:
            if self._platform != "nt":
                raise RuntimeError("Windows-only maintenance is unavailable on this platform")
            if action not in OPEN_ACTIONS and not self._is_admin():
                raise PermissionError("Administrator privileges are required")
            guard = self._manager("guard")
            if action not in OPEN_ACTIONS and guard.is_blocked():
                raise RuntimeError(guard.last_error or "MaintenanceGuard blocks further changes")
            value = self._dispatch(action, drive, log or (lambda msg: None), progress)
            if isinstance(value, dict) and "status" in value:
                result = value
            else:
                success, message = _strict_pair(value)
                result = {"status": "completed" if success else "failed",
                          "success": success, "message": str(message)}
            if self._completion_unknown():
                result.update(status="unknown", success=False,
                              message="Command completion unverified. Restart Windows before maintenance.")
            return result
        finally:
            if self._completion_unknown():
                # The write is attempted even if the operation raised.
                self._manager("guard").mark_unknown()
            with self._lock:
                self._active = False
