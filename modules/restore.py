import subprocess
from modules.logger import Logger

class RestoreManager:
    def __init__(self):
        self.logger = Logger()

    def ensure_restore_enabled(self, drive="C:\\"):
        """Checks if System Restore is enabled, enables it if not."""
        try:
            self.logger.log(f"Ensuring System Restore is enabled on {drive}...")
            subprocess.run(
                ['powershell.exe', '-NoProfile', '-Command', f"Enable-ComputerRestore -Drive '{drive}'"],
                capture_output=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
            
            # We assume it worked or was already on. 
            return True
        except Exception as e:
            self.logger.log(f"Failed to enable system restore: {e}", "WARNING")
            return False

    def get_last_restore_points(self, limit=3):
        """Returns list of (date, description) tuples"""
        try:
            p = subprocess.run(
                ['powershell.exe', '-NoProfile', '-Command',
                 f"Get-ComputerRestorePoint | Select-Object -Last {limit} CreationTime, Description | ConvertTo-Json"],
                capture_output=True, text=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
            
            if p.returncode != 0 or not p.stdout.strip():
                return []
                
            import json
            data = json.loads(p.stdout)
            
            # Handle single object vs list
            if isinstance(data, dict):
                data = [data]
                
            points = []
            for item in data:
                # Convert weird PS date format if needed, or just use string
                # PS JSON date often looks like "/Date(123456)/" or just string depending on version
                # But 'CreationTime' usually comes out as string in JSON for this cmdlet
                points.append(f"{item.get('CreationTime')} - {item.get('Description')}")
                
            return points[::-1] # Newest first
        except Exception as e:
            self.logger.log(f"Error listing restore points: {e}", "ERROR")
            return []

    def _get_latest_restore_point_seq(self):
        """Return SequenceNumber of newest restore point, or None if none/error."""
        try:
            p = subprocess.run(
                ['powershell.exe', '-NoProfile', '-Command',
                 "Get-ComputerRestorePoint | "
                 "Sort-Object SequenceNumber | "
                 "Select-Object -Last 1 -ExpandProperty SequenceNumber"],
                capture_output=True, text=True, timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW)
            if p.returncode != 0:
                return None
            out = p.stdout.strip()
            return int(out) if out else None
        except Exception:
            return None

    def create_restore_point(self, description="Panacea Auto-Restore"):
        """
        Creates a Windows System Restore Point.
        Requires Administrative privileges.

        Windows throttles restore-point creation to one per 24h by default
        (SystemRestorePointCreationFrequency reg value). When throttled,
        Checkpoint-Computer exits 0 but silently does nothing, so we compare
        the latest sequence number before/after to detect this.
        """
        self.logger.log(f"Attempting to create restore point: {description}")

        # Enable it first just in case
        self.ensure_restore_enabled()

        seq_before = self._get_latest_restore_point_seq()

        # Escape single quotes for PowerShell
        safe_desc = description.replace("'", "''")
        cmd = f"Checkpoint-Computer -Description '{safe_desc}' -RestorePointType 'MODIFY_SETTINGS'"

        try:
            process = subprocess.run(
                ['powershell.exe', '-NoProfile', '-Command', cmd],
                capture_output=True, text=True, timeout=60,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            if process.returncode == 0:
                seq_after = self._get_latest_restore_point_seq()
                if (seq_before is not None and seq_after is not None
                        and seq_after == seq_before):
                    self.logger.log(
                        "Restore point skipped: Windows 24h throttle "
                        "(SystemRestorePointCreationFrequency).", "WARNING")
                    return False, ("Skipped: a restore point was already "
                                   "created within the last 24h (Windows limit).")
                self.logger.log("Restore point created successfully.")
                return True, "Restore Point created successfully."
            else:
                err = process.stderr.strip()
                self.logger.log(f"Failed to create restore point: {err}", "ERROR")
                # Common error handling
                if "0x80042306" in err: # Shadow Copy error
                    return False, "Failed: Shadow Copy Volume error."
                if "Privilege" in err or "Access" in err:
                    return False, "Failed: Run as Administrator."
                return False, f"Error: {err[:120]}"

        except Exception as e:
            self.logger.log(f"Exception creating restore point: {e}", "ERROR")
            return False, str(e)
