"""Durable, bounded maintenance history. Persist only typed operation metadata."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
import re
import threading
from uuid import uuid4

from modules import logger
from version import VERSION


MAX_ENTRIES = 2000
MAX_PAGE = 100
MAX_LINE = 1024
STATUSES = {"completed", "partial", "failed", "unknown", "cancelled", "confirmed"}
ERRORS = {"permission_denied", "storage_unavailable", "timed_out", "operation_failed",
          "guard_blocked", "completion_unknown", "cancelled", "partial", "interrupted"}
_lock = threading.RLock()


def timestamp(seconds=None):
    moment = datetime.now(timezone.utc) if seconds is None else datetime.fromtimestamp(seconds, timezone.utc)
    return moment.isoformat(timespec="milliseconds")


def safe_time(value):
    if isinstance(value, str) and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?(?:Z|\+00:00)", value):
        return value
    return None


def action_id(value):
    from qt_app.maintenance import ACTIONS
    if isinstance(value, str) and (value in ACTIONS or value in {"archive_guard", "verify_guard"}):
        return value
    return None


def _record(data):
    if not isinstance(data, dict):
        raise ValueError("History entry must be an object")
    action = action_id(data.get("action"))
    if (not action or not re.fullmatch(r"[0-9a-f]{32}", str(data.get("id", "")))
            or data.get("status") not in STATUSES or type(data.get("success")) is not bool
            or not all(safe_time(data.get(key)) for key in ("started", "finished"))
            or not re.fullmatch(r"\d{1,4}\.\d{1,4}\.\d{1,4}", str(data.get("app_version", "")))):
        raise ValueError("Unrecognized history entry")
    row = {key: data[key] for key in ("id", "action", "started", "finished", "status", "success", "app_version")}
    row["restart_required"] = data.get("restart_required") is True
    row["error_code"] = data.get("error_code") if data.get("error_code") in ERRORS else None
    for key in ("count", "bytes", "skipped", "errors", "total"):
        value = data.get(key)
        if type(value) is int and 0 <= value <= 2**63 - 1:
            row[key] = value
    return row


def operation_record(action, started, result=None, error=None, *, unverified=False):
    result = result if isinstance(result, dict) and error is None else {}
    status = "unknown" if unverified else result.get("status", "failed")
    code = result.get("error_code")
    if error is not None:
        if isinstance(error, PermissionError):
            code = "permission_denied"
        elif isinstance(error, TimeoutError):
            code = "timed_out"
        elif isinstance(error, OSError):
            code = "storage_unavailable"
        elif isinstance(error, RuntimeError) and "block" in str(error).lower():
            code = "guard_blocked"
        else:
            code = "operation_failed"
    elif code not in ERRORS:
        code = {"failed": "operation_failed", "partial": "partial", "cancelled": "cancelled",
                "unknown": "completion_unknown"}.get(status)
    messages = [result, *result.get("steps", [])]
    restart = (status == "unknown" or result.get("restart_required") is True
               or any(str(step.get("message", "")).startswith("Restart required.") for step in messages))
    return _record({**result, "id": uuid4().hex, "action": action, "started": timestamp(started),
                    "finished": timestamp(), "status": status, "success": result.get("success") is True,
                    "restart_required": restart, "error_code": code, "app_version": VERSION})


@contextmanager
def _file_lock(root, writing):
    """A stable lock inode spans active-file rotation. Readers create no files."""
    if os.name == "nt":
        # The named mutex also covers first creation of this user's directory.
        yield
        return
    with _lock:
        try:
            stream = logger.open_regular(root / "history.lock", "a+b" if writing else "rb")
        except FileNotFoundError:
            if writing:
                raise
            yield
            return
        with stream:
            stream.seek(0)
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX if writing else fcntl.LOCK_SH)
            try:
                yield
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)


def _lines(path):
    try:
        stream = logger.open_regular(path, "rb")
    except FileNotFoundError:
        return
    with stream:
        # A damaged or foreign file cannot make a page read unbounded.
        size = os.fstat(stream.fileno()).st_size
        if size > MAX_LINE * (MAX_ENTRIES + 1):
            stream.seek(size - MAX_LINE * MAX_ENTRIES)
            yield b""
        while line := stream.readline(MAX_LINE + 1):
            if len(line) > MAX_LINE:
                while not line.endswith(b"\n") and (line := stream.readline(8192)):
                    pass
                yield b""
            else:
                yield line


def append(row):
    payload = json.dumps(_record(row), separators=(",", ":")).encode("ascii") + b"\n"
    root = logger.data_directory()
    with logger.storage_lock(root), logger.directory(root, create=True), _file_lock(root, True):
        path = root / "history.jsonl"
        if sum(1 for _ in _lines(path)) >= MAX_ENTRIES:
            logger.replace_sibling(path, "history.1.jsonl")
        with logger.open_regular(path, "a+b", buffering=0) as stream:
            if stream.seek(0, os.SEEK_END):
                stream.seek(-1, os.SEEK_END)
                if stream.read(1) != b"\n":
                    payload = b"\n" + payload
            if stream.write(payload) != len(payload):
                raise OSError("Incomplete history append")
            os.fsync(stream.fileno())


def page(offset=0, limit=25, status=""):
    offset = max(0, int(offset))
    limit = max(1, min(MAX_PAGE, int(limit)))
    rows = []
    corrupt = 0
    unavailable = False
    try:
        root = logger.data_directory()
        with logger.storage_lock(root), logger.directory(root), _file_lock(root, False):
            for name in ("history.1.jsonl", "history.jsonl"):
                for line in _lines(root / name):
                    try:
                        row = _record(json.loads(line))
                    except (ValueError, TypeError, RecursionError):
                        corrupt += 1
                        continue
                    if not status or row["status"] == status:
                        rows.append(row)
    except FileNotFoundError:
        pass
    except OSError:
        unavailable = True
    rows.reverse()
    return {"items": rows[offset:offset + limit], "total": len(rows), "corrupt": corrupt,
            "has_more": offset + limit < len(rows), "unavailable": unavailable}
