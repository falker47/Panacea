import subprocess
from modules.logger import Logger

class RestoreManager:
    def __init__(self):
        self.logger = Logger()

    def create_restore_point(self, description="Panacea Auto-Restore"):
        """
        Creates a Windows System Restore Point.
        Requires Administrative privileges.
        """
        self.logger.log(f"Attempting to create restore point: {description}")
        
        # PowerShell command to enable system restore (just in case, often needed)
        # Enable-ComputerRestore -Drive "C:\"
        # But usually we just create it.
        
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
                return False, f"Error: {err}"

        except Exception as e:
            self.logger.log(f"Exception creating restore point: {e}", "ERROR")
            return False, str(e)
