import os
import subprocess
import string
from modules.logger import Logger
from modules.utils import run_streaming_command


class DiskOptimizer:
    # Defrag output fragments to filter out (EN + IT localised)
    _DEFRAG_SKIP = (
        "Volume information", "Informazioni sul volume",
        "Volume size", "Dimensioni volume",
        "Free space", "Spazio disponibile",
        "Total space", "Spazio totale",
        "Post Defragmentation", "Report frammentazione",
        "Invoking", "Chiamata di",
        "Re-optimize", "Riottimizza",
        "Analysis:", "Analisi:",
        "Note:", "Nota:",
    )

    def __init__(self):
        self.logger = Logger()

    def get_drives(self) -> list[str]:
        """Return a list of available drive letters (e.g. ['C:', 'D:'])."""
        return [
            f"{letter}:"
            for letter in string.ascii_uppercase
            if os.path.exists(f"{letter}:\\")
        ]

    def get_drive_info(self) -> list[dict]:
        """Return a list of dicts with drive letter and type."""
        return [
            {"letter": d, "type": "Unknown (Windows manages)"}
            for d in self.get_drives()
        ]

    def open_optimize_gui(self) -> None:
        """Launch the built-in Windows Defragment and Optimize Drives GUI."""
        try:
            subprocess.Popen(["dfrgui.exe"])
            self.logger.log("Launched Defragment and Optimize Drives GUI.")
        except Exception as e:
            self.logger.log(f"Failed to launch dfrgui: {e}", "ERROR")

    def analyze_optimize_drive(self, drive_letter: str, progress_callback=None) -> None:
        """Run ``defrag /O`` on *drive_letter*, streaming output to *progress_callback*."""
        cmd = f"defrag {drive_letter} /O"

        if progress_callback:
            progress_callback(f"Starting optimization for {drive_letter}...\nCommand: {cmd}")
        else:
            self.logger.log(f"Starting optimization for {drive_letter}")

        def _defrag_filter(line: str) -> bool:
            if line.startswith("        "):
                return False
            return not any(frag in line for frag in self._DEFRAG_SKIP)

        cb = progress_callback or (lambda _line: None)
        success = run_streaming_command(
            cmd,
            cb,
            filter_func=_defrag_filter if progress_callback else None,
            timeout=1800,  # defrag can take a long time
            logger=self.logger,
            description=f"Optimize {drive_letter}",
        )

        if progress_callback:
            if success:
                progress_callback(f"Optimization of {drive_letter} completed successfully.")
            else:
                progress_callback(f"Optimization of {drive_letter} finished with errors.")
