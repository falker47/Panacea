"""Keep unverified maintenance blocked across app reopens until a verified boot.

Immutable records avoid replacing a stronger unknown-boot marker during concurrent
writes. An interrupted write intentionally leaves a record that fails closed.
"""
from contextlib import contextmanager, ExitStack
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import re
from datetime import datetime, timezone
from uuid import uuid4

from modules.cleanup import _guard_path, _validate_guards, _validate_handle, _windows_handle
from modules.protected_files import relative_handle, read_bytes, write_bytes, rename_same_parent


def _boot_token(value):
    if (not isinstance(value, str) or not re.fullmatch(r'windows-boot-id:(?:0|[1-9]\d{0,9})', value)
            or int(value.split(':')[1]) > 0xffffffff):
        raise ValueError('Windows boot identity is unavailable or invalid')
    return value


def windows_boot_identity():
    """Read Windows' successful-boot counter without using a mutable wall clock.

    Microsoft documents BootId as incremented at each successful boot:
    https://learn.microsoft.com/windows-hardware/design/device-experiences/oem-hvci-enablement
    Missing/invalid data fails closed; there is no timestamp or uptime fallback.
    """
    import winreg
    path = r'SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management\PrefetchParameters'
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
        value, kind = winreg.QueryValueEx(key, 'BootId')
    if kind != winreg.REG_DWORD or type(value) is not int or not 0 <= value <= 0xffffffff:
        raise ValueError('Windows boot counter is unavailable or invalid')
    return f'windows-boot-id:{value}'


def _record_name(boot_id):
    return ('boot-' + hashlib.sha256(boot_id.encode('ascii')).hexdigest() + '.json'
            if boot_id is not None else 'unknown.json')



@contextmanager
def _maintenance_mutex(timeout_ms):
    """One machine-wide Windows lease shared by Tk and Qt maintenance gateways.

    A killed process releases the kernel mutex; the durable journal, not the
    abandoned mutex alone, decides whether another operation is safe.
    """
    with _named_mutex('Global\\PanaceaMaintenanceV2', timeout_ms):
        yield


@contextmanager
def _named_mutex(name, timeout_ms):
    if os.name != 'nt':
        raise OSError('Windows process locking is unavailable')
    if type(timeout_ms) is not int or not 0 <= timeout_ms <= 0xffffffff:
        raise ValueError('Invalid maintenance lock timeout')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateMutexW.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.ReleaseMutex.argtypes = [wintypes.HANDLE]
    kernel.ReleaseMutex.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateMutexW(None, False, name)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    acquired = False
    try:
        state = kernel.WaitForSingleObject(handle, timeout_ms)
        if state == 0x102:
            raise TimeoutError('Maintenance process lock is busy; another Panacea instance is running maintenance.')
        if state not in (0, 0x80):
            raise ctypes.WinError(ctypes.get_last_error())
        acquired = True
        yield
    finally:
        if acquired:
            kernel.ReleaseMutex(handle)
        kernel.CloseHandle(handle)


_RESOLUTIONS = {
    "clear": "none",
    "unknown_completion_same_boot": "restart_windows",
    "unknown_completion_previous_boot": "verify_again",
    "interrupted_journal": "review_archive",
    "unverifiable_storage": "review_archive",
    "busy_other_instance": "wait_for_instance",
}
_MESSAGES = {
    "clear": "",
    "unknown_completion_same_boot": "Maintenance completion is unverified. Restart Windows before running maintenance again.",
    "unknown_completion_previous_boot": "A later Windows boot is verified.",
    "interrupted_journal": "An unfinished maintenance journal was detected. Restart Windows or review recovery.",
    "unverifiable_storage": "Maintenance remains blocked because its recovery storage cannot be verified.",
    "busy_other_instance": "Another Panacea instance holds the maintenance lock.",
}


def _state(code, since=None, action_id=None, message=None):
    safe = code in ("clear", "unknown_completion_previous_boot")
    return {"code": code, "since": since, "action_id": action_id, "resolution": _RESOLUTIONS[code],
            "safe_to_clear": safe, "blocked": not safe,
            "message": _MESSAGES[code] if message is None else message}


def _modified(path):
    return datetime.fromtimestamp(path.lstat().st_mtime, timezone.utc).isoformat(timespec="milliseconds")


