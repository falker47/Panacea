"""Render the app's own views for Windows screenshot/layout QA; no maintenance."""
import argparse
import json
import logging
import hashlib
import ctypes
import sys
import time
import os
from contextlib import ExitStack
from unittest.mock import patch
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scale", type=float, default=1)
    parser.add_argument("--width", type=int, default=1100)
    parser.add_argument("--height", type=int, default=700)
    parser.add_argument("--language", choices=("it", "en"))
    parser.add_argument("--smoke-fixture", action="store_true",
                        help="Inert deterministic visual smoke; all host backends and launches denied")
    parser.add_argument("--focus-subviews", action="store_true",
                        help="Reveal stacked Disk/Startup panels in their own evidence")
    parser.add_argument("--settle-ms", type=int, default=2500,
                        help="Read-only startup settle before the first capture")
    args = parser.parse_args()
    sys.path.insert(0, str(args.source.resolve()))
    if args.language:
        os.environ["PANACEA_LANGUAGE"] = args.language
    logging.getLogger("PanaceaLogger").addHandler(logging.NullHandler())
    import customtkinter as ctk
    from PIL import ImageGrab
    from panacea_ui import PanaceaApp
    patches = ExitStack()
    if args.smoke_fixture:
        import panacea_ui as ui
        from scripts.ui_state_check import InertManager, InertMaintenanceGuard, denied
        for manager in ('Logger', 'CleanupManager', 'DiskOptimizer', 'CommandRunner',
                        'SystemMonitor', 'RestoreManager', 'PerformanceManager'):
            patches.enter_context(patch.object(ui, manager, InertManager))
        patches.enter_context(patch.object(ui, 'MaintenanceGuard', InertMaintenanceGuard))
        for method in ('update_dashboard', '_load_metadata', 'refresh_drives', '_load_turbo_states',
                       '_check_updates_thread', '_check_app_update'):
            patches.enter_context(patch.object(PanaceaApp, method, lambda self: None))
        for module, name in ((ui.subprocess, 'Popen'), (ui.subprocess, 'run'),
                             (ui.os, 'startfile'), (ui.webbrowser, 'open'), (ui.messagebox, 'askyesno')):
            patches.enter_context(patch.object(module, name, denied))
    ctk.set_widget_scaling(args.scale)
    ctk.set_window_scaling(1)
    app = PanaceaApp()
    app.geometry(f"{args.width}x{args.height}")
    app.attributes("-topmost", True)
    if args.smoke_fixture:
        app.app_update_status.configure(text="SIMULATED RESULTS · UI fixture only")
        app.btn_check_update.configure(state='disabled')
        app._update_fast_gui({"cpu": 30.8, "ram": (16.0, 1.5, 90.7), "disk": (256.0, 6.4, 97.5),
                              "battery": (72, "Plugged In"), "uptime": "0d 3h 8m"})
        app._update_metadata_gui({"os": "Windows 11", "cpu_name": "AMD Ryzen 7",
                                  "ram_info": "16.0 GB RAM", "disk_model": "System SSD"})
        app._update_updates_gui(0, 0, "Up to date")
        for graph, points in ((app.cpu_graph, [17, 16, 18, 19, 17, 24, 27, 31, 30, 32, 30.8]),
                              (app.ram_graph, [84, 84.3, 85, 85.1, 86, 88, 89, 90.7])):
            graph.points = ([0.0] * 60 + points)[-60:]
            graph.draw()
        app._turbo_states = {"power": True, "visual": False, "sysmain": False, "wsearch": False, "spooler": False}
        app._turbo_master = False
        app._turbo_saved = {"power": "balanced", "visual": True}
        app._set_drives([{"letter": "C:", "available": True, "type": "Fixed", "used_percent": 97.5,
                          "total_bytes": 256 * 1024**3, "free_bytes": 6.4 * 1024**3}])
    names = ["Dashboard", "Cleaning", "Apps", "Tools", "Disk", "Turbo", "Startup", "Resurrect"]
    observations = []
    errors = []
    navigation_measurements = []
    navigation_started = {}
    guided_cards_stable_at = None
    class DispatchErrors(logging.Handler):
        def emit(self, record):
            errors.append(record.getMessage())
    handler = DispatchErrors(level=logging.ERROR)
    dispatch_logger = logging.getLogger('modules.ui_dispatch')
    dispatch_logger.addHandler(handler)
    app.report_callback_exception = lambda kind, error, traceback: errors.append(str(error))
    args.output.mkdir(parents=True, exist_ok=True)

    def capture(index):
        name = names[index]
        started = time.perf_counter()
        navigation_started[name] = started
        app.select_frame(name)
        if args.smoke_fixture and name == "Resurrect":
            # Build every production phase before this diagnostic capture;
            # this mode does not benchmark deferred construction.
            while app._resurrection_next_index < len(app.RESURRECTION_STEPS):
                app._pause_resurrection_cards()
                app._build_resurrection_batch()
            app._pause_resurrection_cards()
        callback_ms = (time.perf_counter() - started) * 1000
        geometry_started = time.perf_counter()
        app.update_idletasks()
        geometry_ms = (time.perf_counter() - geometry_started) * 1000
        if args.focus_subviews and app.active_group in app.group_scroll:
            canvas = app.group_scroll[app.active_group]._parent_canvas
            canvas.yview_moveto(0)
            if name in ("Disk", "Startup") and app._group_stacked.get(app.active_group):
                bounds = canvas.bbox('all')
                if bounds:
                    frame = app.frames[name]
                    target = frame.winfo_rooty() - canvas.winfo_rooty()
                    canvas.yview_moveto(max(0, target / max(1, bounds[3] - bounds[1])))
        navigation_measurements.append({
            'view': name,
            'callback_ms': round(callback_ms, 1),
            'geometry_flush_ms': round(geometry_ms, 1),
            'first_navigation_ms': round(callback_ms + geometry_ms, 1)})
        app.after(700 if args.smoke_fixture else 300, lambda: save(index))

    def save(index):
        nonlocal guided_cards_stable_at
        name = names[index]
        if name == "Resurrect":
            if len(app._resurrection_rows) < len(app.RESURRECTION_STEPS):
                if time.perf_counter() - navigation_started[name] < 5:
                    app.after(25, lambda: save(index))
                    return
                errors.append("Guided maintenance cards not ready before capture")
            elif guided_cards_stable_at is None:
                # CTk canvas redraws run after Tk widget creation. Do not grab an
                # intermediate frame that contains incomplete/overlapping text.
                guided_cards_stable_at = time.perf_counter()
                app.after(500, lambda: save(index))
                return
        app.update_idletasks()
        x, y = app.winfo_rootx(), app.winfo_rooty()
        width, height = app.winfo_width(), app.winfo_height()
        if width < 640 or height < 400:
            errors.append(f'Unusable {names[index]} window: {width}x{height}')
        ImageGrab.grab(bbox=(x, y, x + width, y + height)).save(args.output / f"{names[index].lower()}.png")
        observations.append({"section": names[index], "pixels": [width, height], "widget_scale": args.scale})
        if index + 1 < len(names):
            app.after(50, lambda: capture(index + 1))
        else:
            dpi = ctypes.windll.user32.GetDpiForWindow(app.winfo_id()) if sys.platform == 'win32' else None
            sources = ['panacea_ui.py', 'version.py', 'modules/system_monitor.py', 'modules/ui_icons.py']
            for section in ('Dashboard', 'Cleaning', 'Tools', 'Turbo', 'Resurrect'):
                started = time.perf_counter()
                app.select_frame(section)
                app.update_idletasks()
                navigation_measurements.append({
                    'view': section,
                    'warm_navigation_ms': round((time.perf_counter() - started) * 1000, 1)})
            evidence = {"views": observations, "navigation_timings": navigation_measurements,
                        "language": app.language, "visual_fixture": args.smoke_fixture,
                        "focus_subviews": args.focus_subviews,
                        "performance_scope": "diagnostic capture; fixture mode eagerly builds guided cards",
                        "callback_errors": errors,
                        "scaling_method": "CTk widget simulation; window scaling fixed at 1. No Windows display setting changed.",
                        "native_window_dpi": dpi,
                        "screen_pixels": [app.winfo_screenwidth(), app.winfo_screenheight()],
                        "source_sha256": {name: hashlib.sha256((args.source / name).read_bytes()).hexdigest() for name in sources}}
            (args.output / "observations.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
            app._on_close()

    app.after(args.settle_ms, lambda: capture(0))
    app.mainloop()
    patches.close()
    dispatch_logger.removeHandler(handler)
    if errors:
        raise RuntimeError("GUI callback errors: " + "; ".join(errors))


if __name__ == "__main__":
    main()
