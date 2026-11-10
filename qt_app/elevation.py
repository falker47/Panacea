"""Re-launch a Windows Python source script or a packaged executable with UAC.

For a Python interpreter the script path is essential; for PyInstaller it must
be omitted. List-to-command-line conversion quotes paths and arguments safely.
"""
from __future__ import annotations

import subprocess


def elevation_arguments(argv, *, frozen):
    if not argv or not argv[0]:
        raise ValueError("Cannot elevate without a program path")
    # The ShellExecuteW file parameter is sys.executable. In source mode, the
    # script pathname must be included in the parameters for that interpreter.
    return subprocess.list2cmdline(argv[1:] if frozen else argv)
