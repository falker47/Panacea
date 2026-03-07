import ctypes
import os
import shutil
import subprocess
from modules.logger import Logger


class CleanupManager:
    def __init__(self):
        self.logger = Logger()

    def get_temp_paths(self) -> list[str]:
        """Return deduplicated list of temp directories to clean."""
        paths: list[str] = []
        if "TEMP" in os.environ:
            paths.append(os.environ["TEMP"])
        win_temp = os.path.join(
            os.environ.get("SystemRoot", r"C:\Windows"), "Temp")
        if os.path.exists(win_temp):
            paths.append(win_temp)
        return list(set(paths))

    # ------------------------------------------------------------------
    # Browser cache
    # ------------------------------------------------------------------
    def clean_browser_caches(self) -> tuple[int, int]:
        """Clear cache for Chrome, Edge, and Firefox."""
        deleted_count = 0
        deleted_size = 0

        local_app_data = os.environ.get("LOCALAPPDATA")
        if not local_app_data:
            return 0, 0

        targets = [
            os.path.join(local_app_data, r"Google\Chrome\User Data\Default\Cache"),
            os.path.join(local_app_data, r"Google\Chrome\User Data\Default\Code Cache"),
            os.path.join(local_app_data, r"Microsoft\Edge\User Data\Default\Cache"),
            os.path.join(local_app_data, r"Microsoft\Edge\User Data\Default\Code Cache"),
            os.path.join(local_app_data, r"Mozilla\Firefox\Profiles"),
        ]

        self.logger.log("Starting Browser Cleanup...")

        for target in targets:
            if "Firefox" in target:
                if os.path.exists(target):
                    for profile in os.listdir(target):
                        cache_path = os.path.join(target, profile, "cache2")
                        if os.path.exists(cache_path):
                            c, s = self._delete_folder_contents(cache_path)
                            deleted_count += c
                            deleted_size += s
            elif os.path.exists(target):
                c, s = self._delete_folder_contents(target)
                deleted_count += c
                deleted_size += s

        return deleted_count, deleted_size

    def _delete_folder_contents(self, folder_path: str) -> tuple[int, int]:
        """Delete files inside *folder_path*, returning (count, bytes_freed)."""
        count, size = 0, 0
        for root, _dirs, files in os.walk(folder_path):
            for name in files:
                fp = os.path.join(root, name)
                try:
                    sz = os.path.getsize(fp)
                    os.remove(fp)
                    count += 1
                    size += sz
                except OSError:
                    pass  # Skip locked / in-use files
        return count, size

    # ------------------------------------------------------------------
    # Temp files
    # ------------------------------------------------------------------
    def clean_temp_files(self, progress_callback=None) -> tuple[int, int]:
        """Delete temp files and empty directories, returning (count, bytes_freed)."""
        total_deleted = 0
        total_freed = 0

        for base_path in self.get_temp_paths():
            self.logger.log(f"Cleaning path: {base_path}")
            if progress_callback:
                progress_callback(f"Scanning {base_path}...")

            # Bottom-up traversal so directories are empty before we try to
            # remove them, avoiding the race condition of top-down + rmtree.
            for root, dirs, files in os.walk(base_path, topdown=False):
                for name in files:
                    file_path = os.path.join(root, name)
                    try:
                        size = os.path.getsize(file_path)
                        os.remove(file_path)
                        total_deleted += 1
                        total_freed += size
                    except OSError:
                        pass  # Locked files are expected in temp dirs

                for name in dirs:
                    dir_path = os.path.join(root, name)
                    try:
                        os.rmdir(dir_path)  # Only removes empty dirs (safe)
                    except OSError:
                        pass

        result_msg = (
            f"Cleanup complete. Deleted {total_deleted} files, "
            f"freed {total_freed / (1024 * 1024):.2f} MB."
        )
        self.logger.log(result_msg)
        return total_deleted, total_freed

    # ------------------------------------------------------------------
    # Recycle bin
    # ------------------------------------------------------------------
    def empty_recycle_bin(self) -> tuple[bool, str]:
        """Empty the Windows Recycle Bin using the native Shell API."""
        try:
            # SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND
            flags = 0x00000001 | 0x00000002 | 0x00000004
            result = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, flags)
            # S_OK = 0; other HRESULTs are non-fatal (e.g. already empty)
            self.logger.log(f"Recycle bin emptied (HRESULT={result}).")
            return True, "Recycle bin emptied."
        except Exception as e:
            self.logger.log(f"Failed to empty recycle bin: {e}", "ERROR")
            return False, f"Error: {e}"

    # ------------------------------------------------------------------
    # Disk Cleanup GUI
    # ------------------------------------------------------------------
    def open_disk_cleanup(self) -> bool:
        """Launch the built-in Disk Cleanup utility (cleanmgr.exe)."""
        try:
            subprocess.Popen(["cleanmgr.exe"])
            self.logger.log("Launched Disk Cleanup utility.")
            return True
        except Exception as e:
            self.logger.log(f"Failed to launch cleanmgr: {e}", "ERROR")
            return False
