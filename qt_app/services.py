"""Narrow, read-only contract between Qt Quick and existing Panacea backends.

Side-effecting actions are *not* exposed by this gateway. The eventual Qt
maintenance controller must reuse existing confirmation, privilege, completion
guard, cancellation and update-integrity contracts, under separate tests.
"""
from __future__ import annotations

import threading


READ_ACTIONS = frozenset({
    "hardware", "temp_preview", "drives", "turbo_status", "guard_status"
})


def _default_factory(name):
    if name == "monitor":
        from modules.system_monitor import SystemMonitor
        return SystemMonitor()
    if name == "cleanup":
        from modules.cleanup import CleanupManager
        return CleanupManager()
    if name == "disk":
        from modules.disk import DiskOptimizer
        return DiskOptimizer()
    if name == "performance":
        from modules.performance import PerformanceManager
        return PerformanceManager()
    if name == "guard":
        from modules.maintenance_guard import MaintenanceGuard
        return MaintenanceGuard()
    raise ValueError("Unknown backend manager")


def _read_state(fn, *, invert=False):
    try:
        value = fn()
        if value is None:
            return None
        return bool(not value if invert else value)
    except (Exception,):
        return None


class ReadService:
    """Single-worker read facade; it intentionally cannot execute maintenance."""

    def __init__(self, *, factories=None):
        self._factories = dict(factories or {})
        self._instances = {}
        self._lock = threading.Lock()
        self._closed = False

    def _manager(self, name):
        if self._closed:
            raise RuntimeError("Qt read service has been closed")
        if name not in self._instances:
            factory = self._factories.get(name)
            self._instances[name] = (factory() if factory else _default_factory(name))
        return self._instances[name]

    def collect(self, action):
        """Return JSON-compatible data; reject any unrecognized/unsafe command."""
        if action not in READ_ACTIONS:
            raise ValueError("Unknown or side-effecting action is not permitted")
        with self._lock:
            if self._closed:
                raise RuntimeError("Qt read service has been closed")
            return self._collect_locked(action)

    def _collect_locked(self, action):
        if action == "hardware":
            metadata = self._manager("monitor").sample_metadata()
            return {
                "os": str(metadata.get("os") or "Non disponibile"),
                "cpu_name": str(metadata.get("cpu_name") or "Non disponibile"),
                "ram_info": str(metadata.get("ram_info") or "Non disponibile"),
                "disk_model": str(metadata.get("disk_model") or "Non disponibile"),
            }
        if action == "temp_preview":
            manager = self._manager("cleanup")
            count, size = manager.preview_temp_files()
            result = manager.last_result
            return {
                "count": int(count), "bytes": int(size),
                "skipped": len(getattr(result, "skipped", ())),
                "errors": len(getattr(result, "errors", ())),
                "no_files_deleted": True,
            }
        if action == "drives":
            rows = self._manager("disk").get_drive_info()
            return {"drives": [{
                "letter": str(row.get("letter") or ""),
                "available": row.get("available") is True,
                "total_bytes": row.get("total_bytes"),
                "free_bytes": row.get("free_bytes"),
                "used_percent": row.get("used_percent"),
                "error": str(row.get("error") or ""),
            } for row in rows]}
        if action == "turbo_status":
            manager = self._manager("performance")
            try:
                power = manager.get_power_plan()
                power = None if power is None else power == "high"
            except Exception:
                power = None
            return {
                "states": {
                    "power": power,
                    "visual": _read_state(manager.get_visual_effects, invert=True),
                    "sysmain": _read_state(manager.get_sysmain_status, invert=True),
                    "wsearch": _read_state(manager.get_wsearch_status, invert=True),
                    "spooler": _read_state(manager.get_spooler_status, invert=True),
                },
                "master": _read_state(manager.is_turbo_active),
            }
        if action == "guard_status":
            guard = self._manager("guard")
            blocked = guard.is_blocked()
            return {
                "blocked": blocked is True,
                "message": str(guard.last_error if blocked else "Nessun blocco manutenzione rilevato"),
            }
        raise AssertionError("Allowlist dispatch contract is incomplete")

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            monitor = self._instances.get("monitor")
            if monitor is not None:
                monitor.close()
