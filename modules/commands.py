import subprocess
from modules.logger import Logger
from modules.utils import run_streaming_command


class CommandRunner:
    def __init__(self):
        self.logger = Logger()

    def run_command(self, command_str: str, description: str) -> None:
        """Opens a new CMD window to run *command_str* (user-visible)."""
        try:
            subprocess.Popen(f'start cmd /k "{command_str}"', shell=True)
            self.logger.log(f"Executed command: {description} ({command_str})")
        except Exception as e:
            self.logger.log(f"Failed to execute {description}: {e}", "ERROR")

    def run_command_stream(
        self,
        command_str: str,
        description: str,
        progress_callback,
        filter_func=None,
    ) -> bool:
        """Run *command_str* and stream decoded stdout lines to *progress_callback*.

        Uses a multi-encoding fallback (UTF-8 → CP1252 → CP850 → MBCS) to
        correctly handle localised Windows tool output.

        Returns ``True`` if the command exited with code 0.
        """
        self.logger.log(f"Stream command started: {description}")
        return run_streaming_command(
            command_str,
            progress_callback,
            filter_func=filter_func,
            logger=self.logger,
            description=description,
        )
