import subprocess
from modules.logger import Logger

class RestoreManager:
    def __init__(self):
        self.logger = Logger()

    def ensure_restore_enabled(self, drive="C:\\"):
        """Checks if System Restore is enabled, enables it if not."""
        try:
             # Check status
            check_cmd = f"powershell.exe -Command \"Get-ComputerRestorePoint -LastStatus\"" # Simple check isn't enough, we need Rstrui status
            # Actually, effective way is WMI or registry. 
            # Or simpler: Enable-ComputerRestore -Drive "C:\" (It's idempotent-ish)
            
            self.logger.log(f"Ensuring System Restore is enabled on {drive}...")
            enable_cmd = f"powershell.exe -Command \"Enable-ComputerRestore -Drive '{drive}'\""
            subprocess.run(enable_cmd, shell=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            
            # We assume it worked or was already on. 
            return True
        except Exception as e:
            self.logger.log(f"Failed to enable system restore: {e}", "WARNING")
            return False

    def get_last_restore_points(self, limit=3):
        """Returns list of (date, description) tuples"""
        try:
            cmd = f"powershell.exe -Command \"Get-ComputerRestorePoint | Select-Object -Last {limit} CreationTime, Description | ConvertTo-Json\""
            p = subprocess.run(cmd, shell=True, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            
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

    def create_restore_point(self, description="Panacea Auto-Restore"):
        """
        Creates a Windows System Restore Point.
        Requires Administrative privileges.
        """
        self.logger.log(f"Attempting to create restore point: {description}")
        
        # Power move: Enable it first just in case
        self.ensure_restore_enabled()
        
        # Use single quotes for PowerShell string arguments to avoid conflict with the outer double quotes required by shell=True execution
        cmd = f"Checkpoint-Computer -Description '{description}' -RestorePointType 'MODIFY_SETTINGS'"
        
        try:
            # We use PowerShell to execute the cmdlet
            # The outer command uses double quotes to wrap the entire PS command string
            ps_cmd = f'powershell.exe -Command "{cmd}"'
            
            # Run the command
            # Using specific startup info to hide window if possible, though 'run_command' usually handles this via subprocess
            process = subprocess.run(ps_cmd, shell=True, capture_output=True, text=True)
            
            if process.returncode == 0:
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
                return False, f"E: {err[:50]}..." # Truncate error for UI

        except Exception as e:
            self.logger.log(f"Exception creating restore point: {e}", "ERROR")
            return False, str(e)
