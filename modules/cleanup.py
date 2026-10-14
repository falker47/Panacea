"""Conservative cache cleanup with Windows handles protecting path traversal."""
import ctypes
from ctypes import wintypes
from contextlib import contextmanager, ExitStack
from dataclasses import dataclass, field
import os
from pathlib import Path
import re
import stat
import subprocess
import threading

from modules.commands import system_executable
from modules.logger import Logger


@dataclass(frozen=True)
class CleanupIssue:
    """One original diagnostic with an evidence-based, locale-independent cause."""
    kind: str
    reason: str
    path: str
    detail: str
    winerror: int | None = None


@dataclass
class CleanupResult:
    """Current-pass counts: logical file bytes, never a previous preview estimate."""
    count: int = 0
    bytes: int = 0
    skipped: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    preview: bool = False
    issues: list[CleanupIssue] = field(default_factory=list)

    @property
    def ok(self):
        return not self.errors and not self.skipped

    def _issue_counts(self, kind, diagnostics):
        counts = {}
        for issue in self.issues:
            if issue.kind == kind:
                counts[issue.reason] = counts.get(issue.reason, 0) + 1
        # Legacy callers may still provide only diagnostic strings. Do not infer
        # causes from localized text, or lose those entries from grouped counts.
        unmatched = len(diagnostics) - sum(counts.values())
        if unmatched > 0:
            counts['unknown'] = counts.get('unknown', 0) + unmatched
        return counts

    @property
    def skipped_counts(self):
        """Counts diagnostic entries, including directories, not unseen files."""
        return self._issue_counts('skipped', self.skipped)

    @property
    def error_counts(self):
        return self._issue_counts('error', self.errors)

    def add_issue(self, kind, path, error, *, reason=None, detail=None):
        code = getattr(error, 'winerror', None)
        reason = reason or getattr(error, 'reason', None)
        if reason is None:
            reason = {2: 'disappeared', 3: 'disappeared', 5: 'access_denied',
                      32: 'locked', 33: 'locked'}.get(code)
        if reason is None:
            reason = 'filesystem_error' if isinstance(error, OSError) else 'unexpected_error'
        path = str(path) if path is not None else ''
        detail = detail if detail is not None else f'{path}: {error}' if path else str(error)
        self.issues.append(CleanupIssue(kind, reason, path, detail, code))
        (self.skipped if kind == 'skipped' else self.errors).append(detail)


class UnsafePath(OSError):
    def __init__(self, message, *, reason='identity_unverified'):
        super().__init__(message)
        self.reason = reason


class _FileInfo(ctypes.Structure):
    _fields_ = [('attributes', wintypes.DWORD), ('creation', wintypes.FILETIME),
                ('access', wintypes.FILETIME), ('write', wintypes.FILETIME),
                ('volume', wintypes.DWORD), ('size_high', wintypes.DWORD),
                ('size_low', wintypes.DWORD), ('links', wintypes.DWORD),
                ('index_high', wintypes.DWORD), ('index_low', wintypes.DWORD)]


class _RecycleBinInfo(ctypes.Structure):
    _fields_ = [('cbSize', wintypes.DWORD), ('i64Size', ctypes.c_longlong),
                ('i64NumItems', ctypes.c_longlong)]


def _lexical_path(path):
    """Immutable DOS identity: never resolve through an untrusted ancestor."""
    full = os.path.abspath(path)
    drive, tail = os.path.splitdrive(full)
    if len(drive) != 2 or drive[1] != ':' or not drive[0].isalpha() or not tail.startswith('\\'):
        raise UnsafePath('Only local DOS paths are supported', reason='unsupported_path')
    if any(part.endswith((' ', '.')) or ':' in part for part in tail.split('\\') if part):
        raise UnsafePath('Ambiguous file name refused', reason='ambiguous_path')
    return full


