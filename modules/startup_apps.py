"""Inventory of Windows startup sources. Only Explorer's approval value is writable."""
from __future__ import annotations

import ctypes
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import ntpath
import os
from pathlib import Path
import re
import stat
import struct
import time
import uuid

from modules.cleanup import _guard_path, known_folder

RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"
APPROVED = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved"
SOURCES = (("user", "Run"), ("machine", "Run"), ("machine", "Run32"),
           ("user", "StartupFolder"), ("machine", "StartupFolder"))
_EPOCH = datetime(1601, 1, 1, tzinfo=timezone.utc)


def stable_id(scope, location, name):
    identity = "\0".join((scope, location, name))
    return hashlib.sha256(identity.encode("utf-8", "surrogatepass")).hexdigest()


def approval_state(raw):
    if raw is None:  # No Explorer override: the startup source is enabled by default.
        return True, None
    if not isinstance(raw, bytes) or len(raw) != 12:
        return None, None
    state, ticks = struct.unpack("<IQ", raw)
    try:
        changed = (_EPOCH + timedelta(microseconds=ticks // 10)).isoformat() if ticks else None
    except OverflowError:
        changed = None
    return {2: True, 6: True, 3: False}.get(state), changed


def _shortcut(path):
    """Read IShellLinkW via IPersistFile. Never call Resolve, Save or execute the link."""
    ole = ctypes.windll.ole32
    ptr = ctypes.c_void_p
    initialized = ole.CoInitializeEx(None, 2)
    if initialized < 0 and initialized != -2147417850:  # RPC_E_CHANGED_MODE
        return "", ""
    link, persistent = ptr(), ptr()

    def guid(value):
        return ctypes.create_string_buffer(uuid.UUID(value).bytes_le)

    def method(obj, index, *args):
        table = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ptr))).contents
        return ctypes.WINFUNCTYPE(ctypes.c_long, ptr, *args)(table[index])

    try:
        if ole.CoCreateInstance(guid("00021401-0000-0000-C000-000000000046"), None, 1,
                                guid("000214F9-0000-0000-C000-000000000046"), ctypes.byref(link)) < 0:
            return "", ""
        if method(link, 0, ptr, ctypes.POINTER(ptr))(
                link, guid("0000010B-0000-0000-C000-000000000046"), ctypes.byref(persistent)) < 0:
            return "", ""
        if method(persistent, 5, ctypes.c_wchar_p, ctypes.c_uint)(persistent, str(path), 0) < 0:
            return "", ""
        target, args = ctypes.create_unicode_buffer(32768), ctypes.create_unicode_buffer(32768)
        if method(link, 3, ptr, ctypes.c_int, ptr, ctypes.c_uint)(link, target, len(target), None, 4) < 0:
            return "", ""
        method(link, 10, ptr, ctypes.c_int)(link, args, len(args))
        return target.value, args.value
    finally:
        for obj in (persistent, link):
            if obj:
                method(obj, 2)(obj)
        if initialized >= 0:
            ole.CoUninitialize()


def _executable(command):
    expanded = os.path.expandvars(command.strip())
    match = re.match(r'^"([^"]+)"|^([^\s"]+)', expanded)
    if not match:
        return ""
    path = match.group(1) or match.group(2)
    if match.group(2) and re.match(r"^[A-Za-z]:[\\/]", path):
        # CreateProcess tries successively longer prefixes of an unquoted path.
        for prefix in re.finditer(r"\S+(?=\s|$)", expanded):
            candidate = expanded[:prefix.end()]
            extension = ntpath.splitext(candidate)[1]
            candidate = candidate if extension else candidate + ".exe"
            if _image_identity(candidate):
                return candidate
            if extension.lower() == ".exe":
                break
    if not ntpath.dirname(path) and re.fullmatch(r"[\w.-]+\.exe", path, re.I):
        from modules.commands import system_executable
        path = ntpath.join(ntpath.dirname(system_executable("cmd.exe")), path)
    return path


def _image_identity(path):
    if not re.match(r"^[A-Za-z]:[\\/]", path) or ctypes.windll.kernel32.GetDriveTypeW(path[:2] + "\\") != 3:
        return None
    try:
        with _guard_path(Path(path).parent):
            info = os.lstat(path)
            if stat.S_ISREG(info.st_mode) and not info.st_file_attributes & 0x400:
                return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns
    except OSError:
        pass
    return None


def _version_strings(path):
    """Read CompanyName/FileDescription from a local PE version resource as data."""
    if not _image_identity(path):
        return "", ""
    version = ctypes.windll.version
    size = version.GetFileVersionInfoSizeW(path, None)
    if not 0 < size <= 4 * 1024 * 1024:
        return "", ""
    data = ctypes.create_string_buffer(size)
    if not version.GetFileVersionInfoW(path, 0, size, data):
        return "", ""

    def query(key):
        value, length = ctypes.c_void_p(), ctypes.c_uint()
        if version.VerQueryValueW(data, key, ctypes.byref(value), ctypes.byref(length)):
            return value.value, length.value
        return None, 0

    address, length = query(r"\VarFileInfo\Translation")
    if address and length >= 4:
        for lang, page in struct.iter_unpack("<HH", ctypes.string_at(address, length - length % 4)):
            prefix = f"\\StringFileInfo\\{lang:04x}{page:04x}\\"
            fields = []
            for key in ("CompanyName", "FileDescription"):
                address, count = query(prefix + key)
                fields.append(ctypes.wstring_at(address, count).rstrip("\0") if address and count else "")
            if any(fields):
                return tuple(fields)
    return "", ""


