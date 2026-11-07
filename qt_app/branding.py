"""Stable and QA windows have separate Windows taskbar identities."""
from pathlib import Path
import ctypes


def application_id(*, smoke: bool, frozen: bool, executable: str) -> str:
    if not smoke and frozen and Path(executable).name == "Panacea.exe":
        return "Panacea.Desktop"
    return "Panacea.QtQA"


def configure_windows_identity(identifier: str) -> str:
    shell = ctypes.windll.shell32
    shell.SetCurrentProcessExplicitAppUserModelID.argtypes = [ctypes.c_wchar_p]
    if shell.SetCurrentProcessExplicitAppUserModelID(identifier) != 0:
        raise OSError("Cannot set Windows application identity")
    observed = ctypes.c_wchar_p()
    shell.GetCurrentProcessExplicitAppUserModelID.argtypes = [ctypes.POINTER(ctypes.c_wchar_p)]
    if shell.GetCurrentProcessExplicitAppUserModelID(ctypes.byref(observed)) != 0:
        raise OSError("Cannot read back Windows application identity")
    try:
        if observed.value != identifier:
            raise OSError("Windows application identity mismatch")
        return observed.value
    finally:
        ctypes.windll.ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
        ctypes.windll.ole32.CoTaskMemFree(ctypes.cast(observed, ctypes.c_void_p))
