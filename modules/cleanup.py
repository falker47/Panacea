import os
import shutil
import subprocess
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

    def clean_browser_caches(self):
        """Clears cache for Chrome, Edge, and Firefox"""
        deleted_count = 0
        deleted_size = 0
        
        users_dir = os.path.dirname(os.environ['USERPROFILE'])
        # We only really care about current user usually, but let's stick to env vars
        local_app_data = os.environ.get('LOCALAPPDATA')
        
        if not local_app_data: return 0, 0

        # Define targets
        targets = [
            os.path.join(local_app_data, r"Google\Chrome\User Data\Default\Cache"),
            os.path.join(local_app_data, r"Google\Chrome\User Data\Default\Code Cache"),
            os.path.join(local_app_data, r"Microsoft\Edge\User Data\Default\Cache"),
            os.path.join(local_app_data, r"Microsoft\Edge\User Data\Default\Code Cache"),
            os.path.join(local_app_data, r"Mozilla\Firefox\Profiles"), # Needs wildcard handling
        ]

        self.logger.log("Starting Browser Cleanup...")

        for target in targets:
            # Handle Firefox wildcard profiles
            if "Firefox" in target:
                 # Look for /cache2 inside profiles
                 if os.path.exists(target):
                     for profile in os.listdir(target):
                         cache_path = os.path.join(target, profile, "cache2")
                         if os.path.exists(cache_path):
                             c, s = self._delete_folder_contents(cache_path)
                             deleted_count += c; deleted_size += s
            else:
                if os.path.exists(target):
                    c, s = self._delete_folder_contents(target)
                    deleted_count += c; deleted_size += s
        
        return deleted_count, deleted_size

    def _delete_folder_contents(self, folder_path):
        c, s = 0, 0
        for root, dirs, files in os.walk(folder_path):
            for name in files:
                try:
                    fp = os.path.join(root, name)
                    sz = os.path.getsize(fp)
                    os.remove(fp)
                    c += 1; s += sz
                except PermissionError:
                    pass  # Locked files are expected
                except Exception as e:
                    self.logger.log(f"Could not delete {os.path.join(root, name)}: {e}", "WARNING")
        return c, s

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
                    except Exception:
                        pass  # Locked files are expected

                for name in dirs:
                    dir_path = os.path.join(root, name)
                    try:
                        shutil.rmtree(dir_path)
                    except Exception:
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
            
            # S_OK = 0, E_UNEXPECTED = -2147418113 (0x8000FFFF, often means already empty)
            if result == 0:
                self.logger.log("Recycle bin emptied successfully.")
                return True, "Recycle bin emptied."
            elif result == -2147418113:
                self.logger.log("Recycle bin was already empty.")
                return True, "Recycle bin was already empty."
            else:
                self.logger.log(f"Recycle bin API returned code: {result}", "WARNING")
                return False, f"Recycle bin operation returned code {result}."

        except Exception as e:
            self.logger.log(f"Failed to empty recycle bin: {e}", "ERROR")
            return False, f"Error: {e}"

    def open_disk_cleanup(self):
        try:
            subprocess.Popen(["cleanmgr.exe"], creationflags=subprocess.DETACHED_PROCESS)
            self.logger.log("Launched Disk Cleanup utility.")
            return True
        except Exception as e:
            self.logger.log(f"Failed to launch cleanmgr: {e}", "ERROR")
            return False