def _validate_handle(kernel, handle, path):
    """Bind the opened object to the approved spelling, including live attributes."""
    expected = _lexical_path(path)
    info = _FileInfo()
    if not kernel.GetFileInformationByHandle(handle, ctypes.byref(info)):
        raise ctypes.WinError(ctypes.get_last_error())
    if info.attributes & 0x400:
        raise UnsafePath(f'Reparse point refused: {path}', reason='reparse_point')
    if info.attributes & 0x10:
        flags = wintypes.DWORD()
        if not kernel.GetFileInformationByHandleEx(handle, 23, ctypes.byref(flags), ctypes.sizeof(flags)):
            raise UnsafePath(f'Cannot verify directory case sensitivity: {path}')
        if flags.value & 1:
            raise UnsafePath(f'Case-sensitive directory refused: {path}', reason='case_sensitive')
    buffer = ctypes.create_unicode_buffer(32768)
    length = kernel.GetFinalPathNameByHandleW(handle, buffer, len(buffer), 0)
    if not length or length >= len(buffer):
        raise UnsafePath(f'Cannot verify final file identity: {path}')
    actual = buffer.value
    if not actual.startswith('\\\\?\\') or actual.startswith('\\\\?\\UNC\\'):
        raise UnsafePath(f'Unsupported final file namespace: {path}', reason='unsupported_path')
    if os.path.normcase(actual[4:].rstrip('\\')) != os.path.normcase(expected.rstrip('\\')):
        raise UnsafePath(f'Opened object left its approved path: {path}')
    return info


def _validate_guards(guards):
    for kernel, handle, path in guards:
        _validate_handle(kernel, handle, path)


def _kernel_api():
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.POINTER(_FileInfo)]
    kernel.GetFileInformationByHandleEx.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
    kernel.GetFinalPathNameByHandleW.argtypes = [wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD]
    kernel.GetFinalPathNameByHandleW.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.SetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
    return kernel


@contextmanager
def _windows_handle(path, delete=False):
    """Deny data-write/delete sharing and validate the actual opened object.

    Attribute-only opens bypass sharing rules, so share flags alone cannot
    prevent reparse conversion. Final-path binding is the mutation boundary.
    """
    if os.name != 'nt':
        raise UnsafePath('Protected cleanup requires Windows file handles', reason='unsupported_platform')
    kernel = _kernel_api()
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    native = '\\\\?\\' + _lexical_path(path)
    # Attribute-only opens do not participate in Windows sharing rules.
    # LIST_DIRECTORY makes the deny-delete lock effective (READ_DATA for preview files).
    access = 0x80 | (0x10000 if delete else 1)
    handle = kernel.CreateFileW(native, access, 1, None, 3, 0x02200000, None)
    if handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        info = _validate_handle(kernel, handle, path)
        yield kernel, handle, info
    finally:
        kernel.CloseHandle(handle)


@contextmanager
def _guard_path(path):
    """Retain validated ancestors; callers can recheck live attributes."""
    full = Path(_lexical_path(path))
    with ExitStack() as stack:
        guards = []
        for item in [*reversed(full.parents), full]:
            kernel, handle, info = stack.enter_context(_windows_handle(item))
            if not info.attributes & 0x10:
                raise UnsafePath(f'Not a directory: {item}', reason='not_directory')
            guards.append((kernel, handle, item))
        _validate_guards(guards)
        yield guards


