import subprocess
from modules.logger import Logger
from modules.utils import decode_console_bytes

class CommandRunner:
    def __init__(self):
        self.logger = Logger()

    def run_command(self, command_str, description):
        """Runs a command in a new CMD window."""
        try:
            # use /k to keep window open so user can see result
            full_cmd = f'start cmd /k "{command_str}"'
            subprocess.Popen(full_cmd, shell=True)
            self.logger.log(f"Executed command: {description} ({command_str})")
        except Exception as e:
            self.logger.log(f"Failed to execute {description}: {e}", "ERROR")

    def run_command_stream(self, command_str, description, progress_callback, filter_func=None):
        """
        Runs a command and streams stdout to the callback.
        :param filter_func: Optional function that takes a line and returns True (keep) or False (discard).
        """
        self.logger.log(f"Stream command started: {description}")
        try:
            # Creation flags to hide window
            creation_flags = 0x08000000
            
            # Force UTF-8 encoding via chcp, then run the command
            # Using list form to avoid shell injection
            process = subprocess.Popen(
                ['cmd', '/c', f'chcp 65001 >NUL & {command_str}'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                shell=False,
                creationflags=creation_flags
            )
            
            while True:
                line_bytes = process.stdout.readline()
                if not line_bytes and process.poll() is not None:
                    break
                if line_bytes:
                    line = decode_console_bytes(line_bytes, ('utf-8', 'cp1252', 'cp850', 'mbcs'))
                    line = line.replace('\x00', '')

                    if line:
                        if filter_func and not filter_func(line):
                            continue
                        progress_callback(line)
            
            return_code = process.wait()
            if return_code == 0:
                self.logger.log(f"Stream command finished: {description}")
                return True
            else:
                self.logger.log(f"Stream command finished with error code {return_code}: {description}", "WARNING")
                return False
                
        except Exception as e:
            self.logger.log(f"Failed to stream {description}: {e}", "ERROR")
            progress_callback(f"Error executing {description}: {e}")
            return False
