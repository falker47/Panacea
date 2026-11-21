"""Fixed Windows cache categories. A consent snapshot names specific file identities."""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import threading
import time

from modules.cleanup import (CleanupManager, UnsafePath, _guard_path, _lexical_path,
                             guarded_stamp, known_folder, remove_guarded_empty_folder)
from modules.commands import system_executable

CATEGORIES = ("wer_reports", "thumbnail_cache", "shader_cache", "delivery_optimization",
              "crash_dumps", "panacea_leftovers")
DEFAULT_CATEGORIES = frozenset(CATEGORIES) - {"crash_dumps"}
DELIVERY_COMMAND = "powershell.exe -NoProfile -NonInteractive -Command Delete-DeliveryOptimizationCache -Force"
_DELIVERY_READ = (
    "$ErrorActionPreference='Stop'; "
    r"$m=Import-Module ($PSHOME + '\Modules\DeliveryOptimization\DeliveryOptimization.psd1') -PassThru; "
    "if (!$m.ExportedCommands.ContainsKey('Delete-DeliveryOptimizationCache')) {exit 3}; "
    r"DeliveryOptimization\Get-DeliveryOptimizationPerfSnap | Select-Object Files,CacheSizeBytes | ConvertTo-Json -Compress"
)


def delivery_preview():
    """Windows owns this cache. Never traverse its private directory or guess its size."""
    if os.name != "nt":
        return None
    try:
        result = subprocess.run([system_executable("powershell.exe"), "-NoProfile", "-NonInteractive",
                                 "-Command", _DELIVERY_READ], stdin=subprocess.DEVNULL, capture_output=True,
                                timeout=12, shell=False, creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            count, size = data["Files"], data["CacheSizeBytes"]
            if all(type(x) is int and x >= 0 for x in (count, size)):
                return count, size
    except (OSError, ValueError, TypeError, KeyError, subprocess.TimeoutExpired):
        pass
    return None


def _folder(name):
    if name == "windows":
        root = CleanupManager._windows_root()
    elif name == "temp":
        root = os.environ.get("TEMP")
    else:
        return known_folder(name)
    if not root or not os.path.isabs(root):
        raise OSError("Windows folder unavailable")
    return Path(_lexical_path(root))


def category_ids(target):
    if not isinstance(target, str) or len(target) > 128:
        raise ValueError("Select at least one cleanup category")
    values = target.split(",")
    if len(values) != len(set(values)) or any(value not in CATEGORIES for value in values):
        raise ValueError("Unknown or duplicate cleanup category")
    return tuple(key for key in CATEGORIES if key in values)


@dataclass
class Inventory:
    category: str
    files: dict = field(default_factory=dict)
    folders: dict = field(default_factory=dict)
    roots: dict = field(default_factory=dict)
    skipped: int = 0
    available: bool = True
    managed: tuple | None = None

    def row(self):
        count, size = self.managed or (len(self.files), sum(v[-1] for v in self.files.values()))
        return {"id": self.category, "available": self.available,
                "default_selected": self.available and self.category in DEFAULT_CATEGORIES,
                "count": count if self.available else None, "bytes": size if self.available else None,
                "samples": [str(p) for p in sorted(self.files)[:5]], "skipped": self.skipped}


@dataclass(frozen=True)
class CleanupTarget:
    categories: tuple
    inventory: tuple

    @property
    def label(self):
        return ", ".join(self.categories)

    def changed_result(self, current):
        available = {item.category: item.available for item in current.inventory} if current else {}
        steps = []
        for key in self.categories:
            status = "unavailable" if available.get(key) is False else "stale"
            steps.append({"id": key, "name": key, "status": status, "success": False, "message": status})
        return {"status": "unavailable" if all(row["status"] == "unavailable" for row in steps) else "stale",
                "success": False, "steps": steps, "total": len(steps),
                "message": "The cleanup preview changed. Refresh and confirm again."}


class DeepCleanup:
    def __init__(self, *, folder=_folder, delivery=delivery_preview, clock=time.time):
        self.folder, self.delivery, self.clock = folder, delivery, clock
        self._lock = threading.Lock()
        self._preview = {}

    def _roots(self, category):
        # Patterns apply only to immediate files. None means the complete subtree.
        if category == "wer_reports":
            for key in ("program_data", "local"):
                for name in ("ReportArchive", "ReportQueue"):
                    yield key, Path("Microsoft", "Windows", "WER", name), None
        elif category == "thumbnail_cache":
            yield "local", Path("Microsoft", "Windows", "Explorer"), r"(?:thumbcache_|iconcache_).*\.db"
        elif category == "shader_cache":
            yield "local", "D3DSCache", None
        elif category == "crash_dumps":
            yield "windows", "Minidump", r".*\.dmp"
            yield "windows", "", r"MEMORY\.DMP"
            yield "local", "CrashDumps", r".*\.dmp"
        elif category == "panacea_leftovers":
            yield "temp", "", "staging"

    def _scan_root(self, inventory, root, pattern):
        pending = [(root, pattern)]
        while pending:
            directory, rule = pending.pop()
            try:
                with _guard_path(directory), os.scandir(directory) as entries:
                    if directory == root:
                        inventory.roots[root] = guarded_stamp(root, directory=True)[:5]
                    if rule == "staging" and directory == Path(sys.executable).parent:
                        inventory.available = False
                        return
                    for entry in entries:
                        path = directory / entry.name
                        if rule == "staging":
                            if not re.fullmatch(r"Panacea-Qt-update-[\w-]+", entry.name, re.I):
                                continue
                        elif rule and not re.fullmatch(rule, entry.name, re.I):
                            continue
                        try:
                            info = entry.stat(follow_symlinks=False)
                            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                                raise UnsafePath("Reparse point")
                            if rule == "staging":
                                if (stat.S_ISDIR(info.st_mode) and self.clock() - info.st_mtime > 86400
                                        and not Path(sys.executable).is_relative_to(path)):
                                    inventory.folders[path] = guarded_stamp(path, directory=True)
                                    # tempfile.mkstemp in modules.updater uses eight random characters.
                                    pending.append((path, r"Panacea-[a-z0-9_]{8}\.(?:exe|part)"))
                            elif stat.S_ISREG(info.st_mode):
                                inventory.files[path] = guarded_stamp(path)
                            elif stat.S_ISDIR(info.st_mode) and rule is None:
                                pending.append((path, None))
                        except OSError:
                            inventory.skipped += 1
            except FileNotFoundError:
                continue  # A cache which Windows has not created is empty.
            except OSError:
                inventory.skipped += 1

    def _inspect(self, category):
        inventory = Inventory(category)
        if category == "delivery_optimization":
            inventory.managed = self.delivery()
            inventory.available = inventory.managed is not None
        else:
            inventory.available = False
            for folder, relative, pattern in self._roots(category):
                try:
                    root = self.folder(folder) / relative
                except OSError:
                    inventory.skipped += 1
                    continue
                inventory.available = True
                self._scan_root(inventory, root, pattern)
        return inventory

    def preview(self, *, remember=True):
        snapshots = {key: self._inspect(key) for key in CATEGORIES}
        if remember:
            with self._lock:
                self._preview = snapshots
        return {"categories": [x.row() for x in snapshots.values()]}

    def target(self, action, raw, *, fresh=False):
        ids = category_ids(raw)
        with self._lock:
            stored = {} if fresh else self._preview.copy()
        return CleanupTarget(ids, tuple(stored[key] if key in stored else self._inspect(key) for key in ids))

    def _clean_files(self, inventory, cancelled):
        count = size = 0
        skipped = inventory.skipped
        for path, stamp in inventory.files.items():
            if cancelled():
                break
            try:
                with _guard_path(path.parent):
                    size += CleanupManager._delete_file(path, False, expected=stamp)
                count += 1
            except OSError:
                skipped += 1
        for path, stamp in inventory.folders.items():
            if cancelled():
                break
            try:
                remove_guarded_empty_folder(path, stamp)
            except OSError:
                skipped += 1
        status = "cancelled" if cancelled() else "partial" if skipped else "completed"
        return {"status": status, "count": count, "bytes": size, "skipped": skipped}

    def apply(self, target, runner, log, cancelled):
        rows = []
        for inventory in target.inventory:
            if cancelled():
                break
            key = inventory.category
            if not inventory.available:
                row = {"status": "unavailable"}
            elif key == "delivery_optimization":
                ok = runner.run_command_stream(DELIVERY_COMMAND, "Delivery Optimization", log)
                status = "completed" if ok else "failed"
                if runner.completion_unknown:
                    status = "unknown"
                elif not ok and self.delivery() is None:
                    status = "unavailable"
                row = {"status": status, "count": None, "bytes": None}
            else:
                row = self._clean_files(inventory, cancelled)
            rows.append(dict(row, id=key, name=key, success=row["status"] == "completed",
                             message=row["status"]))
            if row["status"] == "unknown":
                break
        with self._lock:
            self._preview.clear()
        statuses = {row["status"] for row in rows}
        examined = len(rows)
        status = ("unknown" if "unknown" in statuses else "cancelled" if cancelled()
                  else next(iter(statuses)) if len(statuses) == 1 else "partial")
        for key in target.categories[len(rows):]:
            rows.append({"id": key, "name": key, "status": "not_run", "success": False, "message": "not_run"})
        return {"status": status, "success": status == "completed", "steps": rows,
                "total": len(target.categories), "message": f"{examined}/{len(target.categories)} categories · {status}"}


@lru_cache(maxsize=1)
def session_cleanup():
    """The viewer and the confirmation gateway share the last explicit preview."""
    return DeepCleanup()
