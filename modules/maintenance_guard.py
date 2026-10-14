"""Keep unverified maintenance blocked across app reopens until a verified boot.

Immutable records avoid replacing a stronger unknown-boot marker during concurrent
writes. An interrupted write intentionally leaves a record that fails closed.
"""
from contextlib import contextmanager, ExitStack
import hashlib
import json
import os
from pathlib import Path
import re

from modules.cleanup import _guard_path, _validate_guards, _validate_handle, _windows_handle
from modules.protected_files import relative_handle, read_bytes, write_bytes


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

    def _read_records(self, guards):
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
                    if entry.name != _record_name(boot_id):
                        raise ValueError('Maintenance guard identity does not match its record')
                    records[entry.name] = boot_id
            _validate_guards(guards)
            return records
        except OSError as exc:
            # A missing or replaced record is not proof of an absent guard directory.
            raise ValueError(f'Maintenance guard records cannot be verified: {exc}') from exc

    def is_blocked(self):
        """Read without creating storage; any unverifiable existing record blocks."""
        if self._blocked:
            return True
        self.last_error = ''
        try:
            try:
                with self._storage_directory() as guards:
                    records = self._read_records(guards)
            except FileNotFoundError:
                return False
            if not records:
                raise ValueError('The maintenance guard write was interrupted before its record was saved')
            if None in records.values():
                raise ValueError('The original Windows boot is unknown; maintenance completion cannot be verified')
            current_boot = _boot_token(self._boot_identity())
            current_counter = int(current_boot.split(':')[1])
            if any(current_counter <= int(record.split(':')[1]) for record in records.values()):
                self.last_error = 'Maintenance completion is unverified. Restart Windows before running maintenance again.'
                return True
            return False
        except Exception as exc:
            self.last_error = f'Maintenance remains blocked: {exc}'
            return True

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
