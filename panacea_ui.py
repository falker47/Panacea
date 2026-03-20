import sys
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
import threading
import webbrowser
from datetime import datetime
from modules.cleanup import CleanupManager
from modules.disk import DiskOptimizer
from modules.commands import CommandRunner
from modules.logger import Logger
from modules.system_monitor import SystemMonitor
from modules.restore import RestoreManager
from modules.performance import PerformanceManager
from modules.utils import resource_path
from PIL import Image
import os
import subprocess
import urllib.request
import json
from version import VERSION, GITHUB_REPO

# Color constants
COL_GREEN = "#00FF00"
COL_GOLD = "#FFD700"
COL_RED = "#F44336"
COL_BLUE = "#00BFFF"
COL_SUCCESS = "#4CAF50"
COL_WARNING = "#FFC107"

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

class PanaceaApp(ctk.CTk):
    def __init__(self, root_is_deprecated_use_self):
        super().__init__()
        
        self.title(f"Panacea System Optimizer v{VERSION}")
        
        # Center window on screen
        window_width = 900
        window_height = 560
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # Set Icon at Runtime
        try:
            self.iconbitmap(resource_path("assets/panacea_icon.ico"))
        except Exception:
            pass # Fallback to default if fails for some reason
        
        self.logger = Logger()
        self.cleanup_mgr = CleanupManager()
        self.disk_opt = DiskOptimizer()
        self.cmd_runner = CommandRunner()
        self.monitor = SystemMonitor()
        self.restore_mgr = RestoreManager()
        self.perf_mgr = PerformanceManager()

        # Load Icons
        self._load_icons()

        # Grid Layout
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # sidebar
        self._setup_sidebar()

        # Main frames
        self.frame_dashboard = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.frame_cleaning = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.frame_disk = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.frame_tools = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.frame_apps = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.frame_turbo = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.frame_resurrect = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        

        self._setup_dashboard_frame()
        self._setup_cleaning_frame()
        self._setup_disk_frame()
        self._setup_tools_frame()
        self._setup_apps_frame()
        self._setup_turbo_frame()
        self._setup_resurrect_frame()
        
        self._dashboard_lock = threading.Lock()
        self.select_frame("Dashboard")
        self.update_dashboard()
        
        # Start update checks
        threading.Thread(target=self._check_updates_thread, daemon=True).start()
        threading.Thread(target=self._check_app_update, daemon=True).start()

    def _create_log_textbox(self, parent, height=150):
        """Create a styled terminal-like textbox with color tags."""
        log = ctk.CTkTextbox(parent, height=height, font=ctk.CTkFont(family="Consolas", size=11), fg_color="black", text_color=COL_GREEN)
        log.configure(state="disabled")
        log.tag_config("info", foreground=COL_GREEN)
        log.tag_config("warn", foreground=COL_GOLD)
        log.tag_config("err", foreground=COL_RED)
        return log

    def _log_to_widget(self, widget, msg, level="info"):
        """Append a message to a log textbox widget (thread-safe)."""
        def _do():
            widget.configure(state="normal")
            widget.insert(tk.END, msg + "\n", level)
            widget.see(tk.END)
            widget.configure(state="disabled")
        try:
            self.after(0, _do)
        except RuntimeError:
            pass

    def _load_icons(self):
        self.icons = {}
        icon_names = ["dashboard", "clean", "disk", "tools", "apps", "turbo", "resurrect"]
        for name in icon_names:
            try:
                # Assuming icons are 24x24 for sidebar
                img = Image.open(resource_path(f"assets/icons/{name}.png"))
                self.icons[name] = ctk.CTkImage(light_image=img, dark_image=img, size=(24, 24))
            except Exception as e:
                print(f"Failed to load icon {name}: {e}")
                self.icons[name] = None
        
        # Load resurrect negative icon for hover effect
        try:
            img_neg = Image.open(resource_path("assets/panacea_icon_negative.png"))
            self.icons["resurrect_negative"] = ctk.CTkImage(light_image=img_neg, dark_image=img_neg, size=(24, 24))
        except Exception:
            self.icons["resurrect_negative"] = self.icons.get("resurrect")

    def _setup_sidebar(self):
        self.sidebar_frame = ctk.CTkFrame(self, width=140, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, rowspan=4, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(7, weight=1)
        
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="Panacea", font=ctk.CTkFont(family="Google Sans", size=30, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 20))
        
        btn_pady = 8
        
        # Color Palette (Base, Hover)
        col_dash = ("#1F6AA5", "#144870")
        self.col_clean_tuple = ("#C2185B", "#880E4F")  # Dark Pink 
        self.col_disk_tuple = ("#2da16f", "#1f7a52")
        self.col_tools = ("#d65729", "#9e3f1d")
        self.col_apps = ("#7b2cbf", "#521c85")
        
        self.sidebar_button_dashboard = ctk.CTkButton(self.sidebar_frame, text="Dashboard", height=35, anchor="w", 
                                                      fg_color=col_dash[0], hover_color=col_dash[1],
                                                      image=self.icons.get("dashboard"), compound="left",
                                                      command=lambda: self.select_frame("Dashboard"))
        self.sidebar_button_dashboard.grid(row=1, column=0, padx=20, pady=btn_pady)
        
        self.sidebar_button_clean = ctk.CTkButton(self.sidebar_frame, text="Cleaning", height=35, anchor="w", 
                                                  fg_color=self.col_clean_tuple[0], hover_color=self.col_clean_tuple[1],
                                                  image=self.icons.get("clean"), compound="left",
                                                  command=lambda: self.select_frame("Cleaning"))
        self.sidebar_button_clean.grid(row=2, column=0, padx=20, pady=btn_pady)
        
        self.sidebar_button_disk = ctk.CTkButton(self.sidebar_frame, text="Disk Opt", height=35, anchor="w", 
                                                 fg_color=self.col_disk_tuple[0], hover_color=self.col_disk_tuple[1],
                                                 image=self.icons.get("disk"), compound="left",
                                                 command=lambda: self.select_frame("Disk"))
        self.sidebar_button_disk.grid(row=3, column=0, padx=20, pady=btn_pady)
        
        self.sidebar_button_tools = ctk.CTkButton(self.sidebar_frame, text="Tools", height=35, anchor="w", 
                                                  fg_color=self.col_tools[0], hover_color=self.col_tools[1],
                                                  image=self.icons.get("tools"), compound="left",
                                                  command=lambda: self.select_frame("Tools"))
        self.sidebar_button_tools.grid(row=4, column=0, padx=20, pady=btn_pady)

        self.sidebar_button_apps = ctk.CTkButton(self.sidebar_frame, text="Apps", height=35, anchor="w", 
                                                 fg_color=self.col_apps[0], hover_color=self.col_apps[1],
                                                 image=self.icons.get("apps"), compound="left",
                                                 command=lambda: self.select_frame("Apps"))
        self.sidebar_button_apps.grid(row=5, column=0, padx=20, pady=btn_pady)

        # Turbo Button
        col_turbo = ("#00BCD4", "#00838F")  # Cyan
        self.sidebar_button_turbo = ctk.CTkButton(self.sidebar_frame, text="Turbo", height=35, anchor="w", 
                                                  fg_color=col_turbo[0], hover_color=col_turbo[1],
                                                  image=self.icons.get("turbo"), compound="left",
                                                  command=lambda: self.select_frame("Turbo"))
        self.sidebar_button_turbo.grid(row=6, column=0, padx=20, pady=btn_pady)

        # Resurrection Button (God Mode)
        col_gold = "#FFD700" 
        self.sidebar_button_god = ctk.CTkButton(self.sidebar_frame, text="RESURRECT", height=35, anchor="w", 
                                                fg_color="transparent", 
                                                border_width=2,
                                                border_color=col_gold,
                                                text_color=col_gold,
                                                hover_color=col_gold,
                                                image=self.icons.get("resurrect"), compound="left",
                                                font=ctk.CTkFont(weight="bold"),
                                                command=lambda: self.select_frame("Resurrect"))
        self.sidebar_button_god.grid(row=7, column=0, padx=20, pady=btn_pady)
        
        # Color config for Resurrect Button
        def on_enter(e):
            self.sidebar_button_god.configure(text_color="black", border_color="black", fg_color=col_gold,
                                              image=self.icons.get("resurrect_negative"))
        def on_leave(e):
            self.sidebar_button_god.configure(text_color=col_gold, border_color=col_gold, fg_color="transparent",
                                              image=self.icons.get("resurrect"))

        self.sidebar_button_god.bind("<Enter>", on_enter)
        self.sidebar_button_god.bind("<Leave>", on_leave)

        # Version label
        self.version_label = ctk.CTkLabel(self.sidebar_frame, text=f"v{VERSION}",
                                          font=ctk.CTkFont(size=11), text_color="gray")
        self.version_label.grid(row=8, column=0, padx=10, pady=(10, 0), sticky="s")

        # Footer
        year = datetime.now().year
        footer_text = f"© {year} Maurizio Falconi - falker47"
        self.footer_label = ctk.CTkLabel(self.sidebar_frame, text=footer_text,
                                         font=ctk.CTkFont(size=10), text_color="gray", cursor="hand2")
        self.footer_label.grid(row=9, column=0, padx=10, pady=(2, 20), sticky="s")
        self.footer_label.bind("<Button-1>", lambda e: webbrowser.open("https://falker47.github.io/Nexus-portfolio/"))

    def select_frame(self, name):
        frame_map = {
            "Dashboard": self.frame_dashboard,
            "Cleaning": self.frame_cleaning,
            "Disk": self.frame_disk,
            "Tools": self.frame_tools,
            "Apps": self.frame_apps,
            "Turbo": self.frame_turbo,
            "Resurrect": self.frame_resurrect,
        }
        for frame in frame_map.values():
            frame.grid_forget()
        if name in frame_map:
            frame_map[name].grid(row=0, column=1, sticky="nsew")

    def _setup_dashboard_frame(self):
        self.frame_dashboard.grid_columnconfigure((0, 1), weight=1)
        
        lbl = ctk.CTkLabel(self.frame_dashboard, text="Live System Monitor", font=ctk.CTkFont(size=28, weight="bold"))
        lbl.grid(row=0, column=0, columnspan=2, padx=20, pady=(20, 20), sticky="w")
        
        # --- Card 1: System Specs ---
        self.card_sys = ctk.CTkFrame(self.frame_dashboard)
        self.card_sys.grid(row=1, column=0, padx=(20, 10), pady=10, sticky="nsew")
        ctk.CTkLabel(self.card_sys, text="System Specs & Uptime", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(15, 5))
        self.dash_os = ctk.CTkLabel(self.card_sys, text="OS: Win ...", text_color="gray")
        self.dash_os.pack()

        # Update Status Label (shows checking/up-to-date message)
        self.lbl_update_status = ctk.CTkLabel(self.card_sys, text="Looking for updates...", font=ctk.CTkFont(size=12), text_color="gray")
        self.lbl_update_status.pack(pady=(10, 5))

        # Update Buttons Row (Hidden by default, centered horizontally)
        self.btn_update_row = ctk.CTkFrame(self.card_sys, fg_color="transparent")
        
        self.btn_run_update = ctk.CTkButton(self.btn_update_row, text="Install Required", height=28, width=140, 
                                            fg_color="#F44336", hover_color="#C62828",
                                            command=self.run_windows_update)
        self.btn_view_optional = ctk.CTkButton(self.btn_update_row, text="View Optional", height=28, width=140, 
                                               fg_color="#FFC107", hover_color="#FFA000", text_color="black",
                                               command=self.run_view_optional_updates)
        
        self.dash_uptime_val = ctk.CTkLabel(self.card_sys, text="Time since restart: 0d 0h 0m", font=ctk.CTkFont(size=18, weight="bold"), text_color="#3B8ED0")
        self.dash_uptime_val.pack(pady=5)
        ctk.CTkLabel(self.card_sys, text="(Restart is recommended once a week)", font=ctk.CTkFont(size=10), text_color="gray").pack(pady=(0, 5))

        # --- Card 2: Disk Usage ---
        self.card_disk = ctk.CTkFrame(self.frame_dashboard)
        self.card_disk.grid(row=1, column=1, padx=(10, 20), pady=10, sticky="nsew")
        ctk.CTkLabel(self.card_disk, text="Disk Usage (C:)", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(15, 5))
        self.dash_disk_bar = ctk.CTkProgressBar(self.card_disk, width=200, height=15)
        self.dash_disk_bar.pack(pady=10)
        self.dash_disk_val = ctk.CTkLabel(self.card_disk, text="0GB Free")
        self.dash_disk_val.pack()
        self.dash_disk_info = ctk.CTkLabel(self.card_disk, text="", text_color="gray", font=ctk.CTkFont(size=11), wraplength=280)
        self.dash_disk_info.pack()
        self.dash_disk_perc = ctk.CTkLabel(self.card_disk, text="0%", font=ctk.CTkFont(size=20, weight="bold"))
        self.dash_disk_perc.pack(pady=5)

        # --- Card 3: CPU Graph ---
        self.card_cpu = ctk.CTkFrame(self.frame_dashboard)
        self.card_cpu.grid(row=2, column=0, padx=(20, 10), pady=10, sticky="nsew")
        ctk.CTkLabel(self.card_cpu, text="CPU Usage History", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(15, 5))
        self.cpu_graph = LiveGraph(self.card_cpu, width=300, height=80, line_color="#4CAF50")
        self.cpu_graph.pack(pady=5)
        self.dash_cpu_name = ctk.CTkLabel(self.card_cpu, text="CPU: ...", text_color="gray", wraplength=280)
        self.dash_cpu_name.pack()
        self.dash_cpu_val = ctk.CTkLabel(self.card_cpu, text="0%", font=ctk.CTkFont(size=20, weight="bold"))
        self.dash_cpu_val.pack(pady=5)

        # --- Card 4: RAM Graph ---
        self.card_ram = ctk.CTkFrame(self.frame_dashboard)
        self.card_ram.grid(row=2, column=1, padx=(10, 20), pady=10, sticky="nsew")
        ctk.CTkLabel(self.card_ram, text="Memory (RAM) History", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(15, 5))
        self.ram_graph = LiveGraph(self.card_ram, width=300, height=80, line_color="#FFC107")
        self.ram_graph.pack(pady=5)
        self.dash_ram_val = ctk.CTkLabel(self.card_ram, text="0GB / 0GB")
        self.dash_ram_val.pack()
        self.dash_ram_info = ctk.CTkLabel(self.card_ram, text="", text_color="gray", font=ctk.CTkFont(size=11))
        self.dash_ram_info.pack()
        self.dash_ram_perc = ctk.CTkLabel(self.card_ram, text="0%", font=ctk.CTkFont(size=20, weight="bold"))
        self.dash_ram_perc.pack(pady=5)

    def _setup_cleaning_frame(self):
        self.frame_cleaning.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.frame_cleaning, text="System Cleanup", font=ctk.CTkFont(size=24, weight="bold")).grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")
        btn_frame = ctk.CTkFrame(self.frame_cleaning)
        btn_frame.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        
        c_base, c_hover = self.col_clean_tuple
        
        ctk.CTkButton(btn_frame, text="Clean Temporary Files", fg_color=c_base, hover_color=c_hover, command=self.run_clean_temp).pack(fill="x", padx=20, pady=10)
        ctk.CTkButton(btn_frame, text="Empty Recycle Bin", fg_color=c_base, hover_color=c_hover, command=self.run_empty_recycle).pack(fill="x", padx=20, pady=10)
        ctk.CTkButton(btn_frame, text="Open Windows Disk Cleanup", fg_color=c_base, hover_color=c_hover, command=self.run_cleanmgr).pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(btn_frame, text="Expert Warning: Takes 10+ minutes.", text_color="orange").pack(anchor="w", padx=20, pady=(10,0))
        ctk.CTkButton(btn_frame, text="Run Deep Clean (WinSxS)", fg_color="darkred", hover_color="#800000", command=self.run_deep_clean).pack(fill="x", padx=20, pady=10)
        self.clean_log = self._create_log_textbox(self.frame_cleaning)
        self.clean_log.grid(row=2, column=0, padx=20, pady=10, sticky="nsew")

    def _setup_disk_frame(self):
        self.frame_disk.grid_columnconfigure(0, weight=1)
        # Only row 4 (log) expands
        self.frame_disk.grid_rowconfigure(4, weight=1)
        
        ctk.CTkLabel(self.frame_disk, text="Disk Optimization", font=ctk.CTkFont(size=24, weight="bold")).grid(row=0, column=0, padx=20, pady=(10, 5), sticky="w")
        
        # Compact drive selection using regular Frame (not scrollable) with horizontal layout
        drive_row = ctk.CTkFrame(self.frame_disk, fg_color="transparent")
        drive_row.grid(row=1, column=0, padx=20, pady=5, sticky="w")
        
        ctk.CTkLabel(drive_row, text="Select Drive:", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=(0, 10))
        
        self.selected_drive = tk.StringVar()
        self.drive_menu = ctk.CTkOptionMenu(drive_row, variable=self.selected_drive, values=["Loading..."], width=120)
        self.drive_menu.pack(side="left", padx=(0, 10))
        
        d_base, d_hover = self.col_disk_tuple
        ctk.CTkButton(drive_row, text="Refresh", fg_color=d_base, hover_color=d_hover, width=80, command=self.refresh_drives).pack(side="left")
        
        # Action buttons in a horizontal row
        btn_row = ctk.CTkFrame(self.frame_disk, fg_color="transparent")
        btn_row.grid(row=2, column=0, padx=20, pady=5, sticky="w")
        
        ctk.CTkButton(btn_row, text="Run Optimization (Defrag/Trim)", fg_color=d_base, hover_color=d_hover, command=self.run_optimize_drive).pack(side="left", padx=(0, 10))
        ctk.CTkButton(btn_row, text="Open Windows Defrag GUI", fg_color=d_base, hover_color=d_hover, command=self.run_dfrgui).pack(side="left")
        
        # Log takes remaining space
        self.disk_log = self._create_log_textbox(self.frame_disk)
        self.disk_log.grid(row=4, column=0, padx=20, pady=10, sticky="nsew")
        
        self.refresh_drives()

    def _setup_tools_frame(self):
        self.frame_tools.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.frame_tools, text="Advanced Tools", font=ctk.CTkFont(size=24, weight="bold")).grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")
        container = ctk.CTkScrollableFrame(self.frame_tools)
        container.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        self.frame_tools.grid_rowconfigure(1, weight=1)
        
        t_base, t_hover = self.col_tools
        
        grp1 = ctk.CTkFrame(container)
        grp1.pack(fill="x", pady=10)
        ctk.CTkLabel(grp1, text="System Integrity", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=5)
        self._add_tool_btn(grp1, "Run SFC Scan", "Scans system files.", "sfc /scannow", "SFC", t_base, t_hover)
        self._add_tool_btn(grp1, "Check Health (DISM)", "Checks system image.", "DISM /Online /Cleanup-Image /CheckHealth", "DISM Check", t_base, t_hover)
        self._add_tool_btn(grp1, "Restore Health (DISM)", "Repairs system image.", "DISM /Online /Cleanup-Image /RestoreHealth", "DISM Restore", t_base, t_hover)
        
        grp2 = ctk.CTkFrame(container)
        grp2.pack(fill="x", pady=10)
        ctk.CTkLabel(grp2, text="Network Tools", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=5)
        self._add_tool_btn(grp2, "Flush DNS", "Clears DNS cache.", "ipconfig /flushdns", "DNS", t_base, t_hover)
        self._add_tool_btn(grp2, "Reset Winsock", "Resets network adapter.", "netsh winsock reset", "Winsock", t_base, t_hover)
        
        grp3 = ctk.CTkFrame(container)
        grp3.pack(fill="x", pady=10)
        ctk.CTkLabel(grp3, text="Power & Backup", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=5)
        ctk.CTkButton(grp3, text="Generate Battery Report", fg_color=t_base, hover_color=t_hover, command=self.run_battery_report).pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(grp3, text="Create Restore Point (Now)", fg_color=t_base, hover_color=t_hover, command=self.run_create_restore).pack(fill="x", padx=10, pady=5)

        # Tools Execution Log
        ctk.CTkLabel(self.frame_tools, text="Execution Log", font=ctk.CTkFont(family="Consolas", size=12), text_color="#00FF00").grid(row=2, column=0, padx=20, pady=(5, 0), sticky="w")
        
        self.tools_log = self._create_log_textbox(self.frame_tools)
        self.tools_log.grid(row=3, column=0, padx=20, pady=10, sticky="nsew")
        
        self.frame_tools.grid_rowconfigure(3, weight=1)

    def _add_tool_btn(self, parent, text, desc, cmd, name, col, hover_col):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(f, text=desc, width=200, anchor="w").pack(side="left")
        ctk.CTkButton(f, text=text, fg_color=col, hover_color=hover_col, command=lambda: self.run_cmd(cmd, name)).pack(side="right", fill="x", expand=True)

    def log_tools_msg(self, msg):
        self._log_to_widget(self.tools_log, msg)

    def _setup_apps_frame(self):
        self.frame_apps.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.frame_apps, text="App Management", font=ctk.CTkFont(size=24, weight="bold")).grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")
        frame = ctk.CTkFrame(self.frame_apps)
        frame.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        
        a_base, a_hover = self.col_apps
        
        ctk.CTkLabel(frame, text="Uninstall Programs", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=10)
        ctk.CTkButton(frame, text="Open Settings (Apps)", fg_color=a_base, hover_color=a_hover, command=lambda: self.run_launch("start ms-settings:appsfeatures", "Settings")).pack(fill="x", padx=20, pady=5)
        ctk.CTkButton(frame, text="Open Control Panel", fg_color=a_base, hover_color=a_hover, command=lambda: self.run_launch("control appwiz.cpl", "Control Panel")).pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(frame, text="Startup", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=10)
        ctk.CTkButton(frame, text="Manage Startup Apps", fg_color=a_base, hover_color=a_hover, command=lambda: self.run_launch("start ms-settings:startupapps", "Startup")).pack(fill="x", padx=20, pady=5)

    def _setup_turbo_frame(self):
        self.frame_turbo.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(self.frame_turbo, text="Turbo Mode", font=ctk.CTkFont(size=28, weight="bold")).grid(row=0, column=0, padx=20, pady=(20, 5), sticky="w")
        ctk.CTkLabel(self.frame_turbo, text="Toggle performance settings. Changes apply immediately.", font=ctk.CTkFont(size=12), text_color="gray").grid(row=1, column=0, padx=20, pady=(0, 10), sticky="w")
        
        container = ctk.CTkScrollableFrame(self.frame_turbo)
        container.grid(row=2, column=0, padx=20, pady=10, sticky="nsew")
        self.frame_turbo.grid_rowconfigure(2, weight=1)
        
        # Store toggle variables
        self.turbo_vars = {}
        self.turbo_switches = {}
        
        # Master Toggle
        master_frame = ctk.CTkFrame(container, fg_color="#00BCD4", corner_radius=10)
        master_frame.pack(fill="x", pady=(0, 15))
        ctk.CTkLabel(master_frame, text="MASTER TOGGLE", font=ctk.CTkFont(size=14, weight="bold"), text_color="black").pack(side="left", padx=15, pady=10)
        self.master_switch = ctk.CTkSwitch(master_frame, text="Enable All", text_color="black", 
                                           command=self._master_toggle_changed)
        self.master_switch.pack(side="right", padx=15, pady=10)
        
        # Individual toggles config: (key, label, description, get_func, set_func_on, set_func_off)
        toggle_config = [
            ("power", "High Performance Power Plan", "Switch from Balanced to High Performance", 
             lambda: self.perf_mgr.get_power_plan() == "high",
             lambda: self.perf_mgr.set_power_plan(True),
             lambda: self.perf_mgr.set_power_plan(False)),
            ("visual", "Disable Visual Effects", "Turn off animations, shadows, transparency",
             lambda: not self.perf_mgr.get_visual_effects(),
             lambda: self.perf_mgr.set_visual_effects(False),
             lambda: self.perf_mgr.set_visual_effects(True)),
            ("sysmain", "Disable SysMain (Superfetch)", "Stop app pre-loading service",
             lambda: not self.perf_mgr.get_sysmain_status(),
             lambda: self.perf_mgr.set_sysmain(False),
             lambda: self.perf_mgr.set_sysmain(True)),
            ("wsearch", "Disable Windows Search", "Stop background indexing",
             lambda: not self.perf_mgr.get_wsearch_status(),
             lambda: self.perf_mgr.set_wsearch(False),
             lambda: self.perf_mgr.set_wsearch(True)),
            ("spooler", "Disable Print Spooler", "Stop print service (if no printer)",
             lambda: not self.perf_mgr.get_spooler_status(),
             lambda: self.perf_mgr.set_spooler(False),
             lambda: self.perf_mgr.set_spooler(True)),
        ]
        
        self.turbo_getters = {}
        for key, label, desc, get_fn, on_fn, off_fn in toggle_config:
            self.turbo_getters[key] = get_fn
            self._create_turbo_toggle(container, key, label, desc, get_fn, on_fn, off_fn)

        # Initial state load (in background to avoid blocking)
        threading.Thread(target=self._load_turbo_states, daemon=True).start()

    def _create_turbo_toggle(self, parent, key, label, desc, get_fn, on_fn, off_fn):
        frame = ctk.CTkFrame(parent)
        frame.pack(fill="x", pady=5)
        
        left = ctk.CTkFrame(frame, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True, padx=10, pady=10)
        ctk.CTkLabel(left, text=label, font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(left, text=desc, font=ctk.CTkFont(size=11), text_color="gray").pack(anchor="w")
        
        var = tk.BooleanVar(value=False)
        self.turbo_vars[key] = var
        
        switch = ctk.CTkSwitch(frame, text="", variable=var, 
                               command=lambda k=key, on=on_fn, off=off_fn: self._turbo_toggle_changed(k, on, off))
        switch.pack(side="right", padx=15, pady=10)
        self.turbo_switches[key] = switch

    def _load_turbo_states(self):
        for key, var in self.turbo_vars.items():
            try:
                get_fn = self.turbo_getters.get(key)
                state = get_fn() if get_fn else False
                self.after(0, lambda v=var, s=state: v.set(s))
            except Exception:
                pass

    def _turbo_toggle_changed(self, key, on_fn, off_fn):
        state = self.turbo_vars[key].get()
        def task():
            try:
                result = on_fn() if state else off_fn()
                # If result is a tuple (success, msg), check success
                if isinstance(result, tuple) and not result[0]:
                    self.after(0, lambda: self.turbo_vars[key].set(not state))
                    self.after(0, lambda: self._show_toast("Toggle Failed", str(result[1]), "error"))
            except Exception as e:
                self.after(0, lambda: self.turbo_vars[key].set(not state))
                self.after(0, lambda: self._show_toast("Toggle Failed", str(e), "error"))
        threading.Thread(target=task, daemon=True).start()

    def _master_toggle_changed(self):
        state = self.master_switch.get()
        
        # Update all toggle variables
        for key, var in self.turbo_vars.items():
            var.set(state)
        
        # Apply all changes in background
        def apply_all():
            if state:
                # Enable all turbo settings
                self.perf_mgr.set_power_plan(True)
                self.perf_mgr.set_visual_effects(False)
                self.perf_mgr.set_sysmain(False)
                self.perf_mgr.set_wsearch(False)
                self.perf_mgr.set_spooler(False)
            else:
                # Disable all turbo settings (restore defaults)
                self.perf_mgr.set_power_plan(False)
                self.perf_mgr.set_visual_effects(True)
                self.perf_mgr.set_sysmain(True)
                self.perf_mgr.set_wsearch(True)
                self.perf_mgr.set_spooler(True)
        threading.Thread(target=apply_all, daemon=True).start()

    def update_dashboard(self):
        if not self._dashboard_lock.acquire(blocking=False):
            return
        threading.Thread(target=self._update_data_thread, daemon=True).start()

    def _update_data_thread(self):
        try:
            os_info = self.monitor.get_os_info()
            cpu_name = self.monitor.get_cpu_info()
            uptime = self.monitor.get_system_uptime()
            t_ram, a_ram, p_ram = self.monitor.get_ram_usage()
            t_disk, f_disk, p_disk = self.monitor.get_disk_usage()
            cpu_usage = self.monitor.get_cpu_usage()
            bat_perc, bat_plug = self.monitor.get_battery_status()
            self.after(0, lambda: self._update_gui(os_info, cpu_name, uptime, t_ram, a_ram, p_ram, t_disk, f_disk, p_disk, cpu_usage, bat_perc, bat_plug))
        except Exception as e:
            self.logger.log(f"Dashboard update error: {e}", "WARNING")
        finally:
            self._dashboard_lock.release()
        self.after(3000, self.update_dashboard)
        
    def _check_updates_thread(self):
        try:
            mandatory, optional, status = self.monitor.get_windows_update_status()
            self.after(0, lambda: self._update_updates_gui(mandatory, optional, status))
        except Exception:
            self.after(0, lambda: self._update_updates_gui(-1, -1, "Check Failed"))

    def _update_updates_gui(self, mandatory, optional, status):
        # Hide button row first
        self.btn_update_row.pack_forget()
        self.btn_run_update.pack_forget()
        self.btn_view_optional.pack_forget()
        
        if mandatory > 0 or optional > 0:
            # Hide status label, show buttons
            self.lbl_update_status.pack_forget()
            self.btn_update_row.pack(pady=(10, 5), before=self.dash_uptime_val)
            
            if mandatory > 0:
                self.btn_run_update.configure(text=f"Install Required ({mandatory})")
                self.btn_run_update.pack(side="left", padx=5)
            
            if optional > 0:
                self.btn_view_optional.configure(text=f"View Optional ({optional})")
                self.btn_view_optional.pack(side="left", padx=5)
        elif mandatory == 0 and optional == 0:
            # System is up to date
            self.lbl_update_status.configure(text="✓ System is up to date", text_color="#4CAF50")
        else:
            # Check failed
            self.lbl_update_status.configure(text="Update check failed", text_color="gray")

    def _check_app_update(self):
        """Check GitHub releases for a newer version of Panacea."""
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            req = urllib.request.Request(url, headers={"User-Agent": "Panacea"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
            remote_tag = data.get("tag_name", "").lstrip("v")
            if remote_tag and self._is_newer(remote_tag, VERSION):
                # Find .exe asset download URL
                exe_url = None
                for asset in data.get("assets", []):
                    if asset.get("name", "").lower().endswith(".exe"):
                        exe_url = asset.get("browser_download_url")
                        break
                self.after(0, lambda: self._show_update_banner(remote_tag, exe_url))
        except Exception:
            pass

    @staticmethod
    def _is_newer(remote: str, local: str) -> bool:
        """Compare dotted version strings (e.g. '1.40' > '1.39')."""
        try:
            r_parts = [int(x) for x in remote.split(".")]
            l_parts = [int(x) for x in local.split(".")]
            return r_parts > l_parts
        except ValueError:
            return False

    def _show_update_banner(self, new_ver, exe_url):
        """Show a small banner at the top of the window for app updates."""
        banner = ctk.CTkFrame(self, fg_color="#1565C0", height=32, corner_radius=0)
        banner.grid(row=0, column=1, sticky="new", padx=0, pady=0)
        banner.lift()

        self._update_banner_lbl = ctk.CTkLabel(banner, text=f"  Panacea v{new_ver} available!",
                           font=ctk.CTkFont(size=13), text_color="white")
        self._update_banner_lbl.pack(side="left", padx=(10, 5))

        if exe_url:
            link = ctk.CTkLabel(banner, text="Install Update", font=ctk.CTkFont(size=13, underline=True),
                                text_color="#BBDEFB", cursor="hand2")
            link.pack(side="left", padx=5)
            link.bind("<Button-1>", lambda e, u=exe_url: self._auto_update(u, banner))
        else:
            link = ctk.CTkLabel(banner, text="View Release", font=ctk.CTkFont(size=13, underline=True),
                                text_color="#BBDEFB", cursor="hand2")
            link.pack(side="left", padx=5)
            link.bind("<Button-1>", lambda e: webbrowser.open(f"https://github.com/{GITHUB_REPO}/releases"))

        close_btn = ctk.CTkLabel(banner, text="✕", font=ctk.CTkFont(size=13),
                                 text_color="white", cursor="hand2", width=24)
        close_btn.pack(side="right", padx=(0, 8))
        close_btn.bind("<Button-1>", lambda e: banner.destroy())

    def _auto_update(self, exe_url, banner):
        """Download new exe, replace current, and relaunch."""
        self._update_banner_lbl.configure(text="  Downloading update...")

        def download_and_replace():
            try:
                current_exe = sys.executable
                # If running from source (python.exe), fall back to browser download
                if not current_exe.lower().endswith("panacea.exe"):
                    self.after(0, lambda: webbrowser.open(exe_url))
                    return

                # Download to temp file next to current exe
                temp_path = current_exe + ".update"
                req = urllib.request.Request(exe_url, headers={"User-Agent": "Panacea"})
                with urllib.request.urlopen(req, timeout=120) as resp:
                    with open(temp_path, "wb") as f:
                        while True:
                            chunk = resp.read(65536)
                            if not chunk:
                                break
                            f.write(chunk)

                # Create a batch script that waits for us to exit, replaces exe, and relaunches
                bat_path = current_exe + ".update.bat"
                with open(bat_path, "w") as bat:
                    bat.write(f'@echo off\n')
                    bat.write(f'echo Updating Panacea...\n')
                    bat.write(f'timeout /t 2 /nobreak >NUL\n')
                    bat.write(f'move /Y "{temp_path}" "{current_exe}"\n')
                    bat.write(f'start "" "{current_exe}"\n')
                    bat.write(f'del "%~f0"\n')

                # Launch the updater script and close the app
                self.after(0, lambda: self._launch_updater_and_exit(bat_path))

            except Exception as e:
                self.after(0, lambda: self._update_banner_lbl.configure(text=f"  Update failed: {e}"))

        threading.Thread(target=download_and_replace, daemon=True).start()

    def _launch_updater_and_exit(self, bat_path):
        """Launch the updater batch script and close the application."""
        subprocess.Popen(
            f'cmd /c "{bat_path}"',
            shell=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        self.destroy()
        sys.exit(0)

    def _show_toast(self, title, message, msg_type="info"):
        """Show a compact toast notification instead of a tall messagebox."""
        colors = {"info": "#1565C0", "success": "#2E7D32", "error": "#C62828", "warning": "#EF6C00"}
        bg = colors.get(msg_type, "#1565C0")

        toast = ctk.CTkToplevel(self)
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        toast.configure(fg_color=bg)

        # Size and position: bottom-right of parent window
        t_w, t_h = 340, 80
        try:
            px = self.winfo_rootx() + self.winfo_width() - t_w - 20
            py = self.winfo_rooty() + self.winfo_height() - t_h - 20
        except Exception:
            px, py = 100, 100
        toast.geometry(f"{t_w}x{t_h}+{px}+{py}")

        title_lbl = ctk.CTkLabel(toast, text=title, font=ctk.CTkFont(size=14, weight="bold"),
                                 text_color="white", anchor="w")
        title_lbl.pack(padx=14, pady=(10, 0), fill="x")

        msg_lbl = ctk.CTkLabel(toast, text=message, font=ctk.CTkFont(size=12),
                               text_color="#E0E0E0", anchor="w", wraplength=310)
        msg_lbl.pack(padx=14, pady=(2, 10), fill="x")

        toast.after(4000, toast.destroy)

    def _update_gui(self, os_info, cpu_name, uptime, t_ram, a_ram, p_ram, t_disk, f_disk, p_disk, cpu_usage, bat_perc, bat_plug):
        if self.dash_os.cget("text").startswith("OS: Win ..."):
            self.dash_os.configure(text=os_info)
            self.dash_cpu_name.configure(text=cpu_name)
            # Get RAM info once
            ram_info = self.monitor.get_ram_info()
            if ram_info:
                self.dash_ram_info.configure(text=ram_info)
            # Get Disk info once
            disk_model = self.monitor.get_disk_model()
            if disk_model:
                self.dash_disk_info.configure(text=disk_model)
        
        # Uptime
        new_uptime = f"Time since restart: {uptime}"
        if self.dash_uptime_val.cget("text") != new_uptime:
            self.dash_uptime_val.configure(text=new_uptime)
        
        # Update CPU Graph
        self.cpu_graph.add_value(cpu_usage)
        new_cpu_val = f"{round(cpu_usage, 1)}%"
        if self.dash_cpu_val.cget("text") != new_cpu_val:
            self.dash_cpu_val.configure(text=new_cpu_val)
        
        # Update RAM Graph
        self.ram_graph.add_value(p_ram)
        new_ram_val = f"{round(t_ram - a_ram, 1)} GB / {t_ram} GB"
        if self.dash_ram_val.cget("text") != new_ram_val:
            self.dash_ram_val.configure(text=new_ram_val)
        
        new_ram_perc = f"{round(p_ram, 1)}%"
        if self.dash_ram_perc.cget("text") != new_ram_perc:
            self.dash_ram_perc.configure(text=new_ram_perc)

        # Disk
        def get_color(perc):
            if perc < 60: return COL_SUCCESS
            if perc < 85: return COL_WARNING
            return COL_RED
        
        # ProgressBar
        current_prog = self.dash_disk_bar.get()
        target_prog = p_disk / 100
        if abs(current_prog - target_prog) > 0.01:
            self.dash_disk_bar.set(target_prog)
            
        new_color = get_color(p_disk)
        # ctk widgets don't easily expose current color, so we just set it if value changed significantly or periodically
        # To avoid flicker, we can just set it. configure might be cheap if value is same, but let's be safe
        try:
             # Access internal color if possible or just set it
             self.dash_disk_bar.configure(progress_color=new_color)
        except Exception:
            pass

        new_disk_val = f"{f_disk} GB Free / {t_disk} GB"
        if self.dash_disk_val.cget("text") != new_disk_val:
            self.dash_disk_val.configure(text=new_disk_val)
            
        new_disk_perc = f"{p_disk}%"
        if self.dash_disk_perc.cget("text") != new_disk_perc:
            self.dash_disk_perc.configure(text=new_disk_perc)

    def log_msg(self, msg):
        self._log_to_widget(self.clean_log, msg)

    def log_disk_msg(self, msg):
        self._log_to_widget(self.disk_log, msg)

    def refresh_drives(self):
        drives = self.disk_opt.get_drive_info()
        drive_values = [f"{d['letter']}" for d in drives]
        if drive_values:
            self.drive_menu.configure(values=drive_values)
            self.selected_drive.set(drive_values[0])
        else:
            self.drive_menu.configure(values=["No drives"])
            self.selected_drive.set("No drives")

    def run_clean_temp(self):
        def task():
            self.log_msg("Starting cleanup...")
            count, freed = self.cleanup_mgr.clean_temp_files(progress_callback=self.log_msg)
            if count == 0:
                self.log_msg("No temporary files found.")
                self.after(0, lambda: self._show_toast("No Cleanup Needed", "No temporary files found.", "info"))
            else:
                self.log_msg(f"Finished. Deleted {count} files. Freed {freed / (1024*1024):.2f} MB.")
                self.after(0, lambda c=count, f=freed: self._show_toast("Cleanup Complete", f"Deleted {c} files. Freed {f / (1024*1024):.2f} MB.", "success"))
        threading.Thread(target=task, daemon=True).start()

    def run_empty_recycle(self):
        def task():
            self.log_msg("Emptying Recycle Bin...")
            success, msg = self.cleanup_mgr.empty_recycle_bin()
            self.log_msg(msg)
            if success: self.after(0, lambda m=msg: self._show_toast("Success", m, "success"))
            else: self.after(0, lambda m=msg: self._show_toast("Error", m, "error"))
        threading.Thread(target=task, daemon=True).start()

    def run_cleanmgr(self):
        self.cleanup_mgr.open_disk_cleanup()
        self.log_msg("Opened Disk Cleanup.")

    def run_deep_clean(self):
        if messagebox.askyesno("Deep Clean Warning", "Run DISM Component Store Cleanup?\nTarget: WinSxS.\nTime: 10-20mins.\n\nProceed?"):
             self.cmd_runner.run_command("DISM /Online /Cleanup-Image /StartComponentCleanup", "Deep Clean")

    def run_optimize_drive(self):
        letter = self.selected_drive.get()
        if not letter: messagebox.showwarning("Selection", "Select a drive."); return
        
        def task():
            self.log_disk_msg("--- Optimization Task Started ---")
            self.disk_opt.analyze_optimize_drive(letter, progress_callback=self.log_disk_msg)
            self.log_disk_msg("--- Optimization Task Finished ---")
            
        if messagebox.askyesno("Confirm", f"Optimize {letter}?"): 
            threading.Thread(target=task, daemon=True).start()

    def run_dfrgui(self): self.disk_opt.open_optimize_gui()

    def run_cmd(self, cmd, desc):
        """Runs command streaming to tools log instead of external window"""
        # Ensure user confirms first
        if not messagebox.askyesno("Confirm", f"Run {desc}?"): return
            
        def task():
            self.log_tools_msg(f"\n> RUNNING: {desc}...")
            # Use run_command_stream and pass our logger
            self.cmd_runner.run_command_stream(cmd, desc, self.log_tools_msg)
            self.log_tools_msg(f"> FINISHED: {desc}")
        
        threading.Thread(target=task, daemon=True).start()

    def run_launch(self, cmd, desc):
        try: subprocess.Popen(cmd, shell=True)
        except Exception as e: messagebox.showerror("Error", str(e))
    
    def run_battery_report(self):
        try:
            path = os.path.join(os.environ['USERPROFILE'], 'battery_report.html')
            subprocess.run(f'powercfg /batteryreport /output "{path}"', shell=True, check=True)
            os.startfile(path)
        except Exception as e: messagebox.showerror("Error", str(e))

    def run_create_restore(self):
        if messagebox.askyesno("Create Restore Point", "Create a Windows System Restore Point?\n(Requires Admin privileges)\nThis may take a minute."):
            def task():
                success, msg = self.restore_mgr.create_restore_point("Panacea Manual Point")
                if success: self.after(0, lambda m=msg: self._show_toast("Success", m, "success"))
                else: self.after(0, lambda m=msg: self._show_toast("Error", m, "error"))
            threading.Thread(target=task, daemon=True).start()

    def run_windows_update(self):
        try:
            subprocess.Popen("start ms-settings:windowsupdate", shell=True)
            # Use CREATE_NO_WINDOW to hide CMD flash
            subprocess.Popen("USOClient.exe StartInteractiveScan", shell=True, 
                             creationflags=subprocess.CREATE_NO_WINDOW)
            # Hide buttons, show status and refresh after delay
            self.btn_update_row.pack_forget()
            self.lbl_update_status.configure(text="Updating... please wait", text_color="gray")
            self.lbl_update_status.pack(pady=(10, 5), before=self.dash_uptime_val)
            self.after(30000, lambda: threading.Thread(target=self._check_updates_thread, daemon=True).start())
        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch updater: {e}")

    def run_view_optional_updates(self):
        try:
            subprocess.Popen("start ms-settings:windowsupdate-optionalupdates", shell=True)
            # Refresh update status after a delay
            self.btn_update_row.pack_forget()
            self.lbl_update_status.configure(text="Looking for updates...", text_color="gray")
            self.lbl_update_status.pack(pady=(10, 5), before=self.dash_uptime_val)
            self.after(30000, lambda: threading.Thread(target=self._check_updates_thread, daemon=True).start())
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open settings: {e}")

    def _setup_resurrect_frame(self):
        self.frame_resurrect.grid_columnconfigure(0, weight=1)
        self.frame_resurrect.grid_rowconfigure(2, weight=1)
        
        # Hero Section
        hero = ctk.CTkFrame(self.frame_resurrect, fg_color="transparent")
        hero.grid(row=0, column=0, padx=20, pady=20, sticky="ew")
        
        title = ctk.CTkLabel(hero, text="SYSTEM RESURRECTION", font=ctk.CTkFont(size=32, weight="bold"), text_color="#FFD700")
        title.pack(anchor="center")
        subtitle = ctk.CTkLabel(hero, text="Advanced Safety Protocol & Deep Optimization", font=ctk.CTkFont(size=14), text_color="gray")
        subtitle.pack(anchor="center")

        # Action Area
        self.action_frame = ctk.CTkFrame(self.frame_resurrect, fg_color=("gray90", "gray13"))
        self.action_frame.grid(row=1, column=0, padx=40, pady=10, sticky="ew")
        
        # Larger Progress Bar with Gold Theme
        self.progress_bar = ctk.CTkProgressBar(self.action_frame, orientation="horizontal", height=20, progress_color="#FFD700")
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=20, pady=(20, 10))
        
        self.lbl_status = ctk.CTkLabel(self.action_frame, text="Ready to Start", font=ctk.CTkFont(size=14, weight="bold"))
        self.lbl_status.pack(pady=(5, 0))
        
        self.lbl_warning = ctk.CTkLabel(self.action_frame, text="(Includes: Auto System Restore, Browser Cleanup, Disk Health Scan)", font=ctk.CTkFont(size=11), text_color="gray70")
        self.lbl_warning.pack(pady=(0, 5))

        self.btn_resurrect_start = ctk.CTkButton(self.action_frame, text="INITIATE PROTOCOL", font=ctk.CTkFont(size=16, weight="bold"),
                                             fg_color="#FFD700", hover_color="#B8860B", text_color="black",
                                             height=40,
                                             command=self.run_god_mode)
        self.btn_resurrect_start.pack(pady=20)
        
        # Log Area (Terminal Style)
        log_frame = ctk.CTkFrame(self.frame_resurrect, corner_radius=10, fg_color="black")
        log_frame.grid(row=2, column=0, padx=20, pady=10, sticky="nsew")
        
        ctk.CTkLabel(log_frame, text="> EXECUTION LOG", font=ctk.CTkFont(family="Consolas", size=12), text_color="#00FF00").pack(anchor="w", padx=10, pady=5)
        
        self.god_log = self._create_log_textbox(log_frame)
        self.god_log.tag_config("head", foreground=COL_BLUE)
        self.god_log.pack(fill="both", expand=True, padx=5, pady=5)
        self.god_log.configure(state="normal")
        self.god_log.insert("0.0", "Waiting for user command...\n")
        self.god_log.configure(state="disabled")

    def log_god_msg(self, msg, level="info"):
        self._log_to_widget(self.god_log, msg, level)

    def run_god_mode(self):
        if not messagebox.askyesno("Confirm Resurrection", "Initiate System Resurrection Protocol?\n\nThis process is intensive and may take time.\nEnsure all work is saved."):
            return

        self.btn_resurrect_start.configure(state="disabled", text="PROTOCOL RUNNING...")
        self.lbl_status.configure(text="Initializing...", text_color="#FFD700")
        self.progress_bar.set(0)
        self.god_log.configure(state="normal"); self.god_log.delete("0.0", tk.END); self.god_log.configure(state="disabled")
        
        # Filters for Cleaner Output
        def health_filter(line):
            # SFC / DISM / CHKDSK filter
            bad_phrases = [
                "Avvio in corso", "Attendere", "L'operazione richieder", "100%", "completed", "Avanzamento:", "ETA:", "Fase:", "totale:", "percent complete",
                # CHKDSK Noise
                "Il file system", "etichetta del volume", "Durata fase", "Verifica file", "Verifica indici", "Verifica descrittori", "journal USN",
                "KB di spazio", "KB in", "KB occupati", "KB disponibili", "byte in ogni", "unit", "allocazione"
            ]
            # Keep final results or phase indicators, drop progress noise if needed or verbose intros
            for phrase in bad_phrases:
                if phrase in line: return False
            if line.strip() == "": return False
            return True
            
        def sequence():
            steps = 8 # Safety, Browser, Cleanup, Network, Disk Opt, Disk Scan, Health, Verification
            current_step = 0
            
            def update_progress(step_i, status_text):
                self.after(0, lambda s=step_i, t=status_text: (
                    self.progress_bar.set(s / steps),
                    self.lbl_status.configure(text=t)
                ))
            
            try:
                # PHASE 1: SAFETY (Auto-Enable Restore)
                current_step += 1; update_progress(current_step, "Phase 1: Safety Backup")
                self.log_god_msg("\n[PHASE 1] SAFETY BACKUP INITIATED...", "head")
                
                # Verify/Enable System Restore first
                self.log_god_msg("Verifying System Restore state...", "info")
                self.restore_mgr.ensure_restore_enabled("C:\\")
                
                success, msg = self.restore_mgr.create_restore_point("Panacea GodMode Auto-Restore")
                if success: self.log_god_msg(f"Restore Point: {msg}", "info")
                else: self.log_god_msg(f"Restore Point Warning: {msg}", "warn")
                
                # PHASE 2: BROWSER CLEANUP
                current_step += 1; update_progress(current_step, "Phase 2: Browser Cleanup")
                self.log_god_msg("\n[PHASE 2] BROWSER CLEANUP...", "head")
                bc_count, bc_size = self.cleanup_mgr.clean_browser_caches()
                self.log_god_msg(f"Browser Cache: Cleared {bc_count} files ({bc_size / (1024*1024):.2f} MB)", "info")

                # PHASE 3: SYSTEM CLEANUP
                current_step += 1; update_progress(current_step, "Phase 3: System Junk Cleanup")
                self.log_god_msg("\n[PHASE 3] SYSTEM JUNK CLEANUP...", "head")
                count, freed = self.cleanup_mgr.clean_temp_files(progress_callback=lambda m: self.log_god_msg(m, "info"))
                self.log_god_msg(f"Temp Files: Deleted {count}, Freed {freed / (1024*1024):.2f} MB", "info")
                success, msg = self.cleanup_mgr.empty_recycle_bin()
                self.log_god_msg(f"Recycle Bin: {msg}", "info")

                # PHASE 4: NETWORK
                current_step += 1; update_progress(current_step, "Phase 4: Network Reset")
                self.log_god_msg("\n[PHASE 4] NETWORK RESET...", "head")
                self.cmd_runner.run_command_stream("ipconfig /flushdns", "DNS Flush", lambda m: self.log_god_msg(m, "info"))
                self.cmd_runner.run_command_stream("netsh winsock reset", "Winsock Reset", lambda m: self.log_god_msg(m, "info"))

                # PHASE 5: DISK OPTIMIZATION
                current_step += 1; update_progress(current_step, "Phase 5: Disk Defrag/Trim")
                self.log_god_msg("\n[PHASE 5] DISK OPTIMIZATION (C:)...", "head")
                self.disk_opt.analyze_optimize_drive("C:", progress_callback=lambda m: self.log_god_msg(m, "info"))

                # PHASE 6: DISK HEALTH
                current_step += 1; update_progress(current_step, "Phase 6: Disk Health Scan")
                self.log_god_msg("\n[PHASE 6] DISK HEALTH CHECK (CHKDSK)...", "head")
                # /scan runs online (no reboot), /perf speeds it up
                self.cmd_runner.run_command_stream("chkdsk C: /scan /perf", "CHKDSK", lambda m: self.log_god_msg(m, "info"), filter_func=health_filter)

                # PHASE 7: SYSTEM IMAGE HEALTH
                current_step += 1; update_progress(current_step, "Phase 7: DISM Health Check")
                self.log_god_msg("\n[PHASE 7] DISM IMAGE HEALTH...", "head")
                self.cmd_runner.run_command_stream("DISM /Online /Cleanup-Image /CheckHealth", "DISM Check", lambda m: self.log_god_msg(m, "info"), filter_func=health_filter)
                
                # PHASE 8: SFC (skipped for speed if preferred, but kept for god mode)
                current_step += 1; update_progress(current_step, "Phase 8: Integrity Scan (SFC)")
                self.log_god_msg("\n[PHASE 8] SFC INTEGRITY SCAN...", "head")
                self.cmd_runner.run_command_stream("sfc /scannow", "SFC Scan", lambda m: self.log_god_msg(m, "info"), filter_func=health_filter)

                update_progress(steps, "Protocol Complete")
                self.log_god_msg("\n=== RESURRECTION PROTOCOL COMPLETE ===", "head")
                
                # Final Tip
                self.log_god_msg("\n[TIP] For best results: Uninstall useless programs and manage startup apps from the APPS tab and then restart your PC.", "warn")
                
                self.after(0, lambda: self._show_toast("Success", "Resurrection Protocol Finished. A system restart is highly recommended.", "success"))

            except Exception as e:
                self.log_god_msg(f"\n[!] ERROR: {str(e)}", "err")
                self.after(0, lambda: self.lbl_status.configure(text="Protocol Failed", text_color="red"))
                self.after(0, lambda: messagebox.showerror("Error", f"Sequence failed: {e}"))

            finally:
                self.after(0, lambda: self.btn_resurrect_start.configure(state="normal", text="INITIATE PROTOCOL"))
                self.after(0, lambda: self.lbl_status.configure(text="Ready", text_color="gray"))

        threading.Thread(target=sequence, daemon=True).start()
class LiveGraph(ctk.CTkFrame):
    def __init__(self, master, width=200, height=80, line_color="#00EE00", **kwargs):
        super().__init__(master, **kwargs)
        self.canvas = ctk.CTkCanvas(self, width=width, height=height, bg="#1a1a1a", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.width = width
        self.height = height
        self.line_color = line_color
        self.points = [0] * (width // 5) # one point every 5 pixels
        
        # Create persistent line object
        self.line_id = self.canvas.create_line(0,0,0,0, fill=self.line_color, width=2, smooth=True)
        
    def add_value(self, value):
        # value 0-100
        self.points.pop(0)
        self.points.append(value)
        self.draw()
        
    def draw(self):
        w = self.width
        h = self.height
        step = w / (len(self.points) - 1)
        
        coords = []
        for i, val in enumerate(self.points):
            x = i * step
            # val is % so 100 is top (0 y), 0 is bottom (h y)
            y = h - (val / 100 * h)
            coords.extend([x, y])
            
        if len(coords) >= 4:
            self.canvas.coords(self.line_id, *coords)
