import ctypes
import os
import shutil
import string
import subprocess
from modules.commands import ProcessCompletionUnknown, run_process_stream, system_executable, validate_drive
from modules.logger import Logger


class DiskOptimizer:
    def __init__(self, logger=None):
        self.logger = logger if logger is not None else Logger()
        self.completion_unknown = False

    def get_drives(self):
        """List local fixed volumes without probing disconnected network paths."""
        if os.name != 'nt':
            return []
        kernel = ctypes.windll.kernel32
        mask = kernel.GetLogicalDrives()
        if not mask:
            raise OSError('Windows drive inventory is unavailable')
        return [f'{letter}:' for index, letter in enumerate(string.ascii_uppercase)
                if mask & (1 << index) and kernel.GetDriveTypeW(f'{letter}:\\') == 3]

    def get_drive_info(self):
        result = []
        for drive in self.get_drives():
            info = {'letter': drive, 'type': 'Fixed', 'total_bytes': None, 'free_bytes': None,
                    'used_percent': None, 'available': False, 'error': ''}
            try:
                usage = shutil.disk_usage(drive + '\\')
                info.update(total_bytes=usage.total, free_bytes=usage.free,
                            used_percent=100 * usage.used / usage.total if usage.total else 0,
                            available=True)
            except OSError as exc:
                info['error'] = str(exc)
            result.append(info)
        return result

    def open_optimize_gui(self):
        try:
            subprocess.Popen([system_executable('dfrgui.exe')], shell=False,
                             creationflags=getattr(subprocess, 'DETACHED_PROCESS', 0), close_fds=True)
            self.logger.log('Launched Windows Optimize Drives.')
            return True
        except Exception as exc:
            self.logger.log(f'Failed to launch Optimize Drives: {exc}', 'ERROR')
            return False

    def analyze_optimize_drive(self, drive_letter, progress_callback=None, timeout=7200):
        self.completion_unknown = False
        try:
            drive = validate_drive(drive_letter)
            return_code = run_process_stream([system_executable('defrag.exe'), drive, '/O'],
                                            progress_callback, timeout=timeout)
            msg = (f'Optimization of {drive} completed.' if return_code == 0
                   else f'Optimization of {drive} failed with exit code {return_code}.')
            self.logger.log(msg, 'INFO' if return_code == 0 else 'WARNING')
            if progress_callback:
                progress_callback(msg)
            return return_code == 0
        except Exception as exc:
            self.completion_unknown = isinstance(exc, (subprocess.TimeoutExpired, ProcessCompletionUnknown))
            message = f'Optimization failed: {exc}'
            self.logger.log(message, 'ERROR')
            if progress_callback:
                try:
                    progress_callback(message)
                except Exception:
                    pass
            return False
