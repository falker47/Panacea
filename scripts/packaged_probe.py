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


class ProcessMemoryCounters(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def peak_working_set(pid):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    query = kernel.K32GetProcessMemoryInfo
    query.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessMemoryCounters), wintypes.DWORD]
    handle = kernel.OpenProcess(0x1000 | 0x0010, False, pid)
    if not handle:
        return 0  # Process may have exited between the window check and sampling.
    try:
        counters = ProcessMemoryCounters()
        if query(handle, ctypes.byref(counters), ctypes.sizeof(counters)):
            return counters.PeakWorkingSetSize
        return 0
    finally:
        kernel.CloseHandle(handle)


def smoke_sample(executable):
    start = time.perf_counter()
    process = subprocess.Popen([str(executable), '--smoke-test'])
    ready = None
    window = None
    peak_gui = peak_loader = 0
    try:
        while process.poll() is None and time.perf_counter() - start < 30:
            if window is None:
                window = usable_candidate_window(executable)
                if window:
                    ready = time.perf_counter() - start
            if window:
                peak_gui = max(peak_gui, peak_working_set(window["pid"]))
            peak_loader = max(peak_loader, peak_working_set(process.pid))
            time.sleep(0.02)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
    return {"mapped_window_seconds": ready, "window": window,
            "gui_peak_working_set_bytes": peak_gui, "loader_peak_working_set_bytes": peak_loader,
            "total_smoke_seconds": time.perf_counter() - start, "exit_code": process.returncode}


BASELINE_SHA256 = "c74c860f3c6e132301b4020cf0a9abc296f183c2af2be508444713e9583cbd98"
BASELINE_LABEL = "v2.1.1"
BASELINE_RETRIES = 2
MIN_BASELINE_SAMPLES = 3


def compare(candidate, baseline):
    ratio = candidate / baseline
    passed = candidate <= 1.1 * baseline
    return {"candidate_to_baseline_ratio": ratio, "improvement_percent": (1 - ratio) * 100,
            "maximum_ratio": 1.1, "passed": passed, "result": "passed" if passed else "failed"}


def record_sample(label, executable, number, report):
    is_baseline = label == BASELINE_LABEL
    attempts = 1 + BASELINE_RETRIES if is_baseline else 1
    for attempt in range(1, attempts + 1):
        row = {**smoke_sample(executable), "sample": number, "attempt": attempt}
        valid = (row.get("exit_code") == 0 and bool(row.get("window"))
                 and row.get("mapped_window_seconds") is not None
                 and (row.get("gui_peak_working_set_bytes") or 0) > 0)
        if is_baseline and not valid:
            report["baseline_anomalies"].append(row)
            continue
        report["runs"][label]["samples"].append(row)
        if not valid:
            raise RuntimeError(f"{label} failed native smoke sample {number}: {row}")
        return


def measure_startup(paths, count, report):
    runs = report["runs"]
    for index in range(count):
        for label in (reversed(paths) if index % 2 else paths):
            record_sample(label, paths[label], index + 1, report)

    for label, run in runs.items():
        samples = run["samples"]
        run["peak_working_set_bytes"] = max((row["gui_peak_working_set_bytes"] for row in samples), default=None)
        if label != BASELINE_LABEL or len(samples) >= MIN_BASELINE_SAMPLES:
            run["median_mapped_window_seconds"] = statistics.median(row["mapped_window_seconds"] for row in samples)

    if BASELINE_LABEL not in runs:
        return
    baseline = runs[BASELINE_LABEL]
    valid_count = len(baseline["samples"])
    if valid_count < MIN_BASELINE_SAMPLES:
        report["comparison"] = {"result": "inconclusive", "passed": False, "valid_baseline_samples": valid_count,
                                "minimum_valid_baseline_samples": MIN_BASELINE_SAMPLES}
        raise RuntimeError(f"Same-runner comparison inconclusive: {BASELINE_LABEL} baseline was unstable "
                           f"({valid_count}/{count} valid samples, at least {MIN_BASELINE_SAMPLES} required). "
                           f"All {count} candidate smoke samples passed.")
    report["comparison"] = compare(runs["candidate"]["median_mapped_window_seconds"],
                                   baseline["median_mapped_window_seconds"])
    if not report["comparison"]["passed"]:
        raise RuntimeError("Candidate startup exceeds 110% of the same-runner v2.1.1 median")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--samples', type=int, default=5)
    parser.add_argument('--baseline', type=Path, help="Pinned v2.1.1 on the authorized disposable runner")
    args = parser.parse_args()
    if args.samples < 1:
        parser.error("--samples must be positive")
    paths = {"candidate": args.exe.resolve(strict=True)}
    report = {"environment": platform.platform(), "python_harness": platform.python_version(), "runs": {},
              "baseline_anomalies": [],
              "method": "Fresh --smoke-test processes, interleaved with alternating first launch. "
                        "Time to a visible 640x400 client window, including extraction. "
                        "OS peak working sets sampled separately for GUI and one-file loader."}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        if args.baseline:
            if (os.name != "nt" or os.getenv("GITHUB_ACTIONS") != "true"
                    or os.getenv("RUNNER_ENVIRONMENT") != "github-hosted"
                    or os.getenv("PANACEA_ALLOW_HOSTED_PROBE") != "true"):
                raise RuntimeError("Release baseline requires the authorized GitHub-hosted runner")
            paths[BASELINE_LABEL] = args.baseline.resolve(strict=True)
        for label, path in paths.items():
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            if label == BASELINE_LABEL and digest != BASELINE_SHA256:
                raise ValueError("Published v2.1.1 digest differs from the pin")
            report["runs"][label] = {"executable": str(path), "sha256": digest, "samples": []}
        measure_startup(paths, args.samples, report)
    except Exception as exc:
        report["error"] = str(exc)
        raise
    finally:
        # Preserve the original single-executable report fields for existing readers.
        report.update(report["runs"].get("candidate", {}))
        payload = json.dumps(report, indent=2)
        args.output.write_text(payload + "\n", encoding="utf-8")
        print(payload)


if __name__ == '__main__':
    main()
