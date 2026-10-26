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


def child(output):
    logging.getLogger("PanaceaLogger").addHandler(logging.NullHandler())
    sys.path.insert(0, str(ROOT))
    from idle_probe import process_sample
    import customtkinter as ctk
    from panacea_ui import PanaceaApp
    ctk.set_widget_scaling(1)
    ctk.set_window_scaling(1)
    started = time.perf_counter()
    app = PanaceaApp()
    init_ms = (time.perf_counter() - started) * 1000
    app.update_idletasks()
    flush_ms = (time.perf_counter() - started) * 1000 - init_ms
    setup_times = {}
    disk_trace = {}
    for key, fn in tuple(app._setup_functions.items()):
        def wrap(original, section):
            def traced():
                before = time.perf_counter()
                try:
                    if section == "Disk":
                        disk_trace.update(profile_disk_widgets(original))
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
    }
    failures = []
    app.report_callback_exception = lambda kind, exc, tb: failures.append(str(exc))
    agenda = [(name, "cold") for name in COLD] + [(name, "warm") for name in WARM]

    def navigate(index=0):
        if index == len(agenda):
            app.after(2800, begin_idle)
            return
        name, kind = agenda[index]
        before = time.perf_counter()
        app.select_frame(name)
        callback = 1000 * (time.perf_counter() - before)
        before = time.perf_counter()
        app.update_idletasks()
        geometry = 1000 * (time.perf_counter() - before)
        _, _, resident = process_sample()
        result[kind][name] = {
            "callback_ms": round(callback, 2),
            "geometry_flush_ms": round(geometry, 2),
            "total_ms": round(callback + geometry, 2),
            "setup_ms": setup_times.get(name),
            "disk_setup_ms": setup_times.get("Disk") if name == "Tools" else None,
            "resident_mb": round(resident, 2),
        }
        app.after(90, navigate, index + 1)

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
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.child:
        child(args.output)
        return
    if args.samples < 5:
        parser.error("Use five or more independent processes")
    samples = []
    for index in range(args.samples):
        path = args.output.with_name(f"{args.output.stem}-sample-{index}.json")
        completed = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--child", "--output", str(path)],
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
        "method": "Independent Windows source-GUI processes, normal read-only monitoring; cold/warm select_frame callback plus Tk update_idletasks; no packaged extraction or compositor paint. Idle CPU normalized by logical processor count across 5 seconds.",
        "startup_median_ms": {key: median([s["startup"][key] for s in samples])
                              for key in samples[0]["startup"]},
        "sections": {},
        "disk_trace_median_ms": {
            key: median([sample["disk_trace"][key]["total_ms"] for sample in samples])
            for key in samples[0]["disk_trace"]
        },
        "disk_setup_median_ms": median([sample["cold"]["Tools"].get("disk_setup_ms") for sample in samples]),
        "idle_median_cpu_percent": median([s["idle"]["cpu_percent_total_machine"] for s in samples]),
        "idle_median_resident_mb": median([s["idle"]["resident_mb"] for s in samples]),
        "samples": samples,
    }
    for kind in ("cold", "warm"):
        report["sections"][kind] = {
            name: {field: median([s[kind][name][field] for s in samples
                                  if s[kind][name][field] is not None])
                   for field in ("callback_ms", "geometry_flush_ms", "total_ms",
                                 "setup_ms", "resident_mb")}
            for name in samples[0][kind]
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "samples"}, indent=2))


if __name__ == "__main__":
    main()
