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
