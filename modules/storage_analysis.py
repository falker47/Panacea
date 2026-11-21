"""Bounded, metadata-only disk inventory. File and folder rankings use logical bytes."""
from __future__ import annotations

from collections import Counter
from contextlib import contextmanager, ExitStack
import ctypes
import heapq
import os
from pathlib import Path
import stat
import subprocess
import threading
import time

from modules.cleanup import _guard_path, known_folder
from modules.commands import system_executable, validate_drive
from modules.disk import DiskOptimizer

LARGE_FILE = 100_000_000
MAX_ENTRIES = 100_000
MAX_SECONDS = 15


def _is_link(info):
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)


@contextmanager
def _entries(path):
    if os.name == "nt":
        # Keep each ancestor pinned while reading the directory and its entries.
        with _guard_path(path), os.scandir(path) as entries:
            yield entries
    else:
        with ExitStack() as stack:
            fd = None
            for part in path.parts:
                fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                stack.callback(os.close, fd)
            yield stack.enter_context(os.scandir(fd))


def _root(selection):
    if selection == "profile":
        profile = known_folder("profile")
        if ctypes.windll.kernel32.GetDriveTypeW(profile.anchor) != 3:
            raise ValueError("The user profile is not on a local fixed drive")
        return profile
    drive = validate_drive(selection)
    # This read never initializes the file logger used for disk maintenance.
    if drive not in DiskOptimizer(logger=False).get_drives():
        raise ValueError("Select an available fixed drive")
    return Path(drive + "\\")


class StorageAnalysis:
    def __init__(self, *, root=_root, clock=time.monotonic, max_entries=MAX_ENTRIES, seconds=MAX_SECONDS):
        self._root, self._clock = root, clock
        self.max_entries, self.seconds = max_entries, seconds
        self._cache = {}
        self._lock = threading.Lock()

    def scan(self, selection="profile", *, cancel=None, progress=None, refresh=False):
        cancel = cancel if cancel is not None else threading.Event()
        start = self._clock()
        root = self._root(selection)
        with self._lock:
            cached = self._cache.get(selection)
            if cached and not refresh and cached["root"] == str(root) and not cancel.is_set():
                return dict(cached, cached=True)
            self._cache.pop(selection, None)
        sizes, large = Counter(), []
        pending = [(root, ())]
        visited = skipped = links = 0
        status = "completed"

        def limit():
            if cancel.is_set():
                return "cancelled"
            if visited >= self.max_entries:
                return "entry_limit"
            if self._clock() - start >= self.seconds:
                return "time_limit"
            return ""

        while pending and not (status := limit()):
            directory, groups = pending.pop()
            try:
                with _entries(directory) as entries:
                    for entry in entries:
                        if (status := limit()):
                            break
                        visited += 1
                        if progress and (visited == 1 or visited % 128 == 0):
                            progress(visited)
                        try:
                            info = entry.stat(follow_symlinks=False)
                        except OSError:
                            skipped += 1
                            continue
                        path = directory / entry.name
                        if _is_link(info):
                            links += 1
                        elif stat.S_ISDIR(info.st_mode):
                            child_groups = groups
                            if len(groups) < 3:
                                sizes[str(path)] += 0
                                child_groups = (*groups, str(path))
                            pending.append((path, child_groups))
                        elif stat.S_ISREG(info.st_mode):
                            for group in groups:
                                sizes[group] += info.st_size
                            if info.st_size >= LARGE_FILE:
                                heapq.heappush(large, (info.st_size, str(path)))
                                if len(large) > 50:
                                    heapq.heappop(large)
            except OSError:
                skipped += 1
                if directory == root:
                    status = "unavailable"
            if status:
                break
        status = status or ("partial" if skipped else "completed")
        if progress:
            progress(visited)
        result = {"selection": selection, "root": str(root), "status": status, "entries": visited,
                  "skipped": skipped, "reparse_points": links, "cached": False,
                  "folders": [{"path": path, "bytes": size} for path, size in
                              heapq.nsmallest(20, sizes.items(), key=lambda pair: (-pair[1], pair[0]))],
                  "files": [{"path": path, "bytes": size} for size, path in sorted(large, reverse=True)]}
        if status not in ("cancelled", "unavailable"):
            with self._lock:
                self._cache[selection] = result
        return result

    def open_in_explorer(self, selection, path):
        with self._lock:
            cached = self._cache.get(selection)
        if not cached or not any(item["path"] == path for item in cached["folders"] + cached["files"]):
            raise ValueError("Select an item from the current scan")
        item = Path(path)
        root = self._root(selection)
        if str(root) != cached["root"] or not item.is_relative_to(root):
            raise ValueError("Storage location changed")
        with _guard_path(item.parent):
            if _is_link(item.lstat()):
                raise ValueError("Selected item changed")
            # Explorer is in the Windows directory, one level above System32.
            explorer = Path(system_executable("explorer.exe")).parent.parent / "explorer.exe"
            subprocess.Popen([str(explorer), "/select,", str(item)], shell=False)
