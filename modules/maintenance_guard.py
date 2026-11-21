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
    if os.name != 'nt':
        raise OSError('Windows maintenance process locking is unavailable')
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
    handle = kernel.CreateMutexW(None, False, 'Global\\PanaceaMaintenanceV2')
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


class _OperationPermit:
    """Only a normally returned and verified command may resolve its journal."""

    def __init__(self):
        self.resolved = False

    def resolve(self):
        self.resolved = True


class MaintenanceGuard:
    def __init__(self, state_path=None, boot_identity=None):
        base = os.environ.get('LOCALAPPDATA')
        self.state_path = (Path(state_path) if state_path is not None else
                           Path(base) / 'Panacea' / 'maintenance-guard' if base else None)
        self._boot_identity = boot_identity or windows_boot_identity
        self._blocked = False
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

    def is_blocked(self):
        """Read old timeout records and pre-execution journals without writes."""
        if self._blocked:
            return True
        self.last_error = ''
        try:
            try:
                with self._storage_directory() as guards:
                    records = self._read_records(guards)
            except FileNotFoundError:
                records = None
            if records is not None:
                if not records:
                    raise ValueError('The maintenance guard write was interrupted before its record was saved')
                if None in records.values():
                    raise ValueError('The original Windows boot is unknown; maintenance completion cannot be verified')
                current_boot = _boot_token(self._boot_identity())
                current_counter = int(current_boot.split(':')[1])
                if any(current_counter <= int(record.split(':')[1]) for record in records.values()):
                    self.last_error = 'Maintenance completion is unverified. Restart Windows before running maintenance again.'
                    return True
            journal = self._journal()
            if journal.is_blocked():
                self.last_error = journal.last_error
                return True
            return False
        except Exception as exc:
            self.last_error = f'Maintenance remains blocked: {exc}'
            return True

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
            permit = _OperationPermit()
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

    def is_blocked(self):
        self.last_error = ''
        try:
            try:
                with self._storage_directory() as guards:
                    records = self._read_records(guards, allow_completed=True)
            except FileNotFoundError:
                return False
            if not records:
                raise ValueError('Maintenance journal initialization is unverified (empty directory)')
            if None in records.values():
                raise ValueError('Maintenance journal has an unknown Windows boot identity')
            pending = {name: boot for name, boot in records.items() if name != 'completed.json'}
            current = int(_boot_token(self._boot_identity()).split(':')[1])
            if any(current <= int(old.split(':')[1]) for old in pending.values()):
                self.last_error = 'Unfinished maintenance was detected. Restart Windows before running maintenance again.'
                return True
            return False
        except Exception as exc:
            self.last_error = f'Unverified maintenance journal: {exc}'
            return True

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

