"""Small handle-bound primitives for the durable Windows Turbo snapshot."""
import ctypes
from ctypes import wintypes
from contextlib import contextmanager

from modules.cleanup import _kernel_api, _validate_handle, UnsafePath


class _UnicodeString(ctypes.Structure):
    _fields_ = [('length', wintypes.USHORT), ('maximum', wintypes.USHORT), ('buffer', wintypes.LPWSTR)]


class _ObjectAttributes(ctypes.Structure):
    _fields_ = [('length', wintypes.ULONG), ('root', wintypes.HANDLE),
                ('name', ctypes.POINTER(_UnicodeString)), ('attributes', wintypes.ULONG),
                ('security', wintypes.LPVOID), ('quality', wintypes.LPVOID)]


class _IoStatus(ctypes.Structure):
    _fields_ = [('status', ctypes.c_void_p), ('information', ctypes.c_size_t)]


def _component(name):
    if not name or name in ('.', '..') or name.endswith((' ', '.')) or any(c in name for c in '\\/\x00:'):
        raise UnsafePath('A simple file name is required')
    return name


def _native_api():
    native = ctypes.WinDLL('ntdll')
    native.RtlNtStatusToDosError.argtypes = [wintypes.LONG]
    native.RtlNtStatusToDosError.restype = wintypes.ULONG
    return native


def dispose(kernel, handle):
    disposition = wintypes.BOOL(True)
    if not kernel.SetFileInformationByHandle(handle, 4, ctypes.byref(disposition), ctypes.sizeof(disposition)):
        raise ctypes.WinError(ctypes.get_last_error())


@contextmanager
def relative_handle(parent, name, directory=False):
    """Create/open one child relative to the retained parent object, never a path.

    Files use exclusive FILE_CREATE; directories use FILE_OPEN_IF. A single
    handle owns the resulting file through payload, flush, rename or disposal.
    """
    kernel, parent_handle, parent_path = parent
    _validate_handle(kernel, parent_handle, parent_path)
    name = _component(name)
    expected = parent_path / name
    text = ctypes.create_unicode_buffer(name)
    encoded = name.encode('utf-16-le')
    string = _UnicodeString(len(encoded), len(encoded) + 2, ctypes.cast(text, wintypes.LPWSTR))
    attributes = _ObjectAttributes(ctypes.sizeof(_ObjectAttributes), parent_handle,
                                   ctypes.pointer(string), 0x1040, None, None)  # DONT_REPARSE | CASE_INSENSITIVE
    native = _native_api()
    native.NtCreateFile.argtypes = [ctypes.POINTER(wintypes.HANDLE), wintypes.ULONG,
        ctypes.POINTER(_ObjectAttributes), ctypes.POINTER(_IoStatus), wintypes.LPVOID,
        wintypes.ULONG, wintypes.ULONG, wintypes.ULONG, wintypes.ULONG, wintypes.LPVOID, wintypes.ULONG]
    native.NtCreateFile.restype = wintypes.LONG
    handle = wintypes.HANDLE()
    status_block = _IoStatus()
    access = 0x100000 | 0x10000 | 0x80 | 1 | (0 if directory else 2)
    options = 0x00200000 | 0x20 | (1 if directory else 0x40)
    status = native.NtCreateFile(ctypes.byref(handle), access, ctypes.byref(attributes),
        ctypes.byref(status_block), None, 0x80, 1, 3 if directory else 2, options, None, 0)
    if status < 0:
        raise ctypes.WinError(native.RtlNtStatusToDosError(status))
    try:
        try:
            info = _validate_handle(kernel, handle, expected)
            if bool(info.attributes & 0x10) != directory or (not directory and info.links != 1):
                raise UnsafePath('Unexpected recovery object')
        except Exception:
            if status_block.information == 2:  # FILE_CREATED; never dispose somebody else's directory.
                dispose(kernel, handle)
            raise
        yield kernel, handle, info
    finally:
        kernel.CloseHandle(handle)


def read_bytes(kernel, handle, limit):
    kernel.ReadFile.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                               ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
    buffer = ctypes.create_string_buffer(limit + 1)
    received = wintypes.DWORD()
    if not kernel.ReadFile(handle, buffer, len(buffer), ctypes.byref(received), None):
        raise ctypes.WinError(ctypes.get_last_error())
    if received.value > limit:
        raise UnsafePath('Original-state file is too large')
    return buffer.raw[:received.value]


def write_bytes(kernel, handle, payload):
    kernel.WriteFile.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                                ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
    kernel.FlushFileBuffers.argtypes = [wintypes.HANDLE]
    buffer = ctypes.create_string_buffer(payload)
    written = wintypes.DWORD()
    if not kernel.WriteFile(handle, buffer, len(payload), ctypes.byref(written), None):
        raise ctypes.WinError(ctypes.get_last_error())
    if written.value != len(payload):
        raise OSError('Incomplete original-state write')
    if not kernel.FlushFileBuffers(handle):
        raise ctypes.WinError(ctypes.get_last_error())


def rename_same_parent(handle, name):
    """Simple name and null root retain the source object's existing parent."""
    encoded = _component(name).encode('utf-16-le')
    class RenameInfo(ctypes.Structure):
        _fields_ = [('replace', wintypes.BOOL), ('root', wintypes.HANDLE),
                    ('length', wintypes.ULONG), ('name', wintypes.WCHAR * (len(encoded) // 2 + 1))]
    info = RenameInfo(True, None, len(encoded))
    ctypes.memmove(ctypes.addressof(info) + RenameInfo.name.offset, encoded, len(encoded))
    native = _native_api()
    native.NtSetInformationFile.argtypes = [wintypes.HANDLE, ctypes.POINTER(_IoStatus),
                                           wintypes.LPVOID, wintypes.ULONG, ctypes.c_int]
    native.NtSetInformationFile.restype = wintypes.LONG
    status = native.NtSetInformationFile(handle, ctypes.byref(_IoStatus()), ctypes.byref(info), ctypes.sizeof(info), 10)
    if status < 0:
        raise ctypes.WinError(native.RtlNtStatusToDosError(status))
