"""Read-only GUI evidence harness. Never calls a maintenance action."""
import argparse
import json
import logging
import sys
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--duration", type=int, default=90)
    parser.add_argument("--width", type=int)
    parser.add_argument("--height", type=int)
    parser.add_argument("--scale", type=float, default=1)
    parser.add_argument("--section", default="Dashboard")
    args = parser.parse_args()
    sys.path.insert(0, str(args.source.resolve()))
    # Keep validation logs in the workspace; no writes to user Documents.
    logging.getLogger("PanaceaLogger").addHandler(logging.NullHandler())
    start = time.perf_counter()
    from panacea_ui import PanaceaApp
    import customtkinter as ctk
    ctk.set_widget_scaling(args.scale)
    ctk.set_window_scaling(args.scale)
    first_metric = []
    class ProbeApp(PanaceaApp):
        def _update_gui(self, *values, **kwargs):
            if not first_metric:
                first_metric.append(time.perf_counter() - start)
            return super()._update_gui(*values, **kwargs)
        def _update_fast_gui(self, *values, **kwargs):
            if not first_metric:
                first_metric.append(time.perf_counter() - start)
            return super()._update_fast_gui(*values, **kwargs)
    app = ProbeApp()
    if args.width and args.height:
        app.geometry(f"{args.width}x{args.height}")
    app.select_frame(args.section)
    results = {"source": str(args.source), "scale": args.scale, "section": args.section}
    latencies = []
    last = time.perf_counter()

    def heartbeat():
        nonlocal last
        now = time.perf_counter()
        latencies.append(max(0, now - last - 0.05) * 1000)
        last = now
        app.after(50, heartbeat)

    def ready():
        results["ready_seconds"] = time.perf_counter() - start
        results["window_pixels"] = [app.winfo_width(), app.winfo_height()]
        heartbeat()

    def finish():
        results["event_loop_delay_ms"] = latencies
        results["first_metric_seconds"] = first_metric[0] if first_metric else None
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(results, indent=2), encoding="utf-8")
        app._on_close()

    app.after(150, ready)
    app.after(args.duration * 1000, finish)
    app.mainloop()


if __name__ == "__main__":
    main()
