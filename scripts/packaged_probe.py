"""Read-only native window timing for the candidate's safe --smoke-test mode."""
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import time


def usable_candidate_window(executable):
    user = ctypes.WinDLL('user32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user.IsWindowVisible.argtypes = [wintypes.HWND]
    user.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                 ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    observed = []
    @callback_type
    def examine(window, parameter):
        if not user.IsWindowVisible(window):
            return True
        title = ctypes.create_unicode_buffer(256)
        user.GetWindowTextW(window, title, len(title))
        if not title.value.startswith('Panacea'):
            return True
        pid = wintypes.DWORD()
        user.GetWindowThreadProcessId(window, ctypes.byref(pid))
        handle = kernel.OpenProcess(0x1000, False, pid.value)
        if not handle:
            return True
        try:
            path = ctypes.create_unicode_buffer(32768)
            length = wintypes.DWORD(len(path))
            if not kernel.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(length)):
                return True
            if os.path.normcase(path.value) != os.path.normcase(str(executable)):
                return True
            bounds = wintypes.RECT()
            if user.GetClientRect(window, ctypes.byref(bounds)):
                dimensions = [bounds.right - bounds.left, bounds.bottom - bounds.top]
                if dimensions[0] >= 640 and dimensions[1] >= 400:
                    observed.append({'pid': pid.value, 'client_pixels': dimensions})
        finally:
            kernel.CloseHandle(handle)
        return not observed
    user.EnumWindows(examine, 0)
    return observed[0] if observed else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--samples', type=int, default=5)
    args = parser.parse_args()
    executable = args.exe.resolve(strict=True)
    samples = []
    for index in range(args.samples):
        start = time.perf_counter()
        info = subprocess.STARTUPINFO()
        info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        process = subprocess.Popen([str(executable), '--smoke-test'], startupinfo=info)
        ready = None
        observed = None
        try:
            while process.poll() is None and time.perf_counter() - start < 30:
                if ready is None:
                    observed = usable_candidate_window(executable)
                    if observed:
                        ready = time.perf_counter() - start
                time.sleep(0.02)
            process.wait(timeout=1)
            elapsed = time.perf_counter() - start
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
        samples.append({'sample': index + 1, 'mapped_window_seconds': ready,
                        'window': observed, 'total_smoke_seconds': elapsed, 'exit_code': process.returncode})
        if process.returncode != 0 or ready is None:
            raise RuntimeError(f'Candidate did not pass safe native startup: {samples[-1]}')
    result = {'environment': platform.platform(), 'python_harness': platform.python_version(),
        'executable': str(executable), 'sha256': hashlib.sha256(executable.read_bytes()).hexdigest(),
        'method': 'Five sequential fresh packaged --smoke-test launches. Native visible client window at least640x400, checked every20ms. Includes onefile extraction. No UAC/maintenance, no OS cache purge, no old EXE executed. Fixed1.5s observation affects total duration, not mapped-window time.',
        'samples': samples, 'median_mapped_window_seconds': statistics.median(s['mapped_window_seconds'] for s in samples)}
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
