"""Known Windows maintenance operations, launched without a command shell."""
import ctypes
import os
import re
import subprocess
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


class CommandRunner:
    _COMMANDS = {
        ('sfc', '/scannow'): ('sfc.exe', '/scannow'),
        ('ipconfig', '/flushdns'): ('ipconfig.exe', '/flushdns'),
        ('netsh', 'winsock', 'reset'): ('netsh.exe', 'winsock', 'reset'),
        **{('dism', '/online', '/cleanup-image', action.lower()):
           ('dism.exe', '/Online', '/Cleanup-Image', action)
           for action in ('/CheckHealth', '/RestoreHealth', '/StartComponentCleanup')},
    }

    def __init__(self, logger=None):
        self.logger = logger if logger is not None else Logger()

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

    def run_command_stream(self, command_str, description, progress_callback, filter_func=None):
        try:
            process = subprocess.Popen(self.command_args(command_str), stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, shell=False,
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            callback_error = None
            try:
                for raw in iter(process.stdout.readline, b''):
                    line = decode_console_bytes(raw).replace('\x00', '')
                    if line and progress_callback and callback_error is None:
                        try:
                            if filter_func is None or filter_func(line):
                                progress_callback(line)
                        except Exception as exc:
                            # Wait for completion even when presentation fails.
                            callback_error = exc
                return_code = process.wait()
            finally:
                process.stdout.close()
            if callback_error:
                raise RuntimeError(f'Progress callback failed: {callback_error}')
            if return_code:
                self.logger.log(f'{description} failed with exit code {return_code}.', 'WARNING')
                return False
            self.logger.log(f'{description} completed.')
            return True
        except Exception as exc:
            message = f'Error executing {description}: {exc}'
            self.logger.log(message, 'ERROR')
            if progress_callback:
                try:
                    progress_callback(message)
                except Exception:
                    pass
            return False
