"""Read-only per-process idle resource sampling after startup has settled."""
import argparse
import ctypes
from ctypes import wintypes
import json
import logging
import os
from pathlib import Path
import statistics
import sys
import time


class Counters(ctypes.Structure):
    _fields_ = [('cb', wintypes.DWORD), ('faults', wintypes.DWORD),
                ('peak_working', ctypes.c_size_t), ('working', ctypes.c_size_t),
                ('peak_paged', ctypes.c_size_t), ('paged', ctypes.c_size_t),
                ('peak_nonpaged', ctypes.c_size_t), ('nonpaged', ctypes.c_size_t),
                ('pagefile', ctypes.c_size_t), ('peak_pagefile', ctypes.c_size_t)]


def process_sample():
    kernel = ctypes.windll.kernel32
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    process = kernel.GetCurrentProcess()
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    memory = ctypes.windll.psapi.GetProcessMemoryInfo
    memory.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    if not memory(process, ctypes.byref(counters), counters.cb):
        raise ctypes.WinError()
    creation, exit_time, kernel_time, user_time = [ctypes.c_ulonglong() for _ in range(4)]
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    if not kernel.GetProcessTimes(process, ctypes.byref(creation), ctypes.byref(exit_time), ctypes.byref(kernel_time), ctypes.byref(user_time)):
        raise ctypes.WinError()
    return time.perf_counter(), (kernel_time.value + user_time.value) / 10_000_000, counters.working / 1024**2


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.source.resolve()))
    logging.getLogger('PanaceaLogger').addHandler(logging.NullHandler())
    from panacea_ui import PanaceaApp
    app = PanaceaApp()
    samples = []
    def observe():
        samples.append(process_sample())
        if len(samples) < 11:
            app.after(1000, observe)
        else:
            percentages = [100 * (second[1] - first[1]) / (second[0] - first[0]) / (os.cpu_count() or 1)
                           for first, second in zip(samples, samples[1:])]
            result = {'method': 'Ten one-second source-GUI idle intervals after ten-second settling; GetProcessTimes CPU normalized by logical processor count, GetProcessMemoryInfo working set. Monitoring/background checks remain active; no maintenance.',
                      'samples': samples, 'cpu_percent_normalized': percentages,
                      'median_cpu_percent': statistics.median(percentages),
                      'median_working_set_mb': statistics.median(sample[2] for sample in samples)}
            args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
            print(json.dumps({key:value for key,value in result.items() if key not in ('samples','cpu_percent_normalized')}, indent=2))
            app._on_close()
    app.after(10000, observe)
    app.mainloop()


if __name__ == '__main__':
    main()
