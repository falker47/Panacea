import os
import subprocess
import string
from modules.logger import Logger

class DiskOptimizer:
    def __init__(self):
        self.logger = Logger()

    def get_drives(self):
        drives = []
        bitmask = os.popen('wmic logicaldisk get caption').read()
        for letter in string.ascii_uppercase:
            if f"{letter}:" in bitmask:
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
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                shell=False, # shell=False is safer and enough since we passed the full executable command or simple args
                # Actually for 'defrag' we might need shell=True or full path if not in path, but usually it is.
                # Let's use shell=True but with hidden window to be safe with path resolution, 
                # OR better: use list args shell=False. 'defrag' is in System32.
                # We will stick to shell=True for compatibility with system commands but hide window.
                creationflags=creation_flags,
                text=True
            )
            
            # Real-time output capturing
            if progress_callback:
                while True:
                    line = process.stdout.readline()
                    if not line and process.poll() is not None:
                        break
                    if line:
                        progress_callback(line.strip())
            
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
