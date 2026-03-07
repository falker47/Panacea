import sys
import ctypes
import os
from tkinter import Tk, messagebox
from modules.utils import is_admin
from modules.logger import Logger
from modules.theme import APP_VERSION, Colors


def main():
    logger = Logger()
    logger.log("Application started.")

    if not is_admin():
        logger.log("Not running as admin. Attempting to elevate.", "WARNING")
        try:
            params = " ".join([f'"{arg}"' for arg in sys.argv[1:]])
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, f'"{sys.argv[0]}" {params}', None, 1)
            sys.exit(0)
        except Exception as e:
            logger.log(f"Failed to elevate privileges: {e}", "ERROR")
            root = Tk()
            root.withdraw()
            messagebox.showerror("Error", f"Failed to restart as administrator.\n{e}")
            sys.exit(1)

    logger.log("Running with admin privileges.")

    # --- Splash Screen with Progress Bar ---
    import tkinter as tk
    from PIL import Image, ImageTk
    from modules.utils import resource_path

    splash = tk.Tk()
    splash.overrideredirect(True)
    splash.attributes("-topmost", True)
    splash.configure(bg=Colors.BG_PRIMARY)

    try:
        img = Image.open(resource_path("assets/panacea.webp"))
        img.thumbnail((500, 350), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(img)

        w, h = img.size
        total_h = h + 50
        x = (splash.winfo_screenwidth() - w) // 2
        y = (splash.winfo_screenheight() - total_h) // 2
        splash.geometry(f"{w}x{total_h}+{x}+{y}")

        # Image
        img_label = tk.Label(splash, image=photo, bd=0, bg=Colors.BG_PRIMARY)
        img_label.pack()

        # Version + progress area
        bottom = tk.Frame(splash, bg=Colors.BG_PRIMARY)
        bottom.pack(fill="x", padx=30, pady=(8, 12))

        ver_label = tk.Label(bottom, text=f"v{APP_VERSION}",
                             font=("Segoe UI", 9), fg="gray", bg=Colors.BG_PRIMARY)
        ver_label.pack(anchor="w")

        # Progress bar (Canvas-based)
        bar_w = w - 60
        bar_canvas = tk.Canvas(bottom, width=bar_w, height=4,
                               bg="#333333", highlightthickness=0, bd=0)
        bar_canvas.pack(pady=(4, 0))
        progress_rect = bar_canvas.create_rectangle(0, 0, 0, 4,
                                                    fill=Colors.DASH[0], outline="")

        steps = 25
        step_time = 60

        def animate(step):
            if step <= steps:
                fill_w = int(bar_w * (step / steps))
                bar_canvas.coords(progress_rect, 0, 0, fill_w, 4)
                splash.after(step_time, animate, step + 1)
            else:
                splash.destroy()

        splash.after(100, animate, 1)
        splash.mainloop()

    except Exception as e:
        logger.log(f"Splash screen failed: {e}", "WARNING")
        try:
            splash.destroy()
        except Exception:
            pass

    # --- Main App ---
    from panacea_ui import PanaceaApp
    app = PanaceaApp(None)
    app.mainloop()


if __name__ == "__main__":
    main()
