import sys
import ctypes
import os
from tkinter import Tk, messagebox
from modules.utils import is_admin
from modules.logger import Logger
from panacea_ui import PanaceaApp

def main():
    logger = Logger()
    logger.log("Application started.")

    if not is_admin():
        logger.log("Not running as admin. Attempting to elevate.", "WARNING")
        # Re-run the program with admin rights
        try:
            # sys.executable is the python interpreter
            # sys.argv[0] is the script path
            # params is the rest of the arguments
            params = " ".join([f'"{arg}"' for arg in sys.argv[1:]])
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{sys.argv[0]}" {params}', None, 1)
            sys.exit(0)
        except Exception as e:
            logger.log(f"Failed to elevate privileges: {e}", "ERROR")
            root = Tk()
            root.withdraw()
            messagebox.showerror("Error", f"Failed to restart as administrator.\n{e}")
            sys.exit(1)
    
    logger.log("Running with admin privileges.")
    
    # --- Splash Screen ---
    import tkinter as tk
    from PIL import Image, ImageTk
    from modules.utils import resource_path
    
    splash = tk.Tk()
    splash.overrideredirect(True)  # No title bar
    splash.attributes("-topmost", True)
    
    # Load splash image
    try:
        img = Image.open(resource_path("assets/panacea.webp"))
        # Resize if needed (maintain aspect ratio, max 600px wide)
        img.thumbnail((600, 400), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(img)
        
        # Center the splash on screen
        w, h = img.size
        x = (splash.winfo_screenwidth() - w) // 2
        y = (splash.winfo_screenheight() - h) // 2
        splash.geometry(f"{w}x{h}+{x}+{y}")
        
        label = tk.Label(splash, image=photo, bd=0)
        label.pack()
        
        splash.update()
        splash.after(1000, splash.destroy)  # Show for 1 second
        splash.mainloop()
    except Exception as e:
        logger.log(f"Splash screen failed: {e}", "WARNING")
        splash.destroy()
    
    # --- Main App ---
    app = PanaceaApp(None)
    app.mainloop()

if __name__ == "__main__":
    main()
