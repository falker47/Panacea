"""Build an explicit, bounded diagnostics ZIP from typed, local Panacea data."""
from datetime import datetime, timezone
from io import BytesIO
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from zipfile import ZIP_DEFLATED, ZipFile

from modules import history, logger
from modules.commands import system_executable
from modules.maintenance_guard import _RESOLUTIONS
from version import VERSION


FILES = ("system.json", "guard.json", "logs.txt", "history.jsonl", "update-readiness.json", "settings.json")
LOG_BYTES = 2 * 1024 * 1024
MAX_BYTES = 4 * 1024 * 1024
_LOG_ENTRY = re.compile(rb"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d{3}) - (INFO|WARNING|ERROR) - (.*)")
_EVENTS = {
    b"Operation history write failed.": b"history_write_failed",
    b"Qt warning:": b"qt_warning",
    b"Unhandled Python exception: main": b"main_exception",
    b"Unhandled Python exception: thread": b"thread_exception",
    b"Cleanup preview:": b"cleanup_preview",
    b"Cleanup finished:": b"cleanup_finished",
    b"Failed to launch": b"launch_failed",
    b"Failed to empty recycle bin:": b"recycle_bin_failed",
}


def _json(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True) + "\n").encode("ascii")


def _log_tail(folder):
    # Project envelope and known event types only. Free-form command output,
    # exception text, continuations, paths and credentials are private by default.
    parts = []
    remaining = LOG_BYTES
    for name in ("panacea.log", *(f"panacea.log.{i}" for i in range(1, 6))):
        if not remaining:
            break
        try:
            with logger.open_regular(folder / name, "rb") as stream:
                start = max(0, stream.seek(0, os.SEEK_END) - remaining)
                stream.seek(start)
                chunk = stream.read(remaining)
        except FileNotFoundError:
            continue
        except OSError:
            parts.append(b"log_unavailable\n")
            continue
        remaining -= len(chunk)
        lines = chunk.splitlines()
        if start:
            lines = lines[1:]
        output = bytearray()
        for line in lines:
            match = _LOG_ENTRY.match(line)
            if match:
                message = match[3]
                event = next((code for prefix, code in _EVENTS.items() if message.startswith(prefix)), b"application_event")
                output.extend(b" ".join((match[1], match[2], event)) + b"\n")
        parts.append(bytes(output))
    return b"".join(reversed(parts))[-LOG_BYTES:]


def _crash_summary(folder):
    try:
        with logger.open_regular(folder / "crash-marker.log", "rb") as stream:
            size = stream.seek(0, os.SEEK_END)
            stream.seek(max(0, size - 64 * 1024))
            lines = stream.read(64 * 1024).splitlines()
    except FileNotFoundError:
        return "none"
    except OSError:
        return "unavailable"
    for line in reversed(lines):
        if line == b"Unhandled Python exception: main":
            return "main_exception"
        if line == b"Unhandled Python exception: thread":
            return "thread_exception"
        if line.startswith((b"Fatal Python error:", b"Windows fatal exception:")):
            return "native_fault"
    return "recorded" if size else "none"


def _read_object(path):
    try:
        with logger.open_regular(path, "rb") as source:
            data = source.read(256 * 1024 + 1)
        if len(data) <= 256 * 1024:
            obj = json.loads(data)
            if isinstance(obj, dict):
                return "present", obj
        return "invalid", {}
    except FileNotFoundError:
        return "absent", {}
    except (OSError, ValueError, RecursionError):
        return "unavailable", {}


def _marker_path():
    if getattr(sys, "frozen", False) and Path(sys.executable).name.lower() == "panacea.exe":
        return Path(sys.executable).with_name("Panacea.exe.update-ready.json")
    return None


def _readiness():
    path = _marker_path()
    if path is None:
        return {"state": "not_packaged"}
    state, values = _read_object(path)
    return {"state": state, **{k: values[k] for k in ("ready", "protected") if type(values.get(k)) is bool}}


def _settings(root, language):
    state, values = _read_object(root / "settings.json")
    safe = {k: values[k] for k in ("autoCheck", "sidebarCollapsed", "reduceMotion") if type(values.get(k)) is bool}
    if values.get("languageChoice") in ("it", "en", "system"):
        safe["languageChoice"] = values["languageChoice"]
    return {"state": state, "language": language if language in ("it", "en") else None, **safe}


def export(guard_state, language):
    root = logger.data_directory()
    code = guard_state.get("code")
    code = code if isinstance(code, str) and code in _RESOLUTIONS else "unverifiable_storage"
    guard = {"code": code, "resolution": _RESOLUTIONS[code], "since": history.safe_time(guard_state.get("since")),
             "action_id": history.action_id(guard_state.get("action_id")), "blocked": guard_state.get("blocked") is True,
             "safe_to_clear": guard_state.get("safe_to_clear") is True}
    records = history.page(0, history.MAX_PAGE)
    system = {"app_version": VERSION, "last_crash": _crash_summary(root / "logs"), "windows_build": sys.getwindowsversion().build if os.name == "nt" else None,
              "history_corrupt": records["corrupt"], "history_unavailable": records["unavailable"]}
    members = {"system.json": _json(system), "guard.json": _json(guard),
               "logs.txt": _log_tail(root / "logs"), "history.jsonl": b"".join(_json(r) for r in records["items"]),
               "update-readiness.json": _json(_readiness()), "settings.json": _json(_settings(root, language))}
    if sum(map(len, members.values())) > MAX_BYTES:
        raise OSError("Diagnostic data exceeds the size cap")
    packed = BytesIO()
    with ZipFile(packed, "w", ZIP_DEFLATED) as archive:
        for name in FILES:
            archive.writestr(name, members[name])
    if packed.tell() > MAX_BYTES:
        raise OSError("Diagnostics ZIP exceeds the size cap")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    with logger.directory(logger.known_folder("downloads")) as downloads:
        target = downloads / f"Panacea-diagnostics-{stamp}.zip"
        with logger.open_regular(target, "xb") as stream:
            try:
                stream.write(packed.getbuffer())
                stream.flush()
                os.fsync(stream.fileno())
            except BaseException:
                stream.close()
                target.unlink(missing_ok=True)
                raise
    return target


def reveal(archive):
    # GetSystemDirectoryW returns Windows\System32. Explorer belongs to its
    # Windows parent. Only the output produced by this export is selectable.
    if (archive.parent != logger.known_folder("downloads")
            or not re.fullmatch(r"Panacea-diagnostics-\d{8}T\d{12}Z\.zip", archive.name)):
        raise ValueError("Unrecognized diagnostics archive")
    explorer = Path(system_executable("explorer.exe")).parent.parent / "explorer.exe"
    subprocess.Popen([str(explorer), "/select,", str(archive)], shell=False)
