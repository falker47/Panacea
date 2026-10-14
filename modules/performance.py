"""Turbo settings with durable original snapshots and verified exact restoration."""
import json
import hashlib
import ctypes
from ctypes import wintypes
from contextlib import contextmanager, ExitStack
import os
from pathlib import Path
import re
import subprocess
import secrets
import threading
import time

from modules.commands import system_executable
from modules.cleanup import _guard_path, _windows_handle, _validate_guards, _validate_handle
from modules.protected_files import relative_handle, read_bytes, write_bytes, rename_same_parent, dispose
from modules.logger import Logger


@contextmanager
def _process_transaction_lock(state_path, timeout_ms):
    """Windows releases an owned named mutex when its process terminates."""
    if os.name != 'nt' or state_path is None or not state_path.is_absolute():
        raise OSError('Protected Turbo transaction locking is unavailable')
    identity = os.path.normcase(os.path.abspath(state_path))
    name = 'Global\\PanaceaTurbo-' + hashlib.sha256(identity.encode('utf-8')).hexdigest()
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
        status = kernel.WaitForSingleObject(handle, timeout_ms)
        if status == 0x102:
            raise TimeoutError('Turbo transaction lock is busy; retry when the other app finishes.')
        if status not in (0, 0x80):  # WAIT_OBJECT_0 / WAIT_ABANDONED
            raise ctypes.WinError(ctypes.get_last_error())
        acquired = True
        yield  # An abandoned owner is safe only after the caller reloads its durable snapshot.
    finally:
        if acquired:
            kernel.ReleaseMutex(handle)
        kernel.CloseHandle(handle)


