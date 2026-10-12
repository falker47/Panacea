"""Explicit System Restore actions with sequence-number verification."""
import json
import os
import re
import subprocess
from modules.commands import system_executable
from modules.logger import Logger


class RestoreManager:
    def __init__(self, logger=None):
        self.logger = logger if logger is not None else Logger()

    def _run_powershell(self, script, timeout=30):
        return subprocess.run([system_executable('powershell.exe'), '-NoProfile', '-NonInteractive',
                               '-Command', "$ErrorActionPreference='Stop'; " + script],
                              shell=False, capture_output=True, text=True, timeout=timeout,
                              creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))

    def ensure_restore_enabled(self, drive='C:\\'):
        """Enable protection only as an explicitly requested action, never during creation."""
        if not isinstance(drive, str) or not re.fullmatch(r'[A-Za-z]:\\', drive):
            self.logger.log('Invalid System Restore drive.', 'WARNING')
            return False
        try:
            result = self._run_powershell(f"Enable-ComputerRestore -Drive '{drive.upper()}'")
            if result.returncode != 0:
                self.logger.log(f'System Restore enable failed: {result.stderr}', 'WARNING')
                return False
            return True
        except Exception as exc:
            self.logger.log(f'System Restore enable failed: {exc}', 'WARNING')
            return False

    def get_last_restore_points(self, limit=3):
        if type(limit) is not int or not 1 <= limit <= 100:
            return []
        try:
            result = self._run_powershell(
                f'Get-ComputerRestorePoint | Sort-Object SequenceNumber | '
                f'Select-Object -Last {limit} CreationTime, Description | ConvertTo-Json')
            if result.returncode or not result.stdout.strip():
                return []
            data = json.loads(result.stdout)
            if isinstance(data, dict):
                data = [data]
            return [f"{item.get('CreationTime')} - {item.get('Description')}" for item in reversed(data)]
        except Exception as exc:
            self.logger.log(f'Error listing restore points: {exc}', 'ERROR')
            return []

    def _get_latest_restore_point_seq(self):
        """0 means a successful empty query; None means unverified/unavailable."""
        try:
            result = self._run_powershell('Get-ComputerRestorePoint | Sort-Object SequenceNumber | '
                                          'Select-Object -Last 1 -ExpandProperty SequenceNumber', timeout=15)
            if result.returncode:
                return None
            output = result.stdout.strip()
            if not output:
                return 0
            sequence = int(output)
            return sequence if sequence >= 0 else None
        except Exception:
            return None

    def create_restore_point(self, description='Panacea Auto-Restore'):
        if not isinstance(description, str) or not description.strip() or len(description) > 256 or any(ord(char) < 32 for char in description):
            return False, 'Invalid restore point description.'
        before = self._get_latest_restore_point_seq()
        if before is None:
            return False, 'System Restore state could not be verified. Check protection and administrator access.'
        safe_description = description.replace("'", "''")
        try:
            result = self._run_powershell(
                f"Checkpoint-Computer -Description '{safe_description}' -RestorePointType 'MODIFY_SETTINGS'", timeout=60)
            if result.returncode:
                message = (result.stderr or '').strip()
                self.logger.log(f'Restore point creation failed: {message}', 'ERROR')
                return False, f'Restore point creation failed: {message[:160]}'
            after = self._get_latest_restore_point_seq()
            if after is None or after <= before:
                message = 'No new restore point could be verified. Windows may have throttled creation or protection is unavailable.'
                self.logger.log(message, 'WARNING')
                return False, message
            self.logger.log(f'Restore point verified: sequence {after}.')
            return True, f'Restore point created and verified (sequence {after}).'
        except Exception as exc:
            self.logger.log(f'Restore point creation failed: {exc}', 'ERROR')
            return False, str(exc)
