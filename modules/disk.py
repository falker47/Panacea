import os
import subprocess
import string
from modules.logger import Logger
from modules.utils import decode_console_bytes

class DiskOptimizer:
    def __init__(self):
        self.logger = Logger()

    def get_drives(self):
        drives = []
        # Use os.path.exists which is faster and more reliable than wmic
        for letter in string.ascii_uppercase:
            if os.path.exists(f"{letter}:\\"):
                drives.append(f"{letter}:")
        return drives

    def get_drive_info(self):
        """Returns a list of dicts with drive letter."""
        drives = self.get_drives()
        return [{"letter": d} for d in drives]

    def open_optimize_gui(self):
        try:
            subprocess.Popen(["dfrgui.exe"], creationflags=subprocess.DETACHED_PROCESS, close_fds=True)
            self.logger.log("Launched Windows Defragment and Optimize Drives GUI.")
        except Exception as e:
            self.logger.log(f"Failed to launch dfrgui: {e}", "ERROR")

    def analyze_optimize_drive(self, drive_letter, progress_callback=None):
        """
        Runs defrag /O on the specified drive and streams output to callback.
        """
        cmd = f"defrag {drive_letter} /O"
        
        if progress_callback:
            progress_callback(f"Starting optimization for {drive_letter}...\nCommand: {cmd}")
        else:
            self.logger.log(f"Starting optimization for {drive_letter}")

        try:
            # CREATE_NO_WINDOW = 0x08000000 to hide console window
            creation_flags = 0x08000000
            
            # Force UTF-8 encoding via chcp, then run the command
            # Using list form to avoid shell injection
            process = subprocess.Popen(
                ['cmd', '/c', f'chcp 65001 >NUL & {cmd}'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                shell=False,
                creationflags=creation_flags
                # text=True removed to handle bytes manually
            )
            
            # Real-time output capturing
            if progress_callback:
                while True:
                    line_bytes = process.stdout.readline()
                    if not line_bytes and process.poll() is not None:
                        break
                    if line_bytes:
                        line = decode_console_bytes(line_bytes)

                        if line:
                            # Basic filtering for defrag clutter
                            if "Volume information" in line or \
                               "Volume size" in line or "Dimensioni volume" in line or \
                               "Free space" in line or "Spazio disponibile" in line or \
                               "Total space" in line or "Spazio totale" in line or \
                               "Post Defragmentation" in line or "Report frammentazione" in line or \
                               "Invoking" in line or "Chiamata di" in line or \
                               "Volume information" in line or "Informazioni sul volume" in line or \
                               "Re-optimize" in line or "Riottimizza" in line or \
                               "Analysis:" in line or "Analisi:" in line or \
                               "Note:" in line or "Nota:" in line or \
                               line.startswith("        ") or line == "":
                               continue
                            
                            progress_callback(line)
            
            # Wait for completion
            return_code = process.wait()
            
            if return_code == 0:
                msg = f"Optimization of {drive_letter} completed successfully."
                if progress_callback: progress_callback(msg)
                self.logger.log(msg)
            else:
                msg = f"Optimization finished with return code {return_code}."
                if progress_callback: progress_callback(msg)
                self.logger.log(msg, "WARNING")
                
        except Exception as e:
            msg = f"Failed to start optimization: {e}"
            if progress_callback: progress_callback(msg)
            self.logger.log(msg, "ERROR")
