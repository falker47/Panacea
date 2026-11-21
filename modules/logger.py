"""Panacea logging and validated access to its per-user storage."""
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import hashlib
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import stat
import threading
from uuid import UUID


_FOLDER_IDS = {
    "local": UUID("f1b32785-6fba-4fcf-9d55-7b8e7f157091"),
    "downloads": UUID("374de290-123f-4565-9164-39c4925e467b"),
}


def known_folder(name):
    return _shell_path(_FOLDER_IDS[name])


def _shell_path(folder_id):
    if os.name != "nt":
        raise OSError("Windows Known Folders are unavailable")
    folder = ctypes.c_wchar_p()
    get = ctypes.windll.shell32.SHGetKnownFolderPath
    get.argtypes = [ctypes.c_void_p, wintypes.DWORD, wintypes.HANDLE, ctypes.POINTER(ctypes.c_wchar_p)]
    get.restype = ctypes.c_long
    free = ctypes.windll.ole32.CoTaskMemFree
    free.argtypes = [ctypes.c_void_p]
    free.restype = None
    try:
        if get(folder_id.bytes_le, 0, None, ctypes.byref(folder)) or not folder.value:
            raise OSError("Windows Known Folder is unavailable")
        path = Path(folder.value)
        if not path.is_absolute():
            raise OSError("Windows returned a relative Known Folder")
        return path
    finally:
        if folder:
            free(folder)


def data_directory():
    return known_folder("local") / "Panacea"


def _plain(info):
    return not (stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400)


@contextmanager
def directory(path, *, create=False):
    """Keep the Windows directory chain pinned across child opens and renames."""
    from contextlib import ExitStack

    path = Path(path)
    if not path.is_absolute():
        raise OSError("An absolute storage directory is required")
    with ExitStack() as stack:
        if os.name == "nt":
            from modules.cleanup import _guard_path
            from modules.protected_files import relative_handle
            existing = path
            missing = []
            while create and not os.path.lexists(existing) and existing != existing.parent:
                missing.append(existing)
                existing = existing.parent
            if missing:
                with ExitStack() as creation:
                    chain = creation.enter_context(_guard_path(existing))
                    for child in reversed(missing):
                        kernel, handle, _ = creation.enter_context(relative_handle(chain[-1], child.name, directory=True))
                        chain.append((kernel, handle, child))
            stack.enter_context(_guard_path(path))
        else:
            for item in (*reversed(path.parents), path):
                if create:
                    item.mkdir(exist_ok=True)
                info = item.lstat()
                if not _plain(info) or not stat.S_ISDIR(info.st_mode):
                    raise OSError("Unsafe storage directory")
        yield path


def open_regular(path, mode, **kwargs):
    """Open a single-link file without truncation. Check its handle before I/O."""
    if mode not in ("rb", "ab", "a", "a+b", "xb", "x+b"):
        raise ValueError("Unsupported file mode")
    path = Path(path)
    with directory(path.parent):
        try:
            before = path.lstat()
        except FileNotFoundError:
            before = None
        if before and (not _plain(before) or not stat.S_ISREG(before.st_mode) or before.st_nlink != 1):
            raise OSError("Unsafe storage file")
        def opener(name, flags):
            if mode.startswith("a"):
                # An inserted dangling link must never turn an append into a
                # create outside this directory. Existing files are open-only.
                flags = (flags | os.O_EXCL) if before is None else (flags & ~os.O_CREAT)
            return os.open(name, flags | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0), 0o600)
        stream = open(path, mode, opener=opener, **kwargs)
        try:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or (before and not os.path.samestat(before, info)):
                raise OSError("Storage file identity changed")
            if os.name == "nt":
                import msvcrt
                from modules.cleanup import _kernel_api, _validate_handle
                _validate_handle(_kernel_api(), msvcrt.get_osfhandle(stream.fileno()), path)
            return stream
        except BaseException:
            stream.close()
            raise


@contextmanager
def storage_lock(root):
    if os.name == "nt":
        from modules.maintenance_guard import _named_mutex
        identity = hashlib.sha256(os.path.normcase(str(root)).encode("utf-8")).hexdigest()
        with _named_mutex("Global\\PanaceaReliability." + identity, 3000):
            yield
    else:
        yield


def replace_sibling(source, target):
    """Rotate or publish an owned regular file under its pinned parent."""
    with directory(source.parent):
        if os.name != "nt":
            os.replace(source, source.with_name(target))
            return
        from modules.cleanup import _windows_handle
        from modules.protected_files import rename_same_parent
        with _windows_handle(source, delete=True) as (_, handle, info):
            if info.links != 1 or info.attributes & 0x10:
                raise OSError("Unsafe rotation source")
            rename_same_parent(handle, target)


class _LogFile(RotatingFileHandler):
    def _open(self):
        return open_regular(self.baseFilename, "a", encoding=self.encoding, errors=self.errors)

    def doRollover(self):
        if self.stream is not None:
            self.stream.close()
            self.stream = None
        base = Path(self.baseFilename)
        for number in range(self.backupCount, 0, -1):
            source = base if number == 1 else base.with_name(f"{base.name}.{number - 1}")
            try:
                replace_sibling(source, f"{base.name}.{number}")
            except FileNotFoundError:
                pass

    def emit(self, record):
        # Windows cannot rename a log held open by a second Panacea instance.
        try:
            folder = Path(self.baseFilename).parent
            with storage_lock(folder.parent), directory(folder):
                try:
                    super().emit(record)
                finally:
                    if self.stream is not None:
                        self.stream.close()
                        self.stream = None
        except Exception:
            self.handleError(record)


class Logger:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                instance = super().__new__(cls)
                instance._initialize()
                cls._instance = instance
        return cls._instance

    def _initialize(self):
        self.logger = logging.getLogger("PanaceaLogger")
        if self.logger.handlers:
            return
        self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        try:
            folder = data_directory() / "logs"
            with storage_lock(folder.parent), directory(folder, create=True):
                handler = _LogFile(folder / "panacea.log", maxBytes=1024 * 1024, backupCount=5,
                                   encoding="utf-8", delay=True)
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        except OSError:
            pass
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        self.logger.addHandler(console)

    def log(self, message, level="INFO"):
        self.logger.log({"WARNING": logging.WARNING, "ERROR": logging.ERROR}.get(level.upper(), logging.INFO), message)
