"""Known Windows maintenance operations, launched without a command shell."""
import codecs
import ctypes
import math
import os
import re
import subprocess
import time
from modules.logger import Logger
from modules.utils import decode_console_bytes


def system_executable(name):
    """Resolve a Windows executable outside the current directory/PATH."""
    if not re.fullmatch(r'[a-zA-Z0-9]+\.exe', name):
        raise ValueError('Invalid system executable')
    if os.name == 'nt':
        buffer = ctypes.create_unicode_buffer(32768)
        if not ctypes.windll.kernel32.GetSystemDirectoryW(buffer, len(buffer)):
            raise OSError('Cannot resolve the Windows system directory')
        if name.lower() == 'powershell.exe':
            return os.path.join(buffer.value, 'WindowsPowerShell', 'v1.0', name)
        return os.path.join(buffer.value, name)
    return name


def validate_drive(drive):
    if not isinstance(drive, str) or not re.fullmatch(r'[A-Za-z]:', drive):
        raise ValueError('Select a single drive letter, for example C:')
    return drive.upper()


class ProcessCompletionUnknown(RuntimeError):
    """A launched maintenance process could not be observed to finish normally."""


def _read_pipe_available(stream):
    """Read only bytes already in the pipe; None means a still-open idle pipe."""
    descriptor = stream.fileno()
    if os.name == 'nt':
        import msvcrt
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        peek = kernel.PeekNamedPipe
        peek.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                         ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD),
                         ctypes.POINTER(wintypes.DWORD)]
        peek.restype = wintypes.BOOL
        available = wintypes.DWORD()
        if not peek(msvcrt.get_osfhandle(descriptor), None, 0, None, ctypes.byref(available), None):
            error = ctypes.get_last_error()
            if error == 109:  # ERROR_BROKEN_PIPE: every writer closed its handle.
                return b''
            raise ctypes.WinError(error)
        if not available.value:
            return None
        size = min(available.value, 65536)
    else:
        import select
        if not select.select([descriptor], [], [], 0)[0]:
            return None
        size = 65536
    return os.read(descriptor, size)


def run_process_stream(args, progress_callback=None, filter_func=None, timeout=3600):
    """Drain a child, enforce a deadline even during silent output, and reap it.

    Cancellation of a maintenance sequence remains between commands. The long
    deadline is a failure boundary for a stalled child, not a user cancel action.
    """
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('A positive finite process timeout is required')
    process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               stdin=subprocess.DEVNULL, shell=False,
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    deadline = time.monotonic() + timeout
    callback_error = None
    decoder = None
    pending = bytearray()
    def report(raw):
        nonlocal decoder, callback_error
        # Keep UTF-16 half-newlines intact across binary line boundaries.
        if decoder is None and (raw.startswith(b'\xff\xfe') or b'\x00' in raw):
            decoder = codecs.getincrementaldecoder('utf-16-le')(errors='replace')
        line = (decoder.decode(raw).lstrip('\ufeff').strip() if decoder
                else decode_console_bytes(raw))
        if line and progress_callback and callback_error is None:
            try:
                if filter_func is None or filter_func(line):
                    progress_callback(line)
            except Exception as exc:
                callback_error = exc
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(args, timeout)
            raw = _read_pipe_available(process.stdout)
            if raw is None:
                if process.poll() is not None:
                    break  # A descendant cannot extend this command's lifetime.
                time.sleep(min(0.02, remaining))
                continue
            if not raw:
                break
            pending.extend(raw)
            while (newline := pending.find(b'\n')) >= 0:
                report(bytes(pending[:newline + 1]))
                del pending[:newline + 1]
            if len(pending) >= 65536:
                report(bytes(pending))  # Bound memory for tools emitting no newline.
                pending.clear()
        if pending:
            report(bytes(pending))
        return_code = process.wait(timeout=max(0, deadline - time.monotonic()))
        if callback_error:
            raise RuntimeError(f'Progress callback failed: {callback_error}')
        return return_code
    except (OSError, ValueError) as exc:
        raise ProcessCompletionUnknown(f'Process completion could not be verified: {exc}') from exc
    finally:
        try:
            if process.poll() is None:
                try:
                    process.kill()
                except OSError:
                    if process.poll() is None:
                        raise
                process.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ProcessCompletionUnknown(f'Process cleanup could not be verified: {exc}') from exc
        finally:
            process.stdout.close()


class CommandRunner:
    _COMMANDS = {
        ('sfc', '/scannow'): ('sfc.exe', '/scannow'),
        ('ipconfig', '/flushdns'): ('ipconfig.exe', '/flushdns'),
        ('netsh', 'winsock', 'reset'): ('netsh.exe', 'winsock', 'reset'),
        **{('dism', '/online', '/cleanup-image', action.lower()):
           ('dism.exe', '/Online', '/Cleanup-Image', action, '/NoRestart')
           for action in ('/CheckHealth', '/RestoreHealth', '/StartComponentCleanup')},
    }

    def __init__(self, logger=None):
        self.logger = logger if logger is not None else Logger()
        self.restart_required = False
        self.completion_unknown = False

    @classmethod
    def command_args(cls, command_str):
        if not isinstance(command_str, str) or any(char in command_str for char in '\r\n\x00'):
            raise ValueError('Command is not an approved maintenance operation')
        tokens = tuple(command_str.split())
        approved = cls._COMMANDS.get(tuple(token.lower() for token in tokens))
        if approved is None and len(tokens) == 4 and tokens[0].lower() == 'chkdsk' and tuple(t.lower() for t in tokens[2:]) == ('/scan', '/perf'):
            approved = ('chkdsk.exe', validate_drive(tokens[1]), '/scan', '/perf')
        if approved is None:
            raise ValueError('Command is not an approved maintenance operation')
        return [system_executable(approved[0]), *approved[1:]]

    def run_command(self, command_str, description):
        try:
            subprocess.Popen(self.command_args(command_str), shell=False,
                             creationflags=getattr(subprocess, 'CREATE_NEW_CONSOLE', 0))
            self.logger.log(f'Launched {description}; completion is shown in its console.')
            return True
        except Exception as exc:
            self.logger.log(f'Failed to launch {description}: {exc}', 'ERROR')
            return False

    def run_command_stream(self, command_str, description, progress_callback, filter_func=None, timeout=3600):
        self.restart_required = False
        self.completion_unknown = False
        try:
            args = self.command_args(command_str)
            return_code = run_process_stream(args, progress_callback, filter_func, timeout)
            if return_code == 1 and os.path.basename(args[0]).lower() == 'chkdsk.exe':
                message = f'{description} completed; errors repaired (exit code 1).'
                self.logger.log(message)
                if progress_callback:
                    progress_callback(message)
                return True
            if return_code == 3010 and os.path.basename(args[0]).lower() == 'dism.exe':
                self.restart_required = True
                message = f'{description} completed; restart required to finish applying changes.'
                self.logger.log(message, 'WARNING')
                if progress_callback:
                    progress_callback(message)
                return True
            if return_code:
                message = f'{description} failed with exit code {return_code}.'
                self.logger.log(message, 'WARNING')
                if progress_callback:
                    progress_callback(message)
                return False
            self.logger.log(f'{description} completed.')
            return True
        except Exception as exc:
            self.completion_unknown = isinstance(exc, (subprocess.TimeoutExpired, ProcessCompletionUnknown))
            message = f'Error executing {description}: {exc}'
            self.logger.log(message, 'ERROR')
            if progress_callback:
                try:
                    progress_callback(message)
                except Exception:
                    pass
            return False
