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
    
    # CustomTkinter apps don't need a root Tk() passed in usually if they inherit from CTk
    # But our code was `app = PanaceaApp(root)`. 
    # The new code is `class PanaceaApp(ctk.CTk):` so we instantiate it directly.
    
    app = PanaceaApp(None)
    app.mainloop()

if __name__ == "__main__":
    main()
