"""Read-only Windows GUI performance measurements from independent Tk processes.

Synchronous callback and geometry times are distinct from compositor paint.
No maintenance actions are invoked.
"""
import argparse
import json
import logging
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
COLD = ("Cleaning", "Tools", "Turbo", "Resurrect")
WARM = ("Dashboard", "Tools", "Resurrect", "Cleaning")


def median(values):
    return round(statistics.median(values), 2) if values else None


def profile_disk_widgets(build):
    """Inclusive, low-overhead breakdown of the synchronous Disk setup path.

    Nested timings overlap; they describe hotspots, not additive costs.
    Instrumentation is scoped to the Disk constructor and never ships in the app.
    """
    from contextlib import ExitStack
    from unittest.mock import patch
    import tkinter as tk
    import customtkinter as ctk
    from panacea_ui import PanaceaApp, _LocalizedText

    targets = (
        ("section_body", PanaceaApp, "_section_body"),
        ("card", PanaceaApp, "_card"),
        ("button", PanaceaApp, "_button"),
        ("section_log", PanaceaApp, "_section_log"),
        ("set_drives", PanaceaApp, "_set_drives"),
        ("drive_selected", PanaceaApp, "_drive_selected"),
        ("CTkFrame_init", ctk.CTkFrame, "__init__"),
        ("CTkOptionMenu_init", ctk.CTkOptionMenu, "__init__"),
        ("CTkOptionMenu_configure", ctk.CTkOptionMenu, "configure"),
        ("CTkProgressBar_init", ctk.CTkProgressBar, "__init__"),
        ("CTkProgressBar_set", ctk.CTkProgressBar, "set"),
        ("localized_widget_init", _LocalizedText, "__init__"),
        ("StringVar_init", tk.StringVar, "__init__"),
        ("tk_pack", tk.Pack, "pack"),
        ("tk_grid", tk.Grid, "grid"),
    )
    measures, counts = {}, {}
    with ExitStack() as scope:
        for key, owner, method in targets:
            original = getattr(owner, method)

            def timed(self, *args, _original=original, _key=key, **kwargs):
                start = time.perf_counter()
                try:
                    return _original(self, *args, **kwargs)
                finally:
                    elapsed = (time.perf_counter() - start) * 1000
                    measures[_key] = measures.get(_key, 0.0) + elapsed
                    counts[_key] = counts.get(_key, 0) + 1

            scope.enter_context(patch.object(owner, method, timed))
        build()
    return {
        key: {"total_ms": round(measures.get(key, 0), 2),
              "calls": counts.get(key, 0)}
        for key, _, _ in targets
    }


def profile_resurrect_widgets(build):
    """Trace guided-maintenance widget construction, with overlapping inclusive times.

    Instrumentation stays in the benchmark process; it does not modify the app.
    """
    from contextlib import ExitStack
    from unittest.mock import patch
    import tkinter as tk
    import customtkinter as ctk
    from panacea_ui import PanaceaApp, _LocalizedText

    targets = (
        ("scroller_init", ctk.CTkScrollableFrame, "__init__"),
        ("frame_init", ctk.CTkFrame, "__init__"),
        ("label_init", _LocalizedText, "__init__"),
        ("button_init", ctk.CTkButton, "__init__"),
        ("progress_init", ctk.CTkProgressBar, "__init__"),
        ("card", PanaceaApp, "_card"),
        ("button", PanaceaApp, "_button"),
        ("section_log", PanaceaApp, "_section_log"),
        ("tk_grid", tk.Grid, "grid"),
        ("tk_grid_configure", tk.Grid, "grid_configure"),
        ("tk_pack", tk.Pack, "pack"),
    )
    measures, counts = {}, {}
    with ExitStack() as scope:
        for key, owner, method in targets:
            original = getattr(owner, method)

            def timed(self, *args, _original=original, _key=key, **kwargs):
                start = time.perf_counter()
                try:
                    return _original(self, *args, **kwargs)
                finally:
                    measures[_key] = measures.get(_key, 0.) + (
                        time.perf_counter() - start) * 1000
                    counts[_key] = counts.get(_key, 0) + 1

            scope.enter_context(patch.object(owner, method, timed))
        build()
    return {
        key: {"total_ms": round(measures.get(key, 0), 2),
              "calls": counts.get(key, 0)}
        for key, _, _ in targets
    }