class CleanupManager:
    def __init__(self, logger=None):
        self.logger = logger if logger is not None else Logger()
        self.last_result = CleanupResult()
        self._lock = threading.RLock()

    @staticmethod
    def _normalized(path):
        return os.path.normcase(os.path.abspath(path))

    def _local_root(self):
        profile = os.environ.get('USERPROFILE')
        local = os.environ.get('LOCALAPPDATA')
        if not profile or not local or not os.path.isabs(profile) or not os.path.isabs(local):
            return None
        expected = os.path.join(profile, 'AppData', 'Local')
        return local if self._normalized(local) == self._normalized(expected) else None

    @staticmethod
    def _windows_root():
        if os.name != 'nt':
            return None
        buffer = ctypes.create_unicode_buffer(32768)
        if not ctypes.windll.kernel32.GetWindowsDirectoryW(buffer, len(buffer)):
            return None
        return buffer.value

    def get_temp_paths(self):
        paths = []
        if os.environ.get('TEMP'):
            paths.append(os.environ['TEMP'])
        elif self._local_root():
            paths.append(os.path.join(self._local_root(), 'Temp'))
        windows = self._windows_root()
        if windows:
            candidate = os.path.join(windows, 'Temp')
            if os.path.isdir(candidate):
                paths.append(candidate)
        return list({self._normalized(path): path for path in paths}.values())

    def _approved_temp(self, path):
        if not isinstance(path, (str, os.PathLike)) or not os.path.isabs(path):
            return False
        local = self._local_root()
        windows = self._windows_root()
        approved = [os.path.join(root, 'Temp') for root in (local, windows) if root]
        return self._normalized(path) in {self._normalized(item) for item in approved}

    def _browser_paths(self):
        local = self._local_root()
        if not local:
            self.last_result.add_issue('skipped', None, 'User cache location could not be verified.',
                                       reason='location_unavailable')
            return []
        targets = []
        for vendor, browser in (('Google', 'Chrome'), ('Microsoft', 'Edge')):
            user_data = os.path.join(local, vendor, browser, 'User Data')
            if not os.path.lexists(user_data):
                continue
            try:
                with _guard_path(user_data) as guards:
                    _validate_guards(guards)
                    names = os.listdir(user_data)
                    _validate_guards(guards)
                    targets.extend(os.path.join(user_data, name, cache) for name in names
                                   if name == 'Default' or re.fullmatch(r'Profile [0-9]+', name)
                                   for cache in ('Cache', 'Code Cache'))
            except OSError as exc:
                self.last_result.add_issue('skipped', user_data, exc)
        profiles = os.path.join(local, 'Mozilla', 'Firefox', 'Profiles')
        if os.path.isdir(profiles):
            try:
                with _guard_path(profiles) as guards:
                    _validate_guards(guards)
                    names = os.listdir(profiles)
                    _validate_guards(guards)
                    targets.extend(os.path.join(profiles, name, 'cache2') for name in names)
            except OSError as exc:
                self.last_result.add_issue('skipped', profiles, exc)
        return [path for path in targets if os.path.lexists(path)]

    def _delete_file(self, path, preview):
        with _windows_handle(path, delete=not preview) as (kernel, handle, info):
            if info.attributes & 0x10 or info.links != 1:
                raise UnsafePath(f'Directory or multiply linked file refused: {path}',
                                 reason='not_regular' if info.attributes & 0x10 else 'hard_link')
            size = (info.size_high << 32) | info.size_low
            if not preview:
                _validate_handle(kernel, handle, path)
                disposition = wintypes.BOOL(True)
                if not kernel.SetFileInformationByHandle(handle, 4, ctypes.byref(disposition), ctypes.sizeof(disposition)):
                    raise ctypes.WinError(ctypes.get_last_error())
        return size

    def _walk_directory(self, directory, preview, progress_callback):
        # Live checks reject persistent retargets; each child is independently
        # bound by its own handle even if an ancestor was retargeted and restored.
        try:
            with _windows_handle(directory) as (kernel, handle, _):
                with os.scandir(directory) as entries:
                    names = [entry.name for entry in entries]
                _validate_handle(kernel, handle, directory)
        except OSError as exc:
            self.last_result.add_issue('error', directory, exc)
            return
        for name in names:
            path = os.path.join(directory, name)
            try:
                info = os.lstat(path)
                if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                    raise UnsafePath(f'Reparse point refused: {path}', reason='reparse_point')
                if stat.S_ISDIR(info.st_mode):
                    with _windows_handle(path) as (_, _, held):
                        if not held.attributes & 0x10:
                            raise UnsafePath(f'Directory changed: {path}')
                        self._walk_directory(path, preview, progress_callback)
                elif stat.S_ISREG(info.st_mode):
                    size = self._delete_file(path, preview)
                    self.last_result.count += 1
                    self.last_result.bytes += size
                    if progress_callback and self.last_result.count % 50 == 0:
                        progress_callback(f'Found {self.last_result.count} eligible files...' if preview
                                          else f'Deleted {self.last_result.count} files...')
                else:
                    raise UnsafePath(f'Nonregular file refused: {path}', reason='not_regular')
            except OSError as exc:
                self.last_result.add_issue('skipped', path, exc)
            except Exception as exc:
                self.last_result.add_issue('error', path, exc)

    def _process_root(self, path, preview=False, progress_callback=None):
        try:
            with _guard_path(path):
                self._walk_directory(path, preview, progress_callback)
        except FileNotFoundError:
            # A validated, approved cache root may legitimately not exist yet.
            # A file disappearing after enumeration is still diagnosed per-file.
            return
        except OSError as exc:
            self.last_result.add_issue('skipped', path, exc)

    def _safe_progress(self, callback):
        if callback is None:
            return None
        failed = False
        def report(message):
            nonlocal failed
            if failed:
                return
            try:
                callback(message)
            except Exception as exc:
                failed = True
                self.last_result.add_issue('error', None, exc, reason='progress_callback')
        return report

    def _temp_operation(self, preview, progress_callback=None):
        with self._lock:
            self.last_result = CleanupResult(preview=preview)
            progress_callback = self._safe_progress(progress_callback)
            paths = self.get_temp_paths()
            if not paths:
                self.last_result.add_issue('skipped', None, 'Temporary file locations could not be verified.',
                                           reason='location_unavailable')
            for path in paths:
                if not self._approved_temp(path):
                    self.last_result.add_issue('skipped', path, '', reason='unapproved_root',
                                               detail=f'Unapproved temporary root: {path}')
                    continue
                if progress_callback:
                    progress_callback(f'Scanning {path}...')
                self._process_root(path, preview, progress_callback)
            self.logger.log(f'Cleanup {"preview" if preview else "finished"}: {self.last_result.count} files, '
                            f'{self.last_result.bytes} bytes; {len(self.last_result.skipped)} skipped, '
                            f'{len(self.last_result.errors)} errors.')
            return self.last_result.count, self.last_result.bytes

    def clean_temp_files(self, progress_callback=None):
        return self._temp_operation(False, progress_callback)

    def preview_temp_files(self, progress_callback=None):
        return self._temp_operation(True, progress_callback)

    def clean_browser_caches(self):
        with self._lock:
            self.last_result = CleanupResult()
            for path in self._browser_paths():
                self._process_root(path)
            return self.last_result.count, self.last_result.bytes

    def _delete_folder_contents(self, folder_path):
        with self._lock:
            self.last_result = CleanupResult()
            approved = self._approved_temp(folder_path) or self._normalized(folder_path) in {
                self._normalized(path) for path in self._browser_paths()}
            if approved:
                self._process_root(folder_path)
            else:
                self.last_result.add_issue('skipped', folder_path, '', reason='unapproved_root',
                                           detail=f'Unapproved cleanup root: {folder_path}')
            return self.last_result.count, self.last_result.bytes

    def empty_recycle_bin(self):
        try:
            result = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 7)
            if result == 0:
                return True, 'Recycle bin emptied.'
            if result == -2147418113:
                # E_UNEXPECTED is an error, not proof that every bin is empty.
                info = _RecycleBinInfo()
                info.cbSize = ctypes.sizeof(info)
                query = ctypes.windll.shell32.SHQueryRecycleBinW
                query.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(_RecycleBinInfo)]
                query.restype = wintypes.LONG
                if query(None, ctypes.byref(info)) == 0 and info.i64NumItems == 0:
                    return True, 'Recycle bin is empty (verified).'
            return False, f'Recycle bin operation returned code {result}.'
        except Exception as exc:
            self.logger.log(f'Failed to empty recycle bin: {exc}', 'ERROR')
            return False, str(exc)

    def open_disk_cleanup(self):
        try:
            subprocess.Popen([system_executable('cleanmgr.exe')], shell=False,
                             creationflags=getattr(subprocess, 'DETACHED_PROCESS', 0))
            return True
        except Exception as exc:
            self.logger.log(f'Failed to launch Disk Cleanup: {exc}', 'ERROR')
            return False
