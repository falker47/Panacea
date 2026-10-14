"""Windows entry point, safe packaged smoke and update helper dispatch."""
import argparse
import ctypes
import os
import subprocess
import sys


def elevation_arguments(argv, *, frozen):
    return subprocess.list2cmdline(argv[1:] if frozen else argv)


def parse_startup_args(argv=None):
    parser = argparse.ArgumentParser(description="Panacea Windows maintenance")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--smoke-test", action="store_true", help="Open and close the GUI without maintenance or elevation")
    mode.add_argument("--panacea-update-helper", metavar="WORKSPACE")
    mode.add_argument("--panacea-update-ready", metavar="TOKEN")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_startup_args(argv)
    if args.panacea_update_helper:
        from modules.update_install import run_update_helper
        return run_update_helper(args.panacea_update_helper)

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass
    from modules.utils import is_admin
    from modules.logger import Logger
    if args.smoke_test:
        import logging
        logging.getLogger("PanaceaLogger").addHandler(logging.NullHandler())
    logger = Logger()
    logger.log("Application started.")

    if not args.smoke_test and not is_admin():
        try:
            params = elevation_arguments(sys.argv, frozen=bool(getattr(sys, "frozen", False)))
            if getattr(sys, 'frozen', False):
                # Elevation is a new application, not a worker reusing medium-token extraction.
                os.environ['PYINSTALLER_RESET_ENVIRONMENT'] = '1'
            result = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
            if result <= 32:
                raise OSError(f"Windows elevation was declined or failed (code {result}).")
            return 0
        except Exception as exc:
            logger.log(f"Failed to elevate privileges: {exc}", "ERROR")
            from tkinter import Tk, messagebox
            root = Tk()
            root.withdraw()
            messagebox.showerror("Administrator access", f"Panacea could not obtain administrator access.\n{exc}")
            root.destroy()
            return 1

    # No artificial splash timeout; the usable window is the startup feedback.
    from panacea_ui import PanaceaApp
    app = PanaceaApp()
    callback_errors = []
    smoke_dispatch_logger = smoke_dispatch_handler = None
    if args.smoke_test:
        class SmokeDispatchErrors(logging.Handler):
            def emit(self, record):
                callback_errors.append(record.getMessage())
        smoke_dispatch_logger = logging.getLogger('modules.ui_dispatch')
        smoke_dispatch_handler = SmokeDispatchErrors(level=logging.ERROR)
        smoke_dispatch_logger.addHandler(smoke_dispatch_handler)
        def smoke_error(exc_type, exc, traceback):
            callback_errors.append(str(exc))
            logger.log(f"GUI smoke callback failed: {exc}", "ERROR")
        app.report_callback_exception = smoke_error
        def check_usable_window():
            if not app.winfo_ismapped() or app.winfo_width() < 640 or app.winfo_height() < 400:
                callback_errors.append('The main window did not reach a usable size.')
        app.after(1000, check_usable_window)
    if args.panacea_update_ready:
        from modules.update_install import acknowledge_ready
        app.after(250, lambda: acknowledge_ready(sys.executable, args.panacea_update_ready))
    if args.smoke_test:
        app.after(1500, app._on_close)
    try:
        app.mainloop()
    finally:
        if smoke_dispatch_logger is not None:
            smoke_dispatch_logger.removeHandler(smoke_dispatch_handler)
    return 1 if callback_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