def limit_cpu_cores(cores):
    """Limit a disposable Windows probe process to a small CPU allocation."""
    if not cores:
        return
    import ctypes
    kernel = ctypes.windll.kernel32
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    kernel.GetProcessAffinityMask.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t),
        ctypes.POINTER(ctypes.c_size_t)]
    kernel.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    process = kernel.GetCurrentProcess()
    available, system = ctypes.c_size_t(), ctypes.c_size_t()
    if not kernel.GetProcessAffinityMask(process, ctypes.byref(available), ctypes.byref(system)):
        raise ctypes.WinError()
    allowed = [bit for bit in range(ctypes.sizeof(ctypes.c_size_t) * 8)
               if available.value & (1 << bit)]
    selected = sum(1 << bit for bit in allowed[:cores])
    if not selected or not kernel.SetProcessAffinityMask(process, selected):
        raise ctypes.WinError()


def child(output, affinity_cores=0):
    logging.getLogger("PanaceaLogger").addHandler(logging.NullHandler())
    sys.path.insert(0, str(ROOT))
    from idle_probe import process_sample
    import customtkinter as ctk
    from panacea_ui import PanaceaApp
    ctk.set_widget_scaling(1)
    ctk.set_window_scaling(1)
    limit_cpu_cores(affinity_cores)
    started = time.perf_counter()
    app = PanaceaApp()
    init_ms = (time.perf_counter() - started) * 1000
    app.update_idletasks()
    flush_ms = (time.perf_counter() - started) * 1000 - init_ms
    setup_times = {}
    disk_trace = {}
    resurrect_trace = {}
    for key, fn in tuple(app._setup_functions.items()):
        def wrap(original, section):
            def traced():
                before = time.perf_counter()
                try:
                    if section == "Disk":
                        disk_trace.update(profile_disk_widgets(original))
                        return None
                    if section == "Resurrect":
                        resurrect_trace.update(profile_resurrect_widgets(original))
                        return None
                    return original()
                finally:
                    setup_times[section] = round((time.perf_counter() - before) * 1000, 2)
            return traced
        app._setup_functions[key] = wrap(fn, key)
    result = {
        "startup": {"constructor_ms": round(init_ms, 2),
                    "first_geometry_flush_ms": round(flush_ms, 2)},
        "cold": {}, "warm": {}, "idle": {}, "disk_trace": disk_trace,
        "resurrect_trace": resurrect_trace,
    }
    failures = []
    event_loop_delays = []
    guided_delays = []
    guided_window = {"start": None, "end": None}
    expected_heartbeat = time.perf_counter() + 0.025

    def heartbeat():
        nonlocal expected_heartbeat
        if app._shutdown.is_set():
            return
        now = time.perf_counter()
        lag = max(0.0, (now - expected_heartbeat) * 1000)
        event_loop_delays.append(lag)
        if (guided_window["start"] is not None
                and (guided_window["end"] is None or now <= guided_window["end"])):
            guided_delays.append(lag)
        expected_heartbeat = now + 0.025
        app.after(25, heartbeat)

    app.after(25, heartbeat)
    app.report_callback_exception = lambda kind, exc, tb: failures.append(str(exc))
    agenda = [(name, "cold") for name in COLD] + [(name, "warm") for name in WARM]

    def navigate(index=0):
        if index == len(agenda):
            app.after(2800, begin_idle)
            return
        name, kind = agenda[index]
        nav_started = time.perf_counter()
        cpu_started = time.process_time()
        mapped = []
        if name == "Resurrect" and kind == "cold":
            guided_window["start"] = nav_started
            guided_window["end"] = None
            app.group_frames["Resurrect"].bind(
                "<Map>", lambda event: mapped.append(time.perf_counter())
                if not mapped else None, add="+")
        app.select_frame(name)
        callback = 1000 * (time.perf_counter() - nav_started)
        before = time.perf_counter()
        app.update_idletasks()
        geometry = 1000 * (time.perf_counter() - before)
        _, _, resident = process_sample()
        entry = {
            "callback_ms": round(callback, 2),
            "geometry_flush_ms": round(geometry, 2),
            "total_ms": round(callback + geometry, 2),
            "setup_ms": setup_times.get(name),
            "disk_setup_ms": setup_times.get("Disk") if name == "Tools" else None,
            "process_cpu_ms": round((time.process_time() - cpu_started) * 1000, 2),
            "disk_controls_ready": name != "Tools" or bool(app.drive_menu.winfo_exists()),
            "resident_mb": round(resident, 2),
        }
        result[kind][name] = entry
        if name != "Resurrect":
            app.after(90, navigate, index + 1)
            return

        entry["controls_ready"] = bool(
            app.btn_resurrect_start.winfo_exists()
            and app.btn_resurrect_cancel.winfo_exists()
            and app.progress_bar.winfo_exists())
        app.after(0, lambda: entry.update(
            first_event_loop_turn_ms=round(
                1000 * (time.perf_counter() - nav_started), 2)))

        def all_cards_ready():
            if len(app._resurrection_rows) == len(app.RESURRECTION_STEPS):
                before_flush = time.perf_counter()
                app.update_idletasks()
                entry["completion_geometry_flush_ms"] = round(
                    1000 * (time.perf_counter() - before_flush), 2)
                entry["all_cards_ready_ms"] = round(
                    1000 * (time.perf_counter() - nav_started), 2)
                entry["process_cpu_full_ms"] = round(
                    1000 * (time.process_time() - cpu_started), 2)
                _, _, full_ram = process_sample()
                entry["resident_full_mb"] = round(full_ram, 2)
                entry["first_map_event_ms"] = round(
                    1000 * (mapped[0] - nav_started), 2) if mapped else None
                entry["all_controls_ready"] = entry["controls_ready"] and bool(
                    app._resurrection_rows[app.RESURRECTION_STEPS[-1]].winfo_exists())
                entry["layout_mode"] = app._resurrection_layout_mode
                if kind == "cold":
                    guided_window["end"] = time.perf_counter() + 0.3
                app.after(90, navigate, index + 1)
            elif time.perf_counter() - nav_started > 6:
                failures.append("Guided maintenance cards were not ready within 6 seconds")
                guided_window["end"] = time.perf_counter()
                app.after(0, navigate, index + 1)
            else:
                app.after(16, all_cards_ready)

        app.after(16, all_cards_ready)

    def begin_idle():
        result["idle"]["before"] = process_sample()
        app.after(5000, end_idle)

    def end_idle():
        first = result["idle"].pop("before")
        second = process_sample()
        wall = max(.00001, second[0] - first[0])
        cpu = 100 * (second[1] - first[1]) / wall / (os.cpu_count() or 1)
        result["idle"] = {
            "cpu_percent_total_machine": round(max(0, cpu), 3),
            "resident_mb": round(second[2], 2),
            "seconds": round(wall, 2),
        }
        delays = sorted(event_loop_delays)
        result['event_loop'] = {
            'max_lag_ms': round(max(delays, default=0.0), 2),
            'p95_lag_ms': round(delays[int((len(delays) - 1) * .95)], 2) if delays else 0.0,
            'p99_lag_ms': round(delays[int((len(delays) - 1) * .99)], 2) if delays else 0.0,
        }
        guided = sorted(guided_delays)
        result["resurrect_event_loop"] = {
            "max_lag_ms": round(max(guided, default=0.0), 2),
            "p95_lag_ms": round(guided[int((len(guided) - 1) * .95)], 2) if guided else 0.0,
            "p99_lag_ms": round(guided[int((len(guided) - 1) * .99)], 2) if guided else 0.0,
            "samples": len(guided),
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2), encoding="utf-8")
        app._on_close()
        if failures:
            raise RuntimeError("GUI callback errors: " + "; ".join(failures))

    app.after(200, navigate)
    app.mainloop()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--child", action="store_true")
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--affinity-cores", type=int, default=0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.affinity_cores < 0:
        parser.error("Affinity cores cannot be negative")
    if args.child:
        child(args.output, args.affinity_cores)
        return
    if args.samples < 5:
        parser.error("Use five or more independent processes")
    samples = []
    for index in range(args.samples):
        path = args.output.with_name(f"{args.output.stem}-sample-{index}.json")
        cmd = [sys.executable, str(Path(__file__).resolve()), "--child", "--output",
               str(path), "--affinity-cores", str(args.affinity_cores)]
        completed = subprocess.run(
            cmd,
            cwd=ROOT, check=False, timeout=75, capture_output=True, text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if completed.returncode:
            raise RuntimeError(
                f"GUI sample {index} failed (exit={completed.returncode}):\n"
                f"{completed.stdout[-4000:]}\n{completed.stderr[-4000:]}")
        samples.append(json.loads(path.read_text(encoding="utf-8")))
    report = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "samples_count": len(samples),
        "affinity_cores": args.affinity_cores or None,
        "method": "Independent read-only Windows Tk processes; initial callback and geometry flush, first next-loop turn, Tk Map event and all ten cards plus final geometry. Tk Map is not compositor paint. Idle CPU normalized by logical processor count.",
        "startup_median_ms": {key: median([s["startup"][key] for s in samples])
                              for key in samples[0]["startup"]},
        "sections": {},
        "disk_trace_median_ms": {
            key: median([sample["disk_trace"][key]["total_ms"] for sample in samples])
            for key in samples[0]["disk_trace"]
        },
        "resurrect_trace_median_ms": {
            key: median([sample["resurrect_trace"][key]["total_ms"] for sample in samples])
            for key in samples[0]["resurrect_trace"]
        },
        "resurrect_trace_calls": {
            key: samples[0]["resurrect_trace"][key]["calls"]
            for key in samples[0]["resurrect_trace"]
        },
        "disk_setup_median_ms": median([sample["cold"]["Tools"].get("disk_setup_ms") for sample in samples]),
        "event_loop_median_ms": {
            key: median([sample['event_loop'][key] for sample in samples])
            for key in samples[0]['event_loop']
        },
        "resurrect_event_loop_median_ms": {
            key: median([sample['resurrect_event_loop'][key] for sample in samples])
            for key in ("max_lag_ms", "p95_lag_ms", "p99_lag_ms")
        },
        "idle_median_cpu_percent": median([s["idle"]["cpu_percent_total_machine"] for s in samples]),
        "idle_median_resident_mb": median([s["idle"]["resident_mb"] for s in samples]),
        "samples": samples,
    }
    for kind in ("cold", "warm"):
        fields = ("callback_ms", "geometry_flush_ms", "total_ms", "setup_ms",
                  "resident_mb", "process_cpu_ms", "controls_ready",
                  "first_event_loop_turn_ms", "first_map_event_ms",
                  "all_cards_ready_ms", "completion_geometry_flush_ms",
                  "process_cpu_full_ms", "resident_full_mb", "all_controls_ready")
        report["sections"][kind] = {
            name: {field: median([s[kind][name].get(field) for s in samples
                                  if s[kind][name].get(field) is not None])
                   for field in fields}
            for name in samples[0][kind]
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "samples"}, indent=2))


if __name__ == "__main__":
    main()
