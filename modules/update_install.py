"""Verified replacement with rollback and an explicit startup acknowledgment.

``install_verified`` is a filesystem primitive, not an authentication boundary:
its caller must obtain the digest from the configured GitHub repository. The
frozen helper below re-fetches that digest itself and requires protected Windows
directories before launching anything with its elevated token.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys
import threading
import time

from modules.updater import (CHUNK_SIZE, MAX_ASSET_SIZE, Release, UpdateClient, UpdateError,
                             UpdateVerificationError, _assert_plain_path,
                             verify_file, verify_stream)


@dataclass(frozen=True)
class InstallResult:
    success: bool
    backup: Path | None = None
    error: str | None = None
    rolled_back: bool = False
    readiness_token: str | None = None
    process: object = field(default=None, repr=False, compare=False)


def readiness_path(target: str | Path) -> Path:
    target = Path(target)
    return target.with_name(target.name + ".update-ready.json")


def _digest(path: Path) -> str:
    with path.open("rb") as stream:
        digest = hashlib.sha256()
        while chunk := stream.read(CHUNK_SIZE):
            digest.update(chunk)
        return digest.hexdigest()


def _read_json(path: Path) -> dict:
    _assert_plain_path(path)
    with path.open("rb") as stream:
        data = stream.read(65537)
    if len(data) > 65536:
        raise UpdateVerificationError("Update state is too large.")
    state = json.loads(data)
    if not isinstance(state, dict):
        raise UpdateVerificationError("Update state is malformed.")
    return state


def _write_json(path: Path, data: dict, *, exclusive=False, protected=False):
    _assert_plain_path(path)
    temporary = path.with_name(path.name + f".{secrets.token_hex(16)}.tmp") if protected and not exclusive else path
    try:
        context = _open_exclusive(temporary, protected) if exclusive or protected else path.open("wb")
        with context as stream:
            stream.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        if temporary != path:
            os.replace(temporary, path)
    finally:
        if temporary != path:
            temporary.unlink(missing_ok=True)


def _copy_verified(source: Path, destination: Path, expected: str, *, protected=False) -> None:
    _assert_plain_path(source)
    before = source.lstat()
    created = False
    try:
        with source.open("rb") as stream:
            opened = os.fstat(stream.fileno())
            if (not stat.S_ISREG(opened.st_mode)
                    or (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino)):
                raise UpdateVerificationError("Staged executable changed while it was opened.")
            output = _open_exclusive(destination, protected)
            created = True
            with output:
                count = 0
                while chunk := stream.read(CHUNK_SIZE):
                    count += len(chunk)
                    if count > MAX_ASSET_SIZE:
                        raise UpdateVerificationError("Staged executable exceeds the update size limit.")
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
                # Verify the exact bytes to be installed, not a prior path lookup.
                verify_stream(output, expected)
    except Exception:
        if created:
            destination.unlink(missing_ok=True)
        raise


def _rollback(target: Path, backup: Path, marker: Path) -> bool:
    try:
        _assert_plain_path(target)
        _assert_plain_path(backup)
        os.replace(backup, target)
        marker.unlink(missing_ok=True)
        return True
    except (OSError, UpdateError):
        return False


_INSTALL_LOCK = threading.RLock()


@contextmanager
def _transaction_guard(target: Path, protected=False):
    """Serialize marker read/validate/delete and replacement across helpers."""
    with _INSTALL_LOCK:
        if not protected:
            yield
            return
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        create = kernel.CreateMutexW
        create.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        create.restype = wintypes.HANDLE
        wait = kernel.WaitForSingleObject
        wait.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        wait.restype = wintypes.DWORD
        release = kernel.ReleaseMutex
        release.argtypes = [wintypes.HANDLE]
        release.restype = wintypes.BOOL
        close = kernel.CloseHandle
        close.argtypes = [wintypes.HANDLE]
        close.restype = wintypes.BOOL
        identity = hashlib.sha256(os.path.normcase(os.path.abspath(target)).encode("utf-8")).hexdigest()
        handle = create(None, False, "Global\\PanaceaUpdater." + identity)
        if not handle:
            raise UpdateVerificationError("Cannot acquire the updater transaction guard; retry later.")
        acquired = False
        try:
            # An abandoned owner releases the mutex; the validated marker still
            # decides whether recovery is safe. No pending backup is swept.
            if wait(handle, 5000) not in (0, 0x80):
                raise UpdateVerificationError("Another updater transaction is active; retry later.")
            acquired = True
            yield
        finally:
            if acquired:
                release(handle)
            close(handle)


def _validated_marker(target: Path, *, token=None, protected=False, require_ready=True) -> tuple[dict, Path]:
    marker = readiness_path(target)
    state = _read_json(marker)
    actual_token = state.get("token")
    if (not isinstance(actual_token, str) or not re.fullmatch(r"[0-9a-f]{64}", actual_token)
            or token is not None and token != actual_token):
        raise UpdateVerificationError("Readiness marker does not match the recorded operation token.")
    backup = target.with_name(f".{target.name}.{actual_token}.backup")
    if (target.name != "Panacea.exe" or state.get("target") != str(target)
            or state.get("backup") != str(backup) or type(state.get("protected")) is not bool
            or protected and state["protected"] is not True
            or require_ready and state.get("ready") is not True):
        raise UpdateVerificationError("Readiness marker is not a completed update for this executable.")
    if state["protected"]:
        _assert_admin_directory(target.parent)
        for path in (target, marker, backup):
            if path.exists():
                _assert_admin_file(path)
    if not isinstance(state.get("backup_sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", state["backup_sha256"]):
        raise UpdateVerificationError("Readiness backup checksum is invalid.")
    verify_file(target, state["sha256"])
    _assert_plain_path(backup)
    if backup.exists():
        verify_file(backup, state["backup_sha256"])
    elif state.get("ready") is not True:
        raise UpdateVerificationError("An unacknowledged update is missing its recovery backup.")
    return state, backup


def _finalize_ready_locked(target: Path, *, token=None, protected=False) -> bool:
    marker = readiness_path(target)
    if not marker.exists():
        return True
    _, backup = _validated_marker(target, token=token, protected=protected)
    try:
        # This is the exact operation-owned path, never a directory sweep.
        backup.unlink(missing_ok=True)
        marker.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def finalize_ready(target: str | Path, *, token=None, protected=False) -> bool:
    """Idempotently finish validated acknowledged state; preserve all other state."""
    target = Path(os.path.abspath(target))
    try:
        if not protected and readiness_path(target).exists():
            protected = _read_json(readiness_path(target)).get("protected") is True
        with _transaction_guard(target, protected):
            return _finalize_ready_locked(target, token=token, protected=protected)
    except (OSError, ValueError, KeyError, UpdateError):
        return False


def install_verified(staged: str | Path, target: str | Path, expected_sha256: str,
                     launch, *, protected=False) -> InstallResult:
    """Replace a verified executable; ``launch(path, token)`` returns a process.

    A successful return means launch was accepted, not startup readiness. The
    backup remains until ``acknowledge_ready`` verifies the installed bytes.
    Never close the current UI merely because this function returned success.
    """
    target = Path(os.path.abspath(target))
    try:
        with _transaction_guard(target, protected):
            return _install_verified_locked(staged, target, expected_sha256, launch, protected=protected)
    except Exception as exc:
        return InstallResult(False, error=str(exc) or type(exc).__name__)


def _install_verified_locked(staged, target, expected_sha256, launch, *, protected=False) -> InstallResult:
    staged, target = Path(os.path.abspath(staged)), Path(os.path.abspath(target))
    token = secrets.token_hex(32)
    backup = target.with_name(f".{target.name}.{token}.backup")
    candidate = target.with_name(f".{target.name}.{token}.candidate")
    marker = readiness_path(target)
    renamed = False
    marker_created = False
    candidate_created = False
    backup_reserved = False
    try:
        if target.name != "Panacea.exe" or staged == target:
            raise UpdateVerificationError("Installer target must be the current Panacea.exe.")
        for path in (target, staged, target.parent, marker, backup, candidate):
            _assert_plain_path(path)
        if marker.exists() and not _finalize_ready_locked(target, protected=protected):
            raise UpdateVerificationError("Previous readiness cleanup is still locked; keep its backup and retry later.")
        if not target.is_file():
            raise UpdateVerificationError("The current executable does not exist.")
        if candidate.exists() or backup.exists():
            raise UpdateVerificationError("A generated update path already exists; no existing files were overwritten.")
        old_digest = _digest(target)
        _copy_verified(staged, candidate, expected_sha256, protected=protected)
        candidate_created = True
        with _open_exclusive(backup, protected):
            pass
        backup_reserved = True
        _write_json(marker, {"token": token, "target": str(target), "backup": str(backup),
                            "sha256": expected_sha256.lower(), "backup_sha256": old_digest,
                            "protected": protected}, exclusive=True, protected=protected)
        marker_created = True
        os.replace(target, backup)
        renamed = True
        os.replace(candidate, target)
        verify_file(target, expected_sha256)
        process = launch(target, token)
        if process is not None and process.poll() is not None:
            raise UpdateVerificationError("The new application exited before it acknowledged readiness.")
        return InstallResult(True, backup, readiness_token=token, process=process)
    except Exception as exc:
        restored = _rollback(target, backup, marker) if renamed else False
        if not renamed and marker_created:
            marker.unlink(missing_ok=True)
        if not renamed and backup_reserved:
            backup.unlink(missing_ok=True)
        message = str(exc) or type(exc).__name__
        if renamed and not restored:
            message += f" Rollback could not complete; recover the old executable from {backup}."
        return InstallResult(False, backup if renamed and backup.exists() else None, message, restored)
    finally:
        if candidate_created:
            candidate.unlink(missing_ok=True)


def acknowledge_ready(target: str | Path, token: str) -> bool:
    """Called by the new application only after its startup has completed."""
    target = Path(os.path.abspath(target))
    marker = readiness_path(target)
    try:
        if not isinstance(token, str) or not re.fullmatch(r"[0-9a-f]{64}", token):
            return False
        protected = _read_json(marker).get("protected") is True
        with _transaction_guard(target, protected):
            state, _ = _validated_marker(target, token=token, protected=protected, require_ready=False)
            state["ready"] = True
            _write_json(marker, state, protected=protected)
            # Startup succeeded even if housekeeping is locked. The helper or
            # next install retries only this authenticated completed record.
            _finalize_ready_locked(target, token=token, protected=protected)
        return True
    except (OSError, ValueError, KeyError, UpdateError):
        return False


_WRITE_MASK = 0x10000000 | 0x40000000 | 0x000D0156
_ANCESTOR_WRITE_MASK = 0x10000000 | 0x40000000 | 0x000C0040
_TRUSTED_SIDS = {"BA", "SY", "S-1-5-18", "S-1-5-32-544"}
_SDDL_RIGHTS = {
    "FA": 0x001F01FF, "FR": 0x00120089, "FW": 0x00120116, "FX": 0x001200A0,
    "GA": 0x10000000, "GR": 0x80000000, "GW": 0x40000000, "GX": 0x20000000,
    "RC": 0x00020000, "SD": 0x00010000, "WD": 0x00040000, "WO": 0x00080000,
    "CC": 1, "DC": 2, "LC": 4, "SW": 8, "RP": 16, "WP": 32,
    "DT": 64, "LO": 128, "CR": 256,
}


def _protected_sddl(sddl: str, *, ancestor=False, trusted_service_sid=None) -> bool:
    """Conservative ACL check: only administrators/SYSTEM may write or own it."""
    trusted = _TRUSTED_SIDS | ({trusted_service_sid} if trusted_service_sid else set())
    owner = re.search(r"O:(.*?)(?=[GDS]:|$)", sddl)
    dacl = re.search(r"D:(.*?)(?=S:|$)", sddl)
    if not owner or owner.group(1) not in trusted or not dacl or "NO_ACCESS_CONTROL" in dacl.group(1):
        return False
    entries = re.findall(r"\(([^()]*)\)", dacl.group(1))
    if not entries:
        return False
    for entry in entries:
        fields = entry.split(";")
        if len(fields) != 6:
            return False
        kind, flags, rights, _, _, sid = fields
        if "IO" in flags or kind == "D":
            continue
        if kind != "A":
            return False
        if sid in trusted:
            continue
        try:
            if rights.startswith("0x"):
                mask = int(rights, 16)
            else:
                if len(rights) % 2:
                    return False
                mask = 0
                for index in range(0, len(rights), 2):
                    mask |= _SDDL_RIGHTS[rights[index:index + 2]]
        except (ValueError, KeyError):
            return False
        if mask & (_ANCESTOR_WRITE_MASK if ancestor else _WRITE_MASK):
            return False
    return True


def _windows_security(path: Path) -> tuple[str, str | None]:
    """Read owner/DACL through Win32; never infer protection from a path name."""
    import ctypes
    from ctypes import wintypes
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    pointer = ctypes.c_void_p
    get_security = advapi.GetNamedSecurityInfoW
    get_security.argtypes = [wintypes.LPWSTR, ctypes.c_int, wintypes.DWORD,
                            ctypes.POINTER(pointer), ctypes.POINTER(pointer),
                            ctypes.POINTER(pointer), ctypes.POINTER(pointer), ctypes.POINTER(pointer)]
    get_security.restype = wintypes.DWORD
    convert = advapi.ConvertSecurityDescriptorToStringSecurityDescriptorW
    convert.argtypes = [pointer, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(wintypes.LPWSTR), ctypes.POINTER(wintypes.DWORD)]
    convert.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [pointer]
    kernel.LocalFree.restype = pointer
    descriptor = pointer()
    if get_security(str(path), 1, 5, None, None, None, None, ctypes.byref(descriptor)):
        raise UpdateVerificationError("Cannot verify update directory permissions.")
    sddl = wintypes.LPWSTR()
    try:
        if not convert(descriptor, 1, 5, ctypes.byref(sddl), None):
            raise UpdateVerificationError("Cannot read update directory permissions.")
        text = sddl.value
    finally:
        if sddl:
            kernel.LocalFree(ctypes.cast(sddl, pointer))
        kernel.LocalFree(descriptor)

    # Program Files may be owned by the Windows TrustedInstaller service.
    service_sid = None
    lookup = advapi.LookupAccountNameW
    lookup.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, pointer, ctypes.POINTER(wintypes.DWORD),
                       wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD)]
    lookup.restype = wintypes.BOOL
    sid_size, domain_size, use = wintypes.DWORD(), wintypes.DWORD(), wintypes.DWORD()
    lookup(None, "NT SERVICE\\TrustedInstaller", None, ctypes.byref(sid_size), None, ctypes.byref(domain_size), ctypes.byref(use))
    if sid_size.value:
        sid = ctypes.create_string_buffer(sid_size.value)
        domain = ctypes.create_unicode_buffer(domain_size.value or 1)
        if lookup(None, "NT SERVICE\\TrustedInstaller", sid, ctypes.byref(sid_size), domain,
                  ctypes.byref(domain_size), ctypes.byref(use)):
            convert_sid = advapi.ConvertSidToStringSidW
            convert_sid.argtypes = [pointer, ctypes.POINTER(wintypes.LPWSTR)]
            convert_sid.restype = wintypes.BOOL
            sid_text = wintypes.LPWSTR()
            if convert_sid(sid, ctypes.byref(sid_text)):
                service_sid = sid_text.value
                kernel.LocalFree(ctypes.cast(sid_text, pointer))
    return text, service_sid


def _assert_admin_directory(directory: Path) -> None:
    if os.name != "nt":
        raise UpdateVerificationError("Automatic executable updates require Windows.")
    _assert_plain_path(directory)
    for index, path in enumerate((directory, *directory.parents)):
        sddl, service_sid = _windows_security(path)
        if not _protected_sddl(sddl, ancestor=index > 0, trusted_service_sid=service_sid):
            raise UpdateVerificationError(
                "Automatic elevated updates require an administrator-protected installation directory. "
                "Download the verified release manually for this installation.")


def _assert_admin_file(path: Path):
    _assert_plain_path(path)
    sddl, service_sid = _windows_security(path)
    if not _protected_sddl(sddl, trusted_service_sid=service_sid):
        raise UpdateVerificationError("The installed executable must be owned and writable only by administrators.")


def _open_exclusive(path: Path, protected=False):
    if not protected:
        return path.open("xb+")
    import ctypes
    from ctypes import wintypes
    import msvcrt
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    pointer = ctypes.c_void_p

    class SecurityAttributes(ctypes.Structure):
        _fields_ = [("length", wintypes.DWORD), ("descriptor", pointer), ("inherit", wintypes.BOOL)]

    convert = advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW
    convert.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(pointer), ctypes.POINTER(wintypes.DWORD)]
    convert.restype = wintypes.BOOL
    create = kernel.CreateFileW
    create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(SecurityAttributes),
                       wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    create.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.LocalFree.argtypes = [pointer]
    kernel.LocalFree.restype = pointer
    descriptor = pointer()
    if not convert("O:BAG:BAD:P(A;;FA;;;SY)(A;;FA;;;BA)", 1, ctypes.byref(descriptor), None):
        raise UpdateVerificationError("Cannot create protected executable permissions.")
    attributes = SecurityAttributes(ctypes.sizeof(SecurityAttributes), descriptor, False)
    try:
        # CREATE_NEW, read/write, no sharing: owner/DACL are set at creation.
        handle = create(str(path), 0xC0000000, 0, ctypes.byref(attributes), 1, 0x80, None)
    finally:
        kernel.LocalFree(descriptor)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        descriptor_number = msvcrt.open_osfhandle(handle, os.O_RDWR | os.O_BINARY)
    except Exception:
        kernel.CloseHandle(handle)
        raise
    return os.fdopen(descriptor_number, "w+b")


@dataclass
class SelfUpdateJob:
    workspace: Path
    process: object

    def poll(self) -> dict:
        try:
            state = _read_json(self.workspace / "status.json")
        except (OSError, ValueError, UpdateError):
            state = {"status": "preparing", "message": "Verifying the release in the trusted helper."}
        if state.get("status") not in {"preparing", "installing", "waiting_ready", "ready", "failed"}:
            state = {"status": "failed", "message": "Updater returned invalid status."}
        if state["status"] not in {"ready", "failed"} and self.process.poll() is not None:
            state = {"status": "failed", "message": "Updater exited before the new application was ready."}
        return state


def _create_admin_workspace(parent: Path) -> Path:
    """Create an Administrators-owned directory with a protected inherited ACL."""
    import ctypes
    from ctypes import wintypes
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    pointer = ctypes.c_void_p

    class SecurityAttributes(ctypes.Structure):
        _fields_ = [("length", wintypes.DWORD), ("descriptor", pointer), ("inherit", wintypes.BOOL)]

    convert = advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW
    convert.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(pointer), ctypes.POINTER(wintypes.DWORD)]
    convert.restype = wintypes.BOOL
    create = kernel.CreateDirectoryW
    create.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(SecurityAttributes)]
    create.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [pointer]
    kernel.LocalFree.restype = pointer
    descriptor = pointer()
    if not convert("O:BAG:BAD:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)", 1, ctypes.byref(descriptor), None):
        raise UpdateVerificationError("Cannot create protected update permissions.")
    workspace = parent / f"panacea-update-{secrets.token_hex(16)}"
    attributes = SecurityAttributes(ctypes.sizeof(SecurityAttributes), descriptor, False)
    try:
        if not create(str(workspace), ctypes.byref(attributes)):
            raise UpdateVerificationError("Cannot create an administrator-protected update workspace.")
    finally:
        kernel.LocalFree(descriptor)
    return workspace


def start_self_update(staged: str | Path, target: str | Path, release: Release,
                      client: UpdateClient, *, popen=None) -> SelfUpdateJob:
    """Start a copy of the current trusted image; the old UI remains open."""
    target = Path(os.path.abspath(target))
    if (not getattr(sys, "frozen", False) or target != Path(os.path.abspath(sys.executable))
            or target.name != "Panacea.exe"):
        raise UpdateVerificationError("Source execution opens the verified release page for manual installation.")
    _assert_admin_directory(target.parent)
    _assert_admin_file(target)
    digest = client.fetch_checksum(release)
    verify_file(staged, digest, release.size)
    workspace = _create_admin_workspace(target.parent)
    _assert_admin_directory(workspace)
    helper = workspace / "Panacea-updater.exe"
    # The helper is the currently installed image, never the newly downloaded image.
    _copy_verified(target, helper, _digest(target), protected=True)
    _copy_verified(Path(staged), workspace / "staged.exe", digest, protected=True)
    _write_json(workspace / "job.json", {"target": str(target), "version": release.version}, exclusive=True, protected=True)
    helper_environment = os.environ.copy()
    helper_environment["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    process = (popen or subprocess.Popen)(
        [str(helper), "--panacea-update-helper", str(workspace)],
        shell=False, cwd=str(workspace), env=helper_environment,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return SelfUpdateJob(workspace, process)


def _assert_helper_context(workspace: Path):
    if (not getattr(sys, "frozen", False)
            or not re.fullmatch(r"panacea-update-[0-9a-f]{32}", workspace.name)
            or Path(os.path.abspath(sys.executable)) != workspace / "Panacea-updater.exe"):
        raise UpdateVerificationError("Update helper must run from its prepared protected workspace.")
    _assert_admin_directory(workspace)
    _assert_admin_file(workspace / "Panacea-updater.exe")


def _write_status(workspace: Path, status: str, message: str):
    temporary = workspace / "status.pending.json"
    _write_json(temporary, {"status": status, "message": message}, protected=True)
    os.replace(temporary, workspace / "status.json")


def _operation_ready(target: Path, result: InstallResult, digest: str, size: int) -> bool:
    """Read/finalize only this helper's operation, even if another one starts."""
    marker = readiness_path(target)
    with _transaction_guard(target, True):
        if not result.backup.exists():
            # Backup deletion occurs only after durable verified acknowledgment.
            # A different marker can now belong to a subsequent installation;
            # never wait on, remove, or terminate that operation's process.
            if marker.exists():
                state = _read_json(marker)
                if state.get("token") == result.readiness_token:
                    _validated_marker(target, token=result.readiness_token, protected=True)
                    _finalize_ready_locked(target, token=result.readiness_token, protected=True)
            return True
        state = _read_json(marker)
        if (state.get("token") != result.readiness_token or state.get("target") != str(target)
                or state.get("backup") != str(result.backup) or state.get("sha256") != digest
                or state.get("protected") is not True):
            raise UpdateVerificationError("Updater operation state changed; preserve the recovery backup.")
        if state.get("ready") is not True:
            return False
        _validated_marker(target, token=result.readiness_token, protected=True)
        verify_file(target, digest, size)
        # Cleanup may remain locked while the original application is open.
        # Its durable acknowledgment permits scoped recovery on the next update.
        _finalize_ready_locked(target, token=result.readiness_token, protected=True)
        return True


