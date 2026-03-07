import json
import subprocess
from modules.logger import Logger
from modules.utils import NO_WINDOW, SUBPROCESS_TIMEOUT

_RESTORE_TIMEOUT = 60  # creating a restore point can be slow


class RestoreManager:
    def __init__(self):
        self.logger = Logger()

    def ensure_restore_enabled(self, drive: str = "C:\\") -> bool:
        """Enable System Restore on *drive* (idempotent)."""
        try:
            self.logger.log(f"Ensuring System Restore is enabled on {drive}...")
            subprocess.run(
                ["powershell.exe", "-Command",
                 f"Enable-ComputerRestore -Drive '{drive}'"],
                capture_output=True,
                creationflags=NO_WINDOW,
                timeout=SUBPROCESS_TIMEOUT,
            )
            return True
        except subprocess.TimeoutExpired:
            self.logger.log("Enable-ComputerRestore timed out.", "WARNING")
            return False
        except Exception as e:
            self.logger.log(f"Failed to enable system restore: {e}", "WARNING")
            return False

    def get_last_restore_points(self, limit: int = 3) -> list[str]:
        """Return list of ``'date - description'`` strings, newest first."""
        try:
            p = subprocess.run(
                ["powershell.exe", "-Command",
                 f"Get-ComputerRestorePoint | Select-Object -Last {limit} "
                 f"CreationTime, Description | ConvertTo-Json"],
                capture_output=True, text=True,
                creationflags=NO_WINDOW,
                timeout=SUBPROCESS_TIMEOUT,
            )

            if p.returncode != 0 or not p.stdout.strip():
                return []

            data = json.loads(p.stdout)
            if isinstance(data, dict):
                data = [data]

            points = [
                f"{item.get('CreationTime')} - {item.get('Description')}"
                for item in data
            ]
            return points[::-1]  # Newest first

        except subprocess.TimeoutExpired:
            self.logger.log("Listing restore points timed out.", "WARNING")
            return []
        except Exception as e:
            self.logger.log(f"Error listing restore points: {e}", "ERROR")
            return []

    def create_restore_point(
        self, description: str = "Panacea Auto-Restore"
    ) -> tuple[bool, str]:
        """Create a System Restore Point (requires admin)."""
        self.logger.log(f"Attempting to create restore point: {description}")
        self.ensure_restore_enabled()

        try:
            process = subprocess.run(
                ["powershell.exe", "-Command",
                 f"Checkpoint-Computer -Description '{description}' "
                 f"-RestorePointType 'MODIFY_SETTINGS'"],
                capture_output=True, text=True,
                creationflags=NO_WINDOW,
                timeout=_RESTORE_TIMEOUT,
            )

            if process.returncode == 0:
                self.logger.log("Restore point created successfully.")
                return True, "Restore Point created successfully."

            err = process.stderr.strip()
            self.logger.log(f"Failed to create restore point: {err}", "ERROR")

            if "0x80042306" in err:
                return False, "Failed: Shadow Copy Volume error."
            if "Privilege" in err or "Access" in err:
                return False, "Failed: Run as Administrator."
            return False, f"E: {err[:50]}..."

        except subprocess.TimeoutExpired:
            self.logger.log("Create restore point timed out.", "WARNING")
            return False, "Operation timed out."
        except Exception as e:
            self.logger.log(f"Exception creating restore point: {e}", "ERROR")
            return False, str(e)
