import sys
import ctypes
import os
import subprocess

# ---------------------------------------------------------------------------
# Subprocess constants (shared across all modules)
# ---------------------------------------------------------------------------
NO_WINDOW = subprocess.CREATE_NO_WINDOW
SUBPROCESS_TIMEOUT = 15        # seconds – quick commands (sc, powercfg, etc.)
STREAM_WAIT_TIMEOUT = 600      # seconds – long-running streams (defrag, sfc, etc.)

# Multi-encoding fallback for decoding Windows subprocess output.
# Priority: UTF-8 (forced via chcp) → CP1252 (ANSI) → CP850 (OEM) → MBCS.
_ENCODING_CHAIN = ("utf-8", "cp1252", "cp850", "mbcs")


# ---------------------------------------------------------------------------
# Existing helpers
# ---------------------------------------------------------------------------
def is_admin() -> bool:
    """Check if the script is running with administrative privileges."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


# ---------------------------------------------------------------------------
# Subprocess utilities (shared by commands.py, disk.py, etc.)
# ---------------------------------------------------------------------------
def decode_process_line(line_bytes: bytes) -> str:
    """Decode a raw bytes line from a subprocess using multi-encoding fallback.

    Tries UTF-8 → CP1252 → CP850 → MBCS, then falls back to UTF-8 with
    replacement characters.  Strips whitespace and null bytes.
    """
    for enc in _ENCODING_CHAIN:
        try:
            return line_bytes.decode(enc).strip().replace("\x00", "")
        except UnicodeDecodeError:
            continue
    return line_bytes.decode("utf-8", errors="replace").strip().replace("\x00", "")


def run_streaming_command(
    command: str,
    callback,
    *,
    filter_func=None,
    timeout: int = STREAM_WAIT_TIMEOUT,
    logger=None,
    description: str = "",
) -> bool:
    """Run *command* and stream decoded output lines to *callback*.

    The command is wrapped with ``chcp 65001`` for UTF-8 output and executed
    in a hidden console window.

    Args:
        command:      Raw command string to execute.
        callback:     Called with each decoded non-empty line.
        filter_func:  Optional predicate – return ``False`` to skip a line.
        timeout:      Max seconds to wait after the read loop for the process
                      to exit (default 600 s).
        logger:       Optional :class:`Logger` for structured logging.
        description:  Human-readable label used in log messages.

    Returns:
        ``True`` if the process exited with code 0, ``False`` otherwise.
    """
    wrapped_cmd = f'cmd /c "chcp 65001 >NUL & {command}"'
    process = None
    try:
        process = subprocess.Popen(
            wrapped_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            shell=False,
            creationflags=NO_WINDOW,
        )

        for line_bytes in iter(process.stdout.readline, b""):
            line = decode_process_line(line_bytes)
            if not line:
                continue
            if filter_func and not filter_func(line):
                continue
            callback(line)

        return_code = process.wait(timeout=timeout)

        if return_code == 0:
            if logger:
                logger.log(f"Stream command finished: {description}")
            return True

        if logger:
            logger.log(
                f"Stream command finished with code {return_code}: {description}",
                "WARNING",
            )
        return False

    except subprocess.TimeoutExpired:
        if logger:
            logger.log(f"Stream command timed out: {description}", "WARNING")
        if process:
            process.kill()
            process.wait()
        return False

    except Exception as e:
        if logger:
            logger.log(f"Failed to stream {description}: {e}", "ERROR")
        callback(f"Error executing {description}: {e}")
        return False

    finally:
        if process and process.stdout:
            process.stdout.close()