class PerformanceManager:
    POWER_HIGH_PERF = '8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c'
    POWER_BALANCED = '381b4222-f694-41f0-9685-ff5bb260df2e'
    SERVICES = ('SysMain', 'WSearch', 'Spooler')
    VISUAL_KEY = r'Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects'
    _lock = threading.RLock()
    _lock_timeout_ms = 30000
    _GUID = re.compile(r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}')

    def __init__(self, logger=None, state_path=None):
        self.logger = logger if logger is not None else Logger()
        base = os.environ.get('LOCALAPPDATA')
        self.state_path = Path(state_path) if state_path else (Path(base) / 'Panacea' / 'turbo-state.json' if base else None)
        self._state = {}
        self._state_error = None
        self._load_state()

    @contextmanager
    def _transaction(self):
        with self._lock:
            with _process_transaction_lock(self.state_path, self._lock_timeout_ms):
                self._load_state()  # Constructors/managers may predate another app's changes.
                yield

    def _load_state(self):
        self._state_error = None
        try:
            if self.state_path is None:
                raise ValueError('Original-state storage is unavailable')
            with self._storage_directory(create=False) as guards:
                _validate_guards(guards)
                with _windows_handle(self.state_path) as (kernel, handle, info):
                    if info.attributes & 0x10 or info.links != 1 or (info.size_high << 32) | info.size_low > 16384:
                        raise ValueError('Unsafe original-state file')
                    data = json.loads(read_bytes(kernel, handle, 16384).decode('utf-8'))
                _validate_guards(guards)
            original = data.get('original')
            if data.get('version') != 1 or not isinstance(original, dict) or set(original) - {'power', 'visual', *self.SERVICES}:
                raise ValueError('Invalid original-state file')
            if 'power' in original and (not isinstance(original['power'], str) or not self._GUID.fullmatch(original['power'])):
                raise ValueError('Invalid original power scheme')
            for service in self.SERVICES:
                if service in original and type(original[service]) is not bool:
                    raise ValueError('Invalid original service state')
            if 'visual' in original and (type(original['visual']) is not int or original['visual'] not in range(4)):
                raise ValueError('Invalid original visual setting')
            self._state = original
        except FileNotFoundError:
            self._state = {}
        except Exception as exc:
            self._state_error = str(exc)

    @contextmanager
    def _storage_directory(self, create=False):
        if self.state_path is None or not self.state_path.is_absolute():
            raise OSError('An absolute recovery file path is required')
        directory = self.state_path.parent
        missing = []
        ancestor = directory
        while not os.path.lexists(ancestor):
            if not create or ancestor.parent == ancestor:
                raise FileNotFoundError('Recovery directory is unavailable')
            missing.append(ancestor)
            ancestor = ancestor.parent
        if os.name == 'nt':
            with ExitStack() as stack:
                guards = stack.enter_context(_guard_path(ancestor))
                _validate_guards(guards)
                for child in reversed(missing):
                    kernel, handle, info = stack.enter_context(relative_handle(guards[-1], child.name, directory=True))
                    if not info.attributes & 0x10:
                        raise OSError('Recovery directory was replaced')
                    guards.append((kernel, handle, child))
                _validate_guards(guards)
                yield guards
        else:
            # Turbo is Windows-only; refuse persistence on unsupported platforms.
            raise OSError('Protected Turbo recovery requires Windows')

    def _save_state(self):
        if self.state_path is None:
            raise OSError('Original-state storage is unavailable')
        payload = json.dumps({'version': 1, 'original': self._state}).encode('utf-8')
        with self._storage_directory(create=True) as guards:
            temporary = self.state_path.parent / ('turbo-' + secrets.token_hex(16) + '.tmp')
            with relative_handle(guards[-1], temporary.name) as (kernel, handle, _):
                committed = False
                try:
                    _validate_guards(guards)
                    write_bytes(kernel, handle, payload)
                    _validate_guards(guards)
                    _validate_handle(kernel, handle, temporary)
                    rename_same_parent(handle, self.state_path.name)
                    committed = True
                    _validate_guards(guards)
                finally:
                    if not committed:
                        dispose(kernel, handle)

    def _run_cmd(self, cmd, hide=True):
        try:
            args = cmd.split() if isinstance(cmd, str) else list(cmd)
            if len(args) == 2 and args == ['powercfg', '/getactivescheme']:
                pass
            elif len(args) == 3 and args[:2] == ['powercfg', '/setactive'] and self._GUID.fullmatch(args[2]):
                pass
            elif len(args) == 3 and args[0] == 'sc' and args[1] in ('query', 'start', 'stop') and args[2] in self.SERVICES:
                pass
            else:
                raise ValueError('Unapproved Turbo command')
            args[0] = system_executable(args[0] + '.exe')
            result = subprocess.run(args, shell=False, stdin=subprocess.DEVNULL,
                                    capture_output=True, text=True, timeout=30,
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0) if hide else 0)
            return result.returncode == 0, (result.stdout or '') + (result.stderr or '')
        except Exception as exc:
            return False, str(exc)

    def _get_power_guid(self):
        success, output = self._run_cmd(['powercfg', '/getactivescheme'])
        found = self._GUID.search(output) if success else None
        return found.group().lower() if found else None

    def get_power_plan(self):
        guid = self._get_power_guid()
        if guid is None:
            return None
        return 'high' if guid == self.POWER_HIGH_PERF else 'balanced' if guid == self.POWER_BALANCED else 'other'

    def get_service_status(self, service_name):
        if service_name not in self.SERVICES:
            return None
        success, output = self._run_cmd(['sc', 'query', service_name])
        if not success:
            return None
        # Numeric states are stable on localized Windows installations.
        state = re.search(r'STATE\s*:\s*([1-7])\b', output, re.IGNORECASE)
        if state:
            return True if state[1] == '4' else False if state[1] == '1' else None
        if re.search(r'\bRUNNING\b', output):
            return True
        if re.search(r'\bSTOPPED\b', output):
            return False
        return None

    def _get_visual_value(self):
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.VISUAL_KEY) as key:
                value, kind = winreg.QueryValueEx(key, 'VisualFXSetting')
            return value if kind == winreg.REG_DWORD and type(value) is int and value in range(4) else None
        except Exception:
            return None

    def get_visual_effects(self):
        value = self._get_visual_value()
        return value != 2 if value is not None else None

    def _set_visual_value(self, value):
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.VISUAL_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, 'VisualFXSetting', 0, winreg.REG_DWORD, value)
            return True, 'Visual setting saved.'
        except Exception as exc:
            return False, str(exc)

    def _change(self, key, activate, read, write, active_value):
        try:
            with self._transaction():
                return self._change_locked(key, activate, read, write, active_value)
        except OSError as exc:
            return False, f'Cannot acquire the Turbo transaction lock: {exc}'

    def _change_locked(self, key, activate, read, write, active_value):
        with self._lock:
            self._load_state()
            if self._state_error:
                return False, f'Cannot safely change settings: {self._state_error}'
            if not activate and key not in self._state:
                return True, f'No saved {key} change to restore.'
            current = read()
            if current is None:
                return False, f'Current {key} state is unknown; no change was made.'
            if activate:
                if key not in self._state:
                    self._state[key] = current
                    try:
                        self._save_state()  # The original must reach durable storage before mutation.
                    except Exception as exc:
                        self._load_state()
                        return False, f'Cannot save original {key} state: {exc}'
                target = active_value
            else:
                target = self._state[key]
            if current != target:
                success, message = write(target)
                if not success:
                    return False, message
                if read() != target:
                    return False, f'{key} change could not be verified; original state retained.'
            if not activate:
                original = self._state.pop(key)
                try:
                    self._save_state()
                except Exception as exc:
                    self._state[key] = original
                    return False, f'{key} restored, but recovery record could not be updated: {exc}'
            return True, f'{key} {"enabled" if activate else "restored to its original state"}.'

    def set_power_plan(self, high_performance=True):
        return self._change('power', high_performance, self._get_power_guid,
                            lambda guid: self._run_cmd(['powercfg', '/setactive', guid]), self.POWER_HIGH_PERF)

    def _write_service(self, name, running):
        success, message = self._run_cmd(['sc', 'start' if running else 'stop', name])
        if not success:
            return False, message
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if self.get_service_status(name) == running:
                return True, message
            time.sleep(0.1)
        return False, f'{name} state change could not be verified.'

    def set_service(self, service_name, start=True):
        if service_name not in self.SERVICES:
            return False, 'Only SysMain, WSearch and Spooler are supported.'
        return self._change(service_name, not start, lambda: self.get_service_status(service_name),
                            lambda running: self._write_service(service_name, running), False)

    def set_visual_effects(self, enable_effects=True):
        return self._change('visual', not enable_effects, self._get_visual_value, self._set_visual_value, 2)

    def get_sysmain_status(self): return self.get_service_status('SysMain')
    def set_sysmain(self, enable=True): return self.set_service('SysMain', start=enable)
    def get_wsearch_status(self): return self.get_service_status('WSearch')
    def set_wsearch(self, enable=True): return self.set_service('WSearch', start=enable)
    def get_spooler_status(self): return self.get_service_status('Spooler')
    def set_spooler(self, enable=True): return self.set_service('Spooler', start=enable)

    def get_saved_settings(self):
        """Return recoverable setting keys, or None if the record is unreadable.

        Pending originals survive partial activation/restoration and are separate
        from whether every live setting currently matches the Turbo profile.
        """
        try:
            with self._transaction():
                return None if self._state_error else tuple(self._state)
        except OSError:
            return None

    def is_turbo_active(self):
        try:
            with self._transaction():
                return self._is_turbo_active_locked()
        except OSError:
            return None

    def _is_turbo_active_locked(self):
        with self._lock:
            self._load_state()
            if self._state_error:
                return None
        states = [self.get_power_plan(), self.get_visual_effects(), *[self.get_service_status(s) for s in self.SERVICES]]
        if any(state is None for state in states):
            return None
        active = states == ['high', False, False, False, False]
        if active and not all(key in self._state for key in ('power', 'visual', *self.SERVICES)):
            return None  # Settings alone do not prove Panacea can restore their originals.
        return active

    def set_turbo(self, enabled=True):
        try:
            with self._transaction():
                return self._set_turbo_locked(enabled)
        except OSError as exc:
            return False, f'Cannot acquire the Turbo transaction lock: {exc}'

    def _set_turbo_locked(self, enabled):
        with self._lock:
            self._load_state()
            if self._state_error:
                return False, f'Original-state recovery is unavailable: {self._state_error}'
            # Capture and persist every original before changing any master setting.
            if enabled:
                snapshot = {'power': self._get_power_guid(), 'visual': self._get_visual_value(),
                            **{name: self.get_service_status(name) for name in self.SERVICES}}
                if any(value is None for value in snapshot.values()):
                    return False, 'Turbo cannot start while any original setting is unknown.'
                for key, value in snapshot.items():
                    self._state.setdefault(key, value)
                try:
                    self._save_state()
                except Exception as exc:
                    return False, f'Cannot save original settings: {exc}'
            methods = [(self.set_power_plan, enabled), (self.set_visual_effects, not enabled),
                       (self.set_sysmain, not enabled), (self.set_wsearch, not enabled),
                       (self.set_spooler, not enabled)]
            failures = []
            for method, argument in methods:
                success, message = method(argument)
                if not success:
                    failures.append(message)
                    if enabled:
                        break
            if failures:
                return False, 'Turbo change did not complete; saved originals remain available. ' + '; '.join(failures)
            return True, 'Turbo enabled.' if enabled else 'Original settings restored.'