def _move_directory(handle, parent_handle, name):
    """Rename the opened object relative to the retained destination, without replacement."""
    from modules.protected_files import _component, _IoStatus, _native_api
    encoded = _component(name).encode("utf-16-le")

    class RenameInfo(ctypes.Structure):
        _fields_ = [("replace", wintypes.BOOLEAN), ("root", wintypes.HANDLE),
                    ("size", wintypes.ULONG), ("name", wintypes.WCHAR * (len(encoded) // 2 + 1))]

    info = RenameInfo(False, parent_handle, len(encoded))
    ctypes.memmove(ctypes.addressof(info) + RenameInfo.name.offset, encoded, len(encoded))
    native = _native_api()
    native.NtSetInformationFile.argtypes = [wintypes.HANDLE, ctypes.POINTER(_IoStatus), wintypes.LPVOID,
                                           wintypes.ULONG, ctypes.c_int]
    native.NtSetInformationFile.restype = wintypes.LONG
    result = native.NtSetInformationFile(handle, ctypes.byref(_IoStatus()), ctypes.byref(info), ctypes.sizeof(info), 10)
    if result < 0:
        raise ctypes.WinError(native.RtlNtStatusToDosError(result))


@contextmanager
def _rename_destination(path):
    # Windows reopens a rename's target directory with WRITE_DATA. Retain a
    # TRAVERSE handle sharing writes, and pin a child to keep the directory
    # nonempty so it cannot be converted to a junction during the move.
    from modules.cleanup import _kernel_api, _lexical_path
    kernel = _kernel_api()
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                   wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    handle = kernel.CreateFileW('\\\\?\\' + _lexical_path(path), 0xa0, 3, None, 3, 0x02200000, None)
    if handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        _validate_handle(kernel, handle, path)
        yield kernel, handle
    finally:
        kernel.CloseHandle(handle)


class _OperationPermit:
    """Only a normally returned and verified command may resolve its journal."""

    def __init__(self, describe):
        self.resolved = False
        self.describe = describe

    def resolve(self):
        self.resolved = True


class MaintenanceGuard:
    def __init__(self, state_path=None, boot_identity=None):
        base = os.environ.get('LOCALAPPDATA')
        self.state_path = (Path(state_path) if state_path is not None else
                           Path(base) / 'Panacea' / 'maintenance-guard' if base else None)
        self._boot_identity = boot_identity or windows_boot_identity
        self._default_path = state_path is None
        self._blocked = False
        self._unknown_boot = None
        self._action = None
        self.last_error = ''

    @contextmanager
    def _storage_directory(self, create=False):
        if self.state_path is None or not self.state_path.is_absolute():
            raise OSError('An absolute maintenance guard path is required')
        missing = []
        ancestor = self.state_path
        while not os.path.lexists(ancestor):
            if ancestor.parent == ancestor:
                raise OSError('Maintenance guard storage is unavailable')
            missing.append(ancestor)
            ancestor = ancestor.parent
        with ExitStack() as stack:
            guards = stack.enter_context(_guard_path(ancestor))
            _validate_guards(guards)
            if missing and not create:
                raise FileNotFoundError('No maintenance guard records')
            for child in reversed(missing):
                kernel, handle, _ = stack.enter_context(relative_handle(guards[-1], child.name, directory=True))
                guards.append((kernel, handle, child))
            _validate_guards(guards)
            yield guards

    def _read_records(self, guards, *, allow_completed=False):
        records = {}
        try:
            with os.scandir(self.state_path) as entries:
                for entry in entries:
                    if len(records) >= 128:
                        raise ValueError('Too many maintenance guard records to verify safely')
                    path = self.state_path / entry.name
                    with _windows_handle(path) as (kernel, handle, info):
                        if info.attributes & 0x10 or info.links != 1 or (info.size_high << 32) | info.size_low > 1024:
                            raise ValueError('Unsafe maintenance guard record')
                        data = json.loads(read_bytes(kernel, handle, 1024).decode('utf-8'))
                        _validate_handle(kernel, handle, path)
                    if (not isinstance(data, dict) or set(data) != {'version', 'boot_id'}
                            or type(data['version']) is not int or data['version'] != 1):
                        raise ValueError('Invalid maintenance guard record')
                    boot_id = data['boot_id']
                    if boot_id is not None:
                        _boot_token(boot_id)
                    if entry.name != _record_name(boot_id) and not (allow_completed and entry.name == 'completed.json'
                                                                and boot_id is not None):
                        raise ValueError('Maintenance guard identity does not match its record')
                    records[entry.name] = boot_id
            _validate_guards(guards)
            return records
        except OSError as exc:
            # A missing or replaced record is not proof of an absent guard directory.
            raise ValueError(f'Maintenance guard records cannot be verified: {exc}') from exc

    def _journal(self):
        path = self.state_path.parent / 'maintenance-journal' if self.state_path is not None else None
        return _MaintenanceJournal(path, self._boot_identity)

    def _directory_state(self, *, journal=False):
        since = None
        try:
            with self._storage_directory() as guards:
                since = _modified(self.state_path)
                records = self._read_records(guards, allow_completed=journal)
        except FileNotFoundError:
            return _state("clear")
        except Exception as exc:
            return _state("unverifiable_storage", since, message=f"Unverified maintenance storage: {exc}")
        if not records:
            return _state("interrupted_journal" if journal else "unverifiable_storage", since)
        if None in records.values():
            return _state("unverifiable_storage", since)
        current = int(_boot_token(self._boot_identity()).split(":")[1])
        pending = [int(boot.split(":")[1]) for name, boot in records.items() if name != "completed.json"]
        if current in pending:
            return _state("interrupted_journal" if journal else "unknown_completion_same_boot", since)
        if any(current < old for old in pending):
            return _state("unverifiable_storage", since, message="The Windows boot counter precedes a recorded boot.")
        return _state("unknown_completion_previous_boot", since) if pending else _state("clear")

    def _remember_action(self, path, action):
        """Advisory only. Keep the v1 journal and its completion protocol intact."""
        try:
            from modules import history, logger
            if not history.action_id(action):
                return
            info = path.lstat()
            data = {"record": path.name, "file_id": info.st_ino, "created": info.st_birthtime_ns, "action": action}
            self._action = data
            base = self.state_path.parent
            if self._default_path and base != logger.data_directory():
                return
            with _guard_path(base) as parents:
                pending = base / "maintenance-action.pending"
                if os.path.lexists(pending):
                    with _windows_handle(pending, delete=True) as (_, handle, old):
                        if old.links != 1 or old.attributes & 0x10:
                            return
                        rename_same_parent(handle, "maintenance-action.json")
                with relative_handle(parents[-1], pending.name) as (api, handle, _):
                    write_bytes(api, handle, json.dumps(data).encode("ascii"))
                    _validate_guards(parents)
                    rename_same_parent(handle, "maintenance-action.json")
        except Exception:
            pass  # A missing label never participates in the guard decision.

    def _known_action(self):
        try:
            from modules import history
            data = self._action
            if not data:
                base = self.state_path.parent
                with _guard_path(base), _windows_handle(base / "maintenance-action.json") as (api, handle, info):
                    if info.links != 1 or info.attributes & 0x10:
                        return None
                    data = json.loads(read_bytes(api, handle, 512))
            if not re.fullmatch(r"boot-[0-9a-f]{64}\.json", data["record"]):
                return None
            record = self._journal().state_path / data["record"]
            with _guard_path(record.parent), _windows_handle(record):
                identity = record.lstat()
                if (identity.st_ino, identity.st_birthtime_ns) == (data["file_id"], data["created"]):
                    return history.action_id(data["action"])
        except Exception:
            pass
        return None

    def _status_locked(self):
        try:
            old = self._directory_state()
            journal = self._journal()._directory_state(journal=True)
            # A known timeout still requires a restart even alongside a damaged journal.
            states = (old, journal)
            priorities = ("unknown_completion_same_boot", "unverifiable_storage", "interrupted_journal",
                          "unknown_completion_previous_boot", "clear")
            state = min(states, key=lambda item: priorities.index(item["code"]))
            if self.state_path is None or not self.state_path.is_absolute():
                return _state("unverifiable_storage")
            pending = self.state_path.parent / "maintenance-recovery-pending"
            try:
                pending_since = _modified(pending)
            except FileNotFoundError:
                pass
            else:
                if state["code"] != "unknown_completion_same_boot":
                    state = _state("interrupted_journal", pending_since)
            if self._blocked:
                if self._unknown_boot is None:
                    state = _state("unverifiable_storage", state["since"])
                else:
                    current = int(_boot_token(self._boot_identity()).split(":")[1])
                    original = int(self._unknown_boot.split(":")[1])
                    if current == original:
                        state = _state("unknown_completion_same_boot", state["since"])
                    elif current < original:
                        state = _state("unverifiable_storage", state["since"])
                    elif state["safe_to_clear"]:
                        state = _state("unknown_completion_previous_boot", state["since"])
                        state["blocked"] = True  # Explicit verification releases the in-process latch.
            if state["code"] != "clear":
                state["action_id"] = self._known_action()
            return state
        except Exception as exc:
            return _state("unverifiable_storage", message=f"Maintenance remains blocked: {exc}")

    def status(self):
        """Probe the shared lease without waiting, writing or clearing evidence."""
        try:
            with _maintenance_mutex(0):
                return self._status_locked()
        except TimeoutError:
            return _state("busy_other_instance")
        except Exception:
            return _state("unverifiable_storage")

    def is_blocked(self):
        state = self._status_locked()
        self.last_error = state["message"] if state["blocked"] else ""
        return state["blocked"]

    def verify_again(self):
        with _maintenance_mutex(0):
            state = self._status_locked()
            if state["code"] == "unknown_completion_previous_boot" and state["safe_to_clear"]:
                self._archive_locked(manual=False)
                self._blocked = False
                self._action = None
            return self._status_locked()

    def archive(self, expected):
        """The reliability service consumes consent before entering this transaction."""
        with _maintenance_mutex(0):
            state = self._status_locked()
            if state["code"] not in {"interrupted_journal", "unverifiable_storage"} or state != expected:
                raise ValueError("Recovery evidence changed; review the current state")
            self._archive_locked(manual=True)
            self._blocked = False
            self._action = None
            return self._status_locked()

    def _archive_locked(self, *, manual):
        from modules import history, logger
        if self.state_path is None or not self.state_path.is_absolute():
            raise OSError("Missing recovery directory")
        base = self.state_path.parent
        if self._default_path and base != logger.data_directory():
            raise OSError("Recovery storage does not match the Windows Known Folder")
        sources = (self.state_path, self._journal().state_path)
        staging = base / "maintenance-recovery-pending"
        if not any(os.path.lexists(path) for path in (*sources, staging)):
            if manual:
                raise OSError("There is no durable evidence to archive")
            return
        metadata = (base / "maintenance-action.json", base / "maintenance-action.pending")
        sources = (*sources, *metadata)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        with _guard_path(base) as parents, ExitStack() as stack:
            # A damaged sibling never downgrades a recognizable current-boot timeout.
            if manual:
                try:
                    timeout_file = self.state_path / _record_name(_boot_token(self._boot_identity()))
                except (OSError, ValueError):
                    timeout_file = None
                if timeout_file is not None and os.path.lexists(timeout_file):
                    raise ValueError("Restart Windows before archiving a current-boot timeout")
            sources_stack = stack.enter_context(ExitStack())
            # Preflight every source before creating or moving anything. Move whole
            # directories by handle; never traverse or delete their contents.
            retained = []
            for source in sources:
                try:
                    opened = sources_stack.enter_context(_windows_handle(source, delete=True, read_for_delete=True))
                except FileNotFoundError:
                    continue
                kernel, handle, info = opened
                if bool(info.attributes & 0x10) != (source not in metadata) or (source in metadata and info.links != 1):
                    raise OSError("Unexpected recovery object")
                retained.append((kernel, handle, source))
            with relative_handle(parents[-1], staging.name, directory=True) as (kernel, stage, _):
                try:
                    with relative_handle((kernel, stage, staging), "archive.intent") as (api, handle, _):
                        write_bytes(api, handle, b"Panacea recovery v1")
                except FileExistsError:
                    pass
            with _rename_destination(staging) as (kernel, stage), _windows_handle(staging / "archive.intent") as (_, _, info):
                if info.links != 1 or info.attributes & 0x10:
                    raise OSError("Unsafe recovery intent")
                for source_kernel, source_handle, source in retained:
                    _validate_handle(source_kernel, source_handle, source)
                    _validate_handle(kernel, stage, staging)
                    _move_directory(source_handle, stage, source.name)
            sources_stack.close()
            # Staging itself blocks maintenance after any partial move or audit
            # failure. On retry, the same directory retains all earlier evidence.
            if manual:
                now = datetime.now(timezone.utc).timestamp()
                history.append(history.operation_record("archive_guard", now, {"status": "confirmed", "success": True}))
            with _windows_handle(staging, delete=True) as (_, stage, _):
                _validate_guards(parents)
                _move_directory(stage, None, "maintenance-archive-" + stamp + "-" + uuid4().hex[:8])

    @contextmanager
    def operation(self, timeout_ms=30000):
        """Require an exclusive process lease and a flushed journal BEFORE work.

        A caught/uncertain exception or a failed persistence operation leaves
        the session record for the next launch. Only resolve() on an ordinary,
        verified terminal outcome permits atomically completing the owned record.
        """
        with _maintenance_mutex(timeout_ms):
            if self.is_blocked():
                raise RuntimeError(self.last_error or 'Maintenance remains blocked')
            journal = self._journal()
            boot_id = journal.begin()
            path = journal.state_path / _record_name(boot_id)
            self._action = None
            permit = _OperationPermit(lambda action: self._remember_action(path, action))
            try:
                yield permit
            except BaseException:
                raise
            else:
                if permit.resolved:
                    journal.complete(boot_id)

    def mark_unknown(self):
        """Persist a timeout marker; False reports save failure, never clears a block."""
        self._blocked = True
        self.last_error = 'Maintenance completion is unverified. Restart Windows before running maintenance again.'
        try:
            boot_id = _boot_token(self._boot_identity())
        except Exception:
            boot_id = None
            self.last_error = 'The original Windows boot is unknown; maintenance remains blocked until recovery is verified.'
        self._unknown_boot = boot_id
        try:
            with self._storage_directory(create=True) as guards:
                name = _record_name(boot_id)
                if name in self._read_records(guards):
                    return True
                try:
                    with relative_handle(guards[-1], name) as (kernel, handle, _):
                        _validate_guards(guards)
                        write_bytes(kernel, handle, json.dumps({'version': 1, 'boot_id': boot_id}).encode('utf-8'))
                        _validate_handle(kernel, handle, self.state_path / name)
                        _validate_guards(guards)
                except FileExistsError:
                    # A concurrent writer owns this immutable record. Verify it, never replace it.
                    if name not in self._read_records(guards):
                        raise OSError('Concurrent maintenance record could not be verified')
            return True
        except Exception as exc:
            self.last_error = f'Maintenance remains blocked; could not save the recovery guard: {exc}'
            return False


class _MaintenanceJournal(MaintenanceGuard):
    """Pre-execution records plus atomic successful-completion evidence.

    An empty directory means interrupted initialization and fails closed.
    A completed.json record is valid only after the owned pending record is
    atomically renamed following a verified terminal outcome. Old-boot pending
    records become nonblocking only after a provably greater Windows BootId.
    The caller holds the shared named mutex throughout every mutation.
    """

    def begin(self):
        boot_id = _boot_token(self._boot_identity())
        name = _record_name(boot_id)
        with self._storage_directory(create=True) as guards:
            if name in self._read_records(guards, allow_completed=True):
                raise RuntimeError('An unfinished maintenance operation is recorded for this Windows boot')
            # FILE_CREATE, handle-bound writing and FlushFileBuffers prevent
            # side effects until the durable record has been read back.
            with relative_handle(guards[-1], name) as (kernel, handle, _):
                _validate_guards(guards)
                write_bytes(kernel, handle, json.dumps({'version': 1, 'boot_id': boot_id}).encode('utf-8'))
                _validate_handle(kernel, handle, self.state_path / name)
                _validate_guards(guards)
            if self._read_records(guards, allow_completed=True).get(name) != boot_id:
                raise OSError('Maintenance journal could not be verified before mutation')
        return boot_id

    def complete(self, boot_id):
        boot_id = _boot_token(boot_id)
        name = _record_name(boot_id)
        path = self.state_path / name
        with self._storage_directory() as guards:
            records = self._read_records(guards, allow_completed=True)
            if records.get(name) != boot_id:
                raise ValueError('Active maintenance journal is missing or altered')
            # Atomic same-directory rename is the completed transaction record.
            # A failed rename leaves the active record in place and blocks reuse.
            with _windows_handle(path, delete=True, read_for_delete=True) as (kernel, handle, info):
                if info.links != 1 or info.attributes & 0x10:
                    raise ValueError('Unsafe maintenance journal record')
                data = json.loads(read_bytes(kernel, handle, 1024).decode('utf-8'))
                if data != {'version': 1, 'boot_id': boot_id}:
                    raise ValueError('Maintenance journal identity changed')
                _validate_handle(kernel, handle, path)
                _validate_guards(guards)
                rename_same_parent(handle, 'completed.json')
                _validate_guards(guards)
            if self._read_records(guards, allow_completed=True).get('completed.json') != boot_id:
                raise OSError('Completed maintenance journal could not be verified')