@dataclass(frozen=True)
class Entry:
    scope: str
    location: str
    name: str
    command: str
    executable: str
    identity: tuple

    @property
    def id(self):
        return stable_id(self.scope, self.location, self.name)


class WindowsStartup:
    def entries(self, scope, location):
        import winreg
        if location == "StartupFolder":
            folder = known_folder("startup" if scope == "user" else "common_startup")
            with _guard_path(folder), os.scandir(folder) as entries:
                for item in entries:
                    try:
                        info = os.lstat(item.path)
                        if (not stat.S_ISREG(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400
                                or item.name.casefold() == "desktop.ini"):
                            continue
                        path = Path(item.path)
                        target, args = _shortcut(path) if path.suffix.lower() == ".lnk" else (str(path), "")
                        command = ('"' + target + '" ' + args).rstrip() if target else str(path)
                        yield Entry(scope, location, item.name, command, os.path.expandvars(target),
                                    (str(path), info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns))
                    except FileNotFoundError:
                        continue
            return
        hive = winreg.HKEY_CURRENT_USER if scope == "user" else winreg.HKEY_LOCAL_MACHINE
        view = winreg.KEY_WOW64_32KEY if location == "Run32" else winreg.KEY_WOW64_64KEY
        with winreg.OpenKey(hive, RUN, 0, winreg.KEY_QUERY_VALUE | view) as key:
            for index in range(winreg.QueryInfoKey(key)[1]):
                name, value, kind = winreg.EnumValue(key, index)
                if name and kind in (winreg.REG_SZ, winreg.REG_EXPAND_SZ) and isinstance(value, str):
                    yield Entry(scope, location, name, value, _executable(value), (kind,))

    def approval(self, entry, data=None):
        import winreg
        hive = winreg.HKEY_CURRENT_USER if entry.scope == "user" else winreg.HKEY_LOCAL_MACHINE
        path = APPROVED + "\\" + entry.location
        access = winreg.KEY_WOW64_64KEY | winreg.KEY_QUERY_VALUE
        if data is not None:
            with winreg.CreateKeyEx(hive, path, 0, access | winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, entry.name, 0, winreg.REG_BINARY, data)
                return winreg.QueryValueEx(key, entry.name)[0]
        try:
            with winreg.OpenKey(hive, path, 0, access) as key:
                value, kind = winreg.QueryValueEx(key, entry.name)
                return value if kind == winreg.REG_BINARY else b""
        except FileNotFoundError:
            return None

    version = staticmethod(_version_strings)
    image_identity = staticmethod(_image_identity)


@dataclass(frozen=True)
class StartupTarget:
    entry: Entry
    approval: bytes | None
    image_identity: tuple | None

    @property
    def label(self):
        return f"{self.entry.name} ({self.entry.scope}/{self.entry.location}) — {self.entry.command}"


class StartupApps:
    def __init__(self, backend=None):
        self.backend = backend or WindowsStartup()

    def _entries(self, issues):
        for scope, location in SOURCES:
            try:
                yield from self.backend.entries(scope, location)
            except FileNotFoundError:
                continue
            except (ImportError, OSError) as exc:
                issues.append({"scope": scope, "location": location, "error": type(exc).__name__})

    def inventory(self):
        rows, issues = [], []
        for item in self._entries(issues):
            try:
                raw = self.backend.approval(item)
            except OSError:
                raw = b""
            enabled, changed = approval_state(raw)
            try:
                publisher, description = self.backend.version(item.executable) if item.executable else ("", "")
            except OSError:
                publisher, description = "", ""
            rows.append({"id": item.id, "name": item.name, "display_name": item.name,
                         "command": item.command, "publisher": publisher, "description": description,
                         "scope": item.scope, "location": item.location, "enabled": enabled,
                         "last_changed": changed})
        rows.sort(key=lambda row: (row["name"].casefold(), row["id"]))
        return {"apps": rows, "issues": issues}

    def target(self, action, identifier):
        if not isinstance(identifier, str) or not re.fullmatch("[a-f0-9]{64}", identifier):
            raise ValueError("Select a startup app")
        for entry in self._entries([]):
            if entry.id == identifier:
                raw = self.backend.approval(entry)
                enabled, _ = approval_state(raw)
                if enabled is (action == "startup_disable"):
                    return StartupTarget(entry, raw, self.backend.image_identity(entry.executable))
                break
        raise ValueError("Startup app disappeared, changed state or could not be verified")

    def apply(self, action, target):
        enabled = action == "startup_enable"
        ticks = 0 if enabled else time.time_ns() // 100 + 116444736000000000
        data = struct.pack("<IQ", 2 if enabled else 3, ticks)
        if self.backend.approval(target.entry, data) != data:
            raise OSError("Explorer startup approval could not be verified")
        return True, "Startup approval verified."
