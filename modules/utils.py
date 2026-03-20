import  sys
import ctypes
import os

def is_admin():
    """Check if the script is running with administrative privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False

def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

def decode_console_bytes(line_bytes, encodings=('utf-8', 'cp1252', 'cp850', 'mbcs')):
    """Decode bytes from Windows console output, trying multiple encodings.
    Prioritizes UTF-8 (set via chcp 65001), then Windows codepages as fallback."""
    for enc in encodings:
        try:
            return line_bytes.decode(enc).strip()
        except (UnicodeDecodeError, ValueError, LookupError):
            continue
    return line_bytes.decode('utf-8', errors='replace').strip()
