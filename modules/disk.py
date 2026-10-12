import os
import string
import subprocess
from modules.commands import system_executable, validate_drive
from modules.logger import Logger
from modules.utils import decode_console_bytes


class DiskOptimizer:
    def __init__(self, logger=None):
        self.logger = logger if logger is not None else Logger()

    def get_drives(self):
        return [f'{letter}:' for letter in string.ascii_uppercase if os.path.exists(f'{letter}:\\')]

    def get_drive_info(self):
        return [{'letter': drive} for drive in self.get_drives()]

    def open_optimize_gui(self):
        try:
            subprocess.Popen([system_executable('dfrgui.exe')], shell=False,
                             creationflags=getattr(subprocess, 'DETACHED_PROCESS', 0), close_fds=True)
            self.logger.log('Launched Windows Optimize Drives.')
            return True
        except Exception as exc:
            self.logger.log(f'Failed to launch Optimize Drives: {exc}', 'ERROR')
            return False

    def analyze_optimize_drive(self, drive_letter, progress_callback=None):
        try:
            drive = validate_drive(drive_letter)
            process = subprocess.Popen([system_executable('defrag.exe'), drive, '/O'],
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False,
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            callback_error = None
            try:
                for raw in iter(process.stdout.readline, b''):
                    line = decode_console_bytes(raw).replace('\x00', '')
                    if line and progress_callback and callback_error is None:
                        try:
                            progress_callback(line)
                        except Exception as exc:
                            callback_error = exc
                return_code = process.wait()
            finally:
                process.stdout.close()
            if callback_error:
                raise RuntimeError(f'Progress callback failed: {callback_error}')
            msg = (f'Optimization of {drive} completed.' if return_code == 0
                   else f'Optimization of {drive} failed with exit code {return_code}.')
            self.logger.log(msg, 'INFO' if return_code == 0 else 'WARNING')
            if progress_callback:
                progress_callback(msg)
            return return_code == 0
        except Exception as exc:
            message = f'Optimization failed: {exc}'
            self.logger.log(message, 'ERROR')
            if progress_callback:
                try:
                    progress_callback(message)
                except Exception:
                    pass
            return False
