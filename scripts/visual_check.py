"""Render the app's own views for Windows screenshot/layout QA; no maintenance."""
import argparse
import json
import logging
import hashlib
import ctypes
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scale", type=float, default=1)
    parser.add_argument("--width", type=int, default=1100)
    parser.add_argument("--height", type=int, default=700)
    parser.add_argument("--settle-ms", type=int, default=2500,
                        help="Read-only startup settle before the first capture")
    args = parser.parse_args()
    sys.path.insert(0, str(args.source.resolve()))
    logging.getLogger("PanaceaLogger").addHandler(logging.NullHandler())
    import customtkinter as ctk
    from PIL import ImageGrab
    from panacea_ui import PanaceaApp
    ctk.set_widget_scaling(args.scale)
    ctk.set_window_scaling(1)
    app = PanaceaApp()
    app.geometry(f"{args.width}x{args.height}")
    app.attributes("-topmost", True)
    names = ["Dashboard", "Cleaning", "Apps", "Tools", "Disk", "Turbo", "Startup", "Resurrect"]
    observations = []
    errors = []
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
        app.select_frame(name)
        app.update_idletasks()
        app.after(300, lambda: save(index))

    def save(index):
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
            evidence = {"views": observations, "callback_errors": errors,
                        "scaling_method": "CTk widget simulation; window scaling fixed at 1. No Windows display setting changed.",
                        "native_window_dpi": dpi,
                        "screen_pixels": [app.winfo_screenwidth(), app.winfo_screenheight()],
                        "source_sha256": {name: hashlib.sha256((args.source / name).read_bytes()).hexdigest() for name in sources}}
            (args.output / "observations.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
            app._on_close()

    app.after(args.settle_ms, lambda: capture(0))
    app.mainloop()
    dispatch_logger.removeHandler(handler)
    if errors:
        raise RuntimeError("GUI callback errors: " + "; ".join(errors))


if __name__ == "__main__":
    main()
