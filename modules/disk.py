import os
import subprocess
import string
from modules.logger import Logger

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
        """Returns a list of dicts with drive letter and type (SSD/HDD/Unknown)"""
        drive_info = []
        try:
            # PowerShell command to get physical disk info
            # We need to map Logical Disks to Physical Disks which is complex in pure WMI/PS without admin
            # Simplified approach: Get all logical drives, attempt to guess or just list them.
            # A better approach for MediaType is `Get-PhysicalDisk` but mapping it to C: is tricky.
            # Using `winsat disk -drive letter` is invasive.
            # We will use `defrag /A` analysis output or `Get-PhysicalDisk` generally.
            
            # Let's try to get PhysicalDisk info and assume simple mapping for now or just list detected physical disks
            # Actually, `dfrgui` handles this best. 
            # We will list logical drives and try to get MediaType via PowerShell if possible.
            
            ps_cmd = "powershell \"Get-PhysicalDisk | Select-Object FriendlyName, MediaType, DeviceId\""
            # This doesn't directly map to volumes like C:.
            
            # Alternative: simpler, just list logical drives. The user can select one.
            # We will just list the drives found.
            drives = self.get_drives()
            for d in drives:
                # Default to Unknown/Generic
                drive_info.append({"letter": d, "type": "Unknown (Windows manages)"})

        except Exception as e:
            self.logger.log(f"Error listing drives: {e}", "ERROR")
        
        return drive_info

    def open_optimize_gui(self):
        try:
            subprocess.Popen(["dfrgui.exe"])
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
            
            # Force UTF-8 encoding for the subprocess
            wrapped_cmd = f'cmd /c "chcp 65001 >NUL & {cmd}"'
            
            process = subprocess.Popen(
                wrapped_cmd,
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
                         # 1. Try UTF-8 first
                         # 2. Try CP1252 (Common for CHKDSK/Defrag in IT locale)
                         # 3. Try CP850
                        line = None
                        for enc in ['utf-8', 'cp1252', 'cp850']:
                            try:
                                line = line_bytes.decode(enc).strip()
                                break
                            except: continue
                        if line is None: line = line_bytes.decode('utf-8', errors='replace').strip()

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