def run_update_helper(workspace: str | Path, *, client_factory=None, popen=None,
                      timeout=30.0, monotonic=time.monotonic, sleep=time.sleep) -> int:
    """main.py dispatches this frozen-only mode before loading Tk or UAC."""
    from version import GITHUB_REPO, VERSION
    workspace = Path(os.path.abspath(workspace))
    context_valid = False
    result = None
    target = None
    try:
        _assert_helper_context(workspace)
        context_valid = True
        _write_status(workspace, "preparing", "Checking the authoritative GitHub release and checksum.")
        state = _read_json(workspace / "job.json")
        target = Path(state["target"])
        if target.name != "Panacea.exe" or target.parent != workspace.parent:
            raise UpdateVerificationError("Prepared target is outside the helper's installation directory.")
        _assert_admin_directory(target.parent)
        _assert_admin_file(target)
        client = (client_factory or UpdateClient)(GITHUB_REPO, VERSION)
        release = client.check()
        if release is None or release.version != state.get("version"):
            raise UpdateVerificationError("The authoritative release changed. Check again before installing.")
        digest = client.fetch_checksum(release)
        staged = workspace / "staged.exe"
        verify_file(staged, digest, release.size)
        _write_status(workspace, "installing", "Replacing the verified executable; the old app remains available.")

        def launch(path, token):
            restart_environment = os.environ.copy()
            restart_environment["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
            return (popen or subprocess.Popen)([str(path), "--panacea-update-ready", token],
                                                shell=False, cwd=str(path.parent), env=restart_environment)

        result = install_verified(staged, target, digest, launch, protected=True)
        if not result.success:
            raise UpdateVerificationError(result.error)
        _write_status(workspace, "waiting_ready", "Waiting for the new application's startup acknowledgment.")
        deadline = monotonic() + timeout
        while not _operation_ready(target, result, digest, release.size):
            if result.process.poll() is not None:
                raise UpdateVerificationError("The new application exited before startup readiness.")
            if monotonic() >= deadline:
                with _transaction_guard(target, True):
                    pending, _ = _validated_marker(target, token=result.readiness_token,
                                                   protected=True, require_ready=False)
                    if pending.get("ready") is True:
                        _finalize_ready_locked(target, token=result.readiness_token, protected=True)
                        break
                    if pending.get("sha256") != digest:
                        raise UpdateVerificationError("Updater operation changed before its readiness deadline.")
                    result.process.terminate()
                    result.process.wait(timeout=5)
                raise UpdateVerificationError("The new application did not acknowledge startup readiness in time.")
            sleep(0.1)
        _write_status(workspace, "ready", "The verified new application is ready.")
        return 0
    except Exception as exc:
        message = str(exc) or type(exc).__name__
        if result and result.success and result.backup and result.backup.exists():
            try:
                with _transaction_guard(target, True):
                    pending, recorded_backup = _validated_marker(target, token=result.readiness_token,
                                                                 protected=True, require_ready=False)
                    if recorded_backup != result.backup or pending.get("sha256") != digest:
                        raise UpdateVerificationError("Recovery state belongs to another operation.")
                    if pending.get("ready") is True or result.process.poll() is None:
                        message += " Startup was acknowledged or the new process is still running; the backup was retained."
                    elif _rollback(target, result.backup, readiness_path(target)):
                        message += " The old executable was restored; the original application remains open."
                    else:
                        message += f" Recover the old executable from {result.backup}."
            except (OSError, ValueError, KeyError, UpdateError):
                message += f" Recovery state changed; the backup was preserved at {result.backup}."
        if context_valid:
            try:
                _write_status(workspace, "failed", message)
            except OSError:
                pass
        return 1
