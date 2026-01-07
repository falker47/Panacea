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

    def run_command_stream(self, command_str, description, progress_callback, filter_func=None):
        """
        Runs a command and streams stdout to the callback.
        :param filter_func: Optional function that takes a line and returns True (keep) or False (discard).
        """
        self.logger.log(f"Stream command started: {description}")
        try:
            # Creation flags to hide window
            creation_flags = 0x08000000
            
            # Force UTF-8 encoding for the subprocess
            # We wrap the command in cmd.exe to set codepage first
            # 'chcp 65001' sets UTF-8. '>NUL' hides the chcp status output ("Active code page: 65001")
            wrapped_cmd = f'cmd /c "chcp 65001 >NUL & {command_str}"'
            
            process = subprocess.Popen(
                wrapped_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                shell=False, # We are running cmd explicitly
                creationflags=creation_flags
            )
            
            while True:
                line_bytes = process.stdout.readline()
                if not line_bytes and process.poll() is not None:
                    break
                if line_bytes:
                    try:
                        # Priority: UTF-8 -> CP1252 (ANSI) -> CP850 (OEM) -> MBCS
                        # UTF-8: Modern/Forced tools
                        # CP1252: Stubborn local tools (e.g. CHKDSK often outputs ANSI)
                        # CP850: Legacy
                        line = None
                        for enc in ['utf-8', 'cp1252', 'cp850', 'mbcs']:
                            try:
                                line = line_bytes.decode(enc).strip()
                                break
                            except UnicodeDecodeError:
                                continue
                        
                        if line is None:
                            line = line_bytes.decode('utf-8', errors='replace').strip()

                        # Fix common mojibake manually if needed, but correct encoding should work.
                        # Windows CMD 'Ó' is often 'à' in CP850 displayed as CP437 or similar.
                        # Actually 'Ó' (curly quote?) for 'ò' or 'à' suggests specific mismatches.
                        # Let's rely on Python's cp850 which is standard for IT CMD.

                        line = line.replace('\x00', '')
                        
                        if line:
                            # Apply Filter
                            if filter_func and not filter_func(line):
                                continue
                            
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
