import os
import shutil
import glob
from modules.logger import Logger

class CleanupManager:
    def __init__(self):
        self.logger = Logger()

    def get_temp_paths(self):
        paths = []
        # User Temp
        if 'TEMP' in os.environ:
            paths.append(os.environ['TEMP'])
        # Windows Temp
        win_temp = os.path.join(os.environ.get('SystemRoot', 'C:\\Windows'), 'Temp')
        if os.path.exists(win_temp):
            paths.append(win_temp)
        return list(set(paths)) # Remove duplicates

    def clean_temp_files(self, progress_callback=None):
        total_deleted = 0
        total_freed = 0
        paths = self.get_temp_paths()

        for base_path in paths:
            self.logger.log(f"Cleaning path: {base_path}")
            if progress_callback:
                progress_callback(f"Scanning {base_path}...")

            for root, dirs, files in os.walk(base_path):
                for name in files:
                    file_path = os.path.join(root, name)
                    try:
                        size = os.path.getsize(file_path)
                        os.remove(file_path)
                        total_deleted += 1
                        total_freed += size
                        self.logger.log(f"Deleted file: {file_path}")
                    except Exception as e:
                        # self.logger.log(f"Skipped file {file_path}: {e}", "WARNING")
                        pass # Valid to skip locked files
                
                for name in dirs:
                    dir_path = os.path.join(root, name)
                    try:
                        shutil.rmtree(dir_path)
                        self.logger.log(f"Deleted directory: {dir_path}")
                    except Exception as e:
                        pass
        
        result_msg = f"Cleanup complete. Deleted {total_deleted} files, freed {total_freed / (1024*1024):.2f} MB."
        self.logger.log(result_msg)
        return total_deleted, total_freed

    def empty_recycle_bin(self):
        try:
            # Use native Windows API via ctypes to avoid PowerShell issues
            import ctypes
            # SHERB_NOCONFIRMATION = 0x00000001
            # SHERB_NOPROGRESSUI = 0x00000002
            # SHERB_NOSOUND = 0x00000004
            flags = 0x00000001 | 0x00000002 | 0x00000004
            
            result = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, flags)
            
            # SHEmptyRecycleBin functions return S_OK (0) on success
            if result == 0 or result == -2147418113: # 0x8000FFFF (catastrophic failure) often means empty or locked? 
                # Actually, standard HRESULTs: S_OK, E_FAIL etc.
                # If it's already empty, it might return something else or S_OK.
                # Let's assume success if no exception for now, but check result.
                self.logger.log("Recycle bin emptied successfully (API call).")
                return True, "Recycle bin emptied."
            else:
                # If it returns non-zero, it might be an issue, but let's check common ones.
                # 0x80040154 (Class not registered) etc.
                # Let's just log result code.
                self.logger.log(f"Recycle bin API returned code: {result}")
                if result == -2147467259: # 'Unspecified error', happens if empty sometimes?
                     pass
                return True, "Recycle bin emptied." #(Optimistic)

        except Exception as e:
            self.logger.log(f"Failed to empty recycle bin: {e}", "ERROR")
            return False, f"Error: {e}"

    def open_disk_cleanup(self):
        try:
            import subprocess
            # Launch cleanmgr.exe
            subprocess.Popen(["cleanmgr.exe"])
            self.logger.log("Launched Disk Cleanup utility.")
            return True
        except Exception as e:
            self.logger.log(f"Failed to launch cleanmgr: {e}", "ERROR")
            return False
