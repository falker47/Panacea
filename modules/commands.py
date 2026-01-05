import subprocess
from modules.logger import Logger

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

    def run_command_stream(self, command_str, description, progress_callback):
        """Runs a command and streams stdout to the callback."""
        self.logger.log(f"Stream command started: {description}")
        try:
            # Creation flags to hide window
            creation_flags = 0x08000000
            process = subprocess.Popen(
                command_str,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                shell=True,
                creationflags=creation_flags
                # text=True removed to handle bytes manually
            )
            
            while True:
                line_bytes = process.stdout.readline()
                if not line_bytes and process.poll() is not None:
                    break
                if line_bytes:
                    try:
                        # Attempt to decode with codepage 850 (common for Italian Windows Shell)
                        # or fallback to utf-8/mbcs
                        try:
                            line = line_bytes.decode('cp850').strip()
                        except:
                            line = line_bytes.decode('mbcs', errors='replace').strip()
                        
                        # Fix spaced text (NUL bytes often present in some tool outputs)
                        line = line.replace('\x00', '')
                        
                        if line:
                            progress_callback(line)
                    except Exception:
                        pass # Skip unparseable lines
            
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
