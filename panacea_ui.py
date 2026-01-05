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
import subprocess

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

class PanaceaApp(ctk.CTk):
    def __init__(self, root_is_deprecated_use_self):
        super().__init__()
        
        self.title("Panacea System Optimizer")
        self.geometry("950x600")
        
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
        
        self.graphs = {} # Store graph references

        self._setup_dashboard_frame()
        self._setup_cleaning_frame()
        self._setup_disk_frame()
        self._setup_tools_frame()
        self._setup_apps_frame()
        self._setup_turbo_frame()
        self._setup_resurrect_frame()
        
        self.select_frame("Dashboard")
        self.update_dashboard()
        
        # Start update check
        threading.Thread(target=self._check_updates_thread, daemon=True).start()

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
        except:
            self.icons["resurrect_negative"] = self.icons.get("resurrect")

    def _setup_sidebar(self):
        self.sidebar_frame = ctk.CTkFrame(self, width=140, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, rowspan=4, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(7, weight=1)
        
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text=" PANACEA", font=ctk.CTkFont(size=24, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(30, 20))
        
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

        # Footer
        year = datetime.now().year
        footer_text = f"© {year} Maurizio Falconi - falker47"
        self.footer_label = ctk.CTkLabel(self.sidebar_frame, text=footer_text, 
                                         font=ctk.CTkFont(size=10), text_color="gray", cursor="hand2")
        self.footer_label.grid(row=9, column=0, padx=10, pady=(10, 20), sticky="s")
        self.footer_label.bind("<Button-1>", lambda e: webbrowser.open("https://falker47.github.io/Nexus-portfolio/"))

    def select_frame(self, name):
        self.frame_dashboard.grid_forget()
        self.frame_cleaning.grid_forget()
        self.frame_disk.grid_forget()
        self.frame_tools.grid_forget()
        self.frame_apps.grid_forget()
        self.frame_turbo.grid_forget()
        self.frame_resurrect.grid_forget()
        
        if name == "Dashboard": self.frame_dashboard.grid(row=0, column=1, sticky="nsew")
        elif name == "Cleaning": self.frame_cleaning.grid(row=0, column=1, sticky="nsew")
        elif name == "Disk": self.frame_disk.grid(row=0, column=1, sticky="nsew")
        elif name == "Tools": self.frame_tools.grid(row=0, column=1, sticky="nsew")
        elif name == "Apps": self.frame_apps.grid(row=0, column=1, sticky="nsew")
        elif name == "Turbo": self.frame_turbo.grid(row=0, column=1, sticky="nsew")
        elif name == "Resurrect": self.frame_resurrect.grid(row=0, column=1, sticky="nsew")

    def _setup_dashboard_frame(self):
        self.frame_dashboard.grid_columnconfigure((0, 1), weight=1)
        
        lbl = ctk.CTkLabel(self.frame_dashboard, text="Live System Monitor", font=ctk.CTkFont(size=28, weight="bold"))
        lbl.grid(row=0, column=0, columnspan=2, padx=20, pady=(20, 20), sticky="w")
        
        # --- Card 1: System Specs ---
        self.card_sys = ctk.CTkFrame(self.frame_dashboard)
        self.card_sys.grid(row=1, column=0, padx=(20, 10), pady=10, sticky="nsew")
        ctk.CTkLabel(self.card_sys, text="System Specs & Uptime", font=ctk.CTkFont(size=15, weight="bold")).pack(pady=(15, 5))
        self.dash_os = ctk.CTkLabel(self.card_sys, text="OS: Win ...", text_color="gray")
        self.dash_os.pack()

        # Windows Update Status Chip (Moved above uptime)
        self.frame_update_status = ctk.CTkFrame(self.card_sys, fg_color="gray30", corner_radius=15, height=25)
        self.frame_update_status.pack(pady=(10, 5))
        self.lbl_update_status = ctk.CTkLabel(self.frame_update_status, text="Checking Updates...", font=ctk.CTkFont(size=12), text_color="black")
        self.lbl_update_status.pack(padx=10, pady=2)
        
        # Update Buttons (Hidden by default)
        self.btn_run_update = ctk.CTkButton(self.card_sys, text="Install Required", height=24, width=120, 
                                            fg_color="#F44336", hover_color="#C62828",
                                            command=self.run_windows_update)
        self.btn_view_optional = ctk.CTkButton(self.card_sys, text="View Optional", height=24, width=120, 
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
        self.dash_disk_val.pack(pady=5)
        self.dash_disk_perc = ctk.CTkLabel(self.card_disk, text="0%", font=ctk.CTkFont(size=20, weight="bold"))
        self.dash_disk_perc.pack(pady=5)

        # --- Card 3: CPU Graph ---
        self.card_cpu = ctk.CTkFrame(self.frame_dashboard)
        self.card_cpu.grid(row=2, column=0, padx=(20, 10), pady=10, sticky="nsew")
        ctk.CTkLabel(self.card_cpu, text="CPU Usage History", font=ctk.CTkFont(size=15, weight="bold")).pack(pady=(15, 5))
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
        self.dash_ram_val.pack(pady=5)
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
        self.clean_log = ctk.CTkTextbox(self.frame_cleaning, height=150)
        self.clean_log.grid(row=2, column=0, padx=20, pady=10, sticky="nsew")
        self.clean_log.configure(state="disabled")

    def _setup_disk_frame(self):
        self.frame_disk.grid_columnconfigure(0, weight=1)
        self.frame_disk.grid_rowconfigure(3, weight=1)
        
        ctk.CTkLabel(self.frame_disk, text="Disk Optimization", font=ctk.CTkFont(size=24, weight="bold")).grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")
        self.drives_frame = ctk.CTkScrollableFrame(self.frame_disk, label_text="Available Drives", height=60)
        self.drives_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        self.selected_drive = tk.StringVar()
        btn_frame = ctk.CTkFrame(self.frame_disk)
        btn_frame.grid(row=2, column=0, padx=20, pady=10, sticky="nsew")
        
        d_base, d_hover = self.col_disk_tuple
        
        ctk.CTkButton(btn_frame, text="Refresh Drives", fg_color=d_base, hover_color=d_hover, command=self.refresh_drives).pack(pady=5)
        # ctk.CTkButton(btn_frame, text="Optimize Selected", fg_color=d_base, hover_color=d_hover, command=self.run_optimize_drive).pack(pady=5)
        # Using a separate method invocation logic
        ctk.CTkButton(btn_frame, text="Run Optimization (Defrag/Trim)", fg_color=d_base, hover_color=d_hover, command=self.run_optimize_drive).pack(pady=5)
        ctk.CTkButton(btn_frame, text="Open Windows Defrag GUI", fg_color=d_base, hover_color=d_hover, command=self.run_dfrgui).pack(pady=5)
        
        self.disk_log = ctk.CTkTextbox(self.frame_disk, height=150)
        self.disk_log.grid(row=3, column=0, padx=20, pady=10, sticky="nsew")
        self.disk_log.configure(state="disabled")
        
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

    def _add_tool_btn(self, parent, text, desc, cmd, name, col, hover_col):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(f, text=desc, width=200, anchor="w").pack(side="left")
        ctk.CTkButton(f, text=text, fg_color=col, hover_color=hover_col, command=lambda: self.run_cmd(cmd, name)).pack(side="right", fill="x", expand=True)

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
        
        for key, label, desc, get_fn, on_fn, off_fn in toggle_config:
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
        # Load current state for each toggle
        for key, var in self.turbo_vars.items():
            try:
                if key == "power":
                    state = self.perf_mgr.get_power_plan() == "high"
                elif key == "visual":
                    state = not self.perf_mgr.get_visual_effects()
                elif key == "sysmain":
                    state = not self.perf_mgr.get_sysmain_status()
                elif key == "wsearch":
                    state = not self.perf_mgr.get_wsearch_status()
                elif key == "spooler":
                    state = not self.perf_mgr.get_spooler_status()
                else:
                    state = False
                self.after(0, lambda v=var, s=state: v.set(s))
            except:
                pass

    def _turbo_toggle_changed(self, key, on_fn, off_fn):
        state = self.turbo_vars[key].get()
        def task():
            if state:
                on_fn()
            else:
                off_fn()
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
            pass
        self.after(3000, self.update_dashboard)
        
    def _check_updates_thread(self):
        try:
            mandatory, optional, status = self.monitor.get_windows_update_status()
            self.after(0, lambda: self._update_updates_gui(mandatory, optional, status))
        except:
             self.after(0, lambda: self._update_updates_gui(-1, -1, "Check Failed"))

    def _update_updates_gui(self, mandatory, optional, status):
        self.lbl_update_status.configure(text=status)
        
        # Hide both buttons first
        self.btn_run_update.pack_forget()
        self.btn_view_optional.pack_forget()
        
        if mandatory > 0 or optional > 0:
            # Amber if only optional, Red if mandatory
            if mandatory > 0:
                self.frame_update_status.configure(fg_color="#F44336") # Red
                self.btn_run_update.pack(pady=(5, 2), before=self.dash_uptime_val)
            else:
                self.frame_update_status.configure(fg_color="#FFC107") # Amber
            
            if optional > 0:
                self.btn_view_optional.pack(pady=(2, 5), before=self.dash_uptime_val)
        elif mandatory == 0 and optional == 0:
            self.frame_update_status.configure(fg_color="#4CAF50") # Green
        else:
            self.frame_update_status.configure(fg_color="gray30") # Gray for error

    def _update_gui(self, os_info, cpu_name, uptime, t_ram, a_ram, p_ram, t_disk, f_disk, p_disk, cpu_usage, bat_perc, bat_plug):
        if self.dash_os.cget("text").startswith("OS: Win ..."):
            self.dash_os.configure(text=os_info)
            self.dash_cpu_name.configure(text=f"CPU: {cpu_name}")
        
        self.dash_uptime_val.configure(text=f"Time since restart: {uptime}")
        
        # Update CPU Graph
        self.cpu_graph.add_value(cpu_usage)
        self.dash_cpu_val.configure(text=f"{int(cpu_usage)}%")
        
        # Update RAM Graph
        self.ram_graph.add_value(p_ram)
        self.dash_ram_val.configure(text=f"{round(t_ram - a_ram, 1)} GB / {t_ram} GB")
        self.dash_ram_perc.configure(text=f"{p_ram}%")

        # Disk
        def get_color(perc):
            if perc < 60: return "#4CAF50"
            if perc < 85: return "#FFC107"
            return "#F44336"
        self.dash_disk_bar.set(p_disk / 100)
        self.dash_disk_bar.configure(progress_color=get_color(p_disk))
        self.dash_disk_val.configure(text=f"{f_disk} GB Free / {t_disk} GB")
        self.dash_disk_perc.configure(text=f"{p_disk}%")

    def log_msg(self, msg):
        self.clean_log.configure(state="normal")
        self.clean_log.insert(tk.END, msg + "\n")
        self.clean_log.see(tk.END)
        self.clean_log.configure(state="disabled")

    def log_disk_msg(self, msg):
        self.disk_log.configure(state="normal")
        self.disk_log.insert(tk.END, msg + "\n")
        self.disk_log.see(tk.END)
        self.disk_log.configure(state="disabled")

    def refresh_drives(self):
        for widget in self.drives_frame.winfo_children():
            widget.destroy()
        drives = self.disk_opt.get_drive_info()
        for d in drives:
            rb = ctk.CTkRadioButton(self.drives_frame, text=f"{d['letter']} - {d['type']}", variable=self.selected_drive, value=d['letter'])
            rb.pack(anchor="w", padx=10, pady=5)

    def run_clean_temp(self):
        def task():
            self.log_msg("Starting cleanup...")
            count, freed = self.cleanup_mgr.clean_temp_files(progress_callback=self.log_msg)
            self.log_msg(f"Finished. Deleted {count} files. Freed {freed / (1024*1024):.2f} MB.")
            messagebox.showinfo("Cleanup Complete", f"Deleted {count} files.\nFreed {freed / (1024*1024):.2f} MB.")
        threading.Thread(target=task, daemon=True).start()

    def run_empty_recycle(self):
        def task():
            self.log_msg("Emptying Recycle Bin...")
            success, msg = self.cleanup_mgr.empty_recycle_bin()
            self.log_msg(msg)
            if success: messagebox.showinfo("Success", msg)
            else: messagebox.showerror("Error", msg)
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
        if messagebox.askyesno("Confirm", f"Run {desc}?"): self.cmd_runner.run_command(cmd, desc)

    def run_launch(self, cmd, desc):
        import subprocess
        try: subprocess.Popen(cmd, shell=True)
        except Exception as e: messagebox.showerror("Error", str(e))
    
    def run_battery_report(self):
        import subprocess, os
        try:
            path = os.path.join(os.environ['USERPROFILE'], 'battery_report.html')
            subprocess.run(f'powercfg /batteryreport /output "{path}"', shell=True, check=True)
            os.startfile(path)
        except Exception as e: messagebox.showerror("Error", str(e))

    def run_create_restore(self):
        if messagebox.askyesno("Create Restore Point", "Create a Windows System Restore Point?\n(Requires Admin privileges)\nThis may take a minute."):
            def task():
                success, msg = self.restore_mgr.create_restore_point("Panacea Manual Point")
                if success: messagebox.showinfo("Success", msg)
                else: messagebox.showerror("Error", msg)
            threading.Thread(target=task, daemon=True).start()

    def run_windows_update(self):
        # Open Windows Update Settings and try to trigger scan (hidden CMD)
        try:
            import os
            os.system("start ms-settings:windowsupdate")
            # Use CREATE_NO_WINDOW to hide CMD flash
            subprocess.Popen("USOClient.exe StartInteractiveScan", shell=True, 
                             creationflags=subprocess.CREATE_NO_WINDOW)
            # Refresh update status after a delay (give time for updates to install)
            self.lbl_update_status.configure(text="Updating...")
            self.after(30000, lambda: threading.Thread(target=self._check_updates_thread, daemon=True).start())
        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch updater: {e}")

    def run_view_optional_updates(self):
        # Open Windows Update optional updates page
        try:
            import os
            os.system("start ms-settings:windowsupdate-optionalupdates")
            # Refresh update status after a delay
            self.lbl_update_status.configure(text="Checking...")
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
        subtitle = ctk.CTkLabel(hero, text="One-Click Optimization & Restoration Suite", font=ctk.CTkFont(size=14), text_color="gray")
        subtitle.pack(anchor="center")

        # Action Area
        self.action_frame = ctk.CTkFrame(self.frame_resurrect, fg_color=("gray90", "gray13"))
        self.action_frame.grid(row=1, column=0, padx=40, pady=10, sticky="ew")
        
        self.progress_bar = ctk.CTkProgressBar(self.action_frame, orientation="horizontal", height=15)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=20, pady=(20, 10))
        
        self.lbl_status = ctk.CTkLabel(self.action_frame, text="Ready to Start", font=ctk.CTkFont(size=14, weight="bold"))
        self.lbl_status.pack(pady=(5, 0))
        
        self.lbl_warning = ctk.CTkLabel(self.action_frame, text="(Process takes time. Run only when idle.)", font=ctk.CTkFont(size=11), text_color="gray70")
        self.lbl_warning.pack(pady=(0, 5))

        self.btn_resurrect_start = ctk.CTkButton(self.action_frame, text="INITIATE PROTOCOL", font=ctk.CTkFont(size=16, weight="bold"),
                                                 fg_color="#FFD700", hover_color="#B8860B", text_color="black",
                                                 height=40,
                                                 command=self.run_god_mode)
        self.btn_resurrect_start.pack(pady=20)
        
        # Log Area (Terminal Style)
        log_frame = ctk.CTkFrame(self.frame_resurrect, corner_radius=10, fg_color="black")
        log_frame.grid(row=2, column=0, padx=20, pady=20, sticky="nsew")
        
        ctk.CTkLabel(log_frame, text="> EXECUTION LOG", font=ctk.CTkFont(family="Consolas", size=12), text_color="#00FF00").pack(anchor="w", padx=10, pady=5)
        
        self.god_log = ctk.CTkTextbox(log_frame, font=ctk.CTkFont(family="Consolas", size=11), fg_color="black", text_color="#00FF00")
        self.god_log.pack(fill="both", expand=True, padx=5, pady=5)
        self.god_log.insert("0.0", "Waiting for user command...\n")
        self.god_log.configure(state="disabled")
        
        # Tag configuration for coloring
        self.god_log.tag_config("info", foreground="#00FF00") # Green
        self.god_log.tag_config("warn", foreground="#FFD700") # Gold
        self.god_log.tag_config("err", foreground="#F44336")  # Red
        self.god_log.tag_config("head", foreground="#00BFFF") # Blue

    def log_god_msg(self, msg, level="info"):
        self.god_log.configure(state="normal")
        # Check for keywords to auto-assign basic levels if untagged, or simple pass
        tag = level
        self.god_log.insert(tk.END, msg + "\n", tag)
        self.god_log.see(tk.END)
        self.god_log.configure(state="disabled")

    def run_god_mode(self):
        if not messagebox.askyesno("Confirm Resurrection", "Initiate System Resurrection Protocol?\n\nThis process is intensive and may take time.\nEnsure all work is saved."):
            return

        self.btn_resurrect_start.configure(state="disabled", text="PROTOCOL RUNNING...")
        self.lbl_status.configure(text="Initializing...", text_color="#FFD700")
        self.progress_bar.set(0)
        self.god_log.configure(state="normal"); self.god_log.delete("0.0", tk.END); self.god_log.configure(state="disabled")
        
        def sequence():
            steps = 7 # 6 phases + complete
            current_step = 0
            
            def update_progress(step_i, status_text):
                self.progress_bar.set(step_i / steps)
                self.lbl_status.configure(text=status_text)
            
            try:
                # PHASE 0: RESTORE POINT
                current_step += 1; update_progress(current_step, "Phase 1/6: Creating Restore Point (Safety)")
                self.log_god_msg("\n[PHASE 1] SAFETY BACKUP INITIATED...", "head")
                success, msg = self.restore_mgr.create_restore_point("Panacea GodMode Auto-Restore")
                if success: self.log_god_msg(f"Restore Point: {msg}", "info")
                else: self.log_god_msg(f"Restore Point Warning: {msg}", "warn")
                
                # PHASE 1
                current_step += 1; update_progress(current_step, "Phase 2/6: System Cleanup")
                self.log_god_msg("\n[PHASE 2] SYSTEM CLEANUP INITIATED...", "head")
                count, freed = self.cleanup_mgr.clean_temp_files(progress_callback=lambda m: self.log_god_msg(m, "info"))
                self.log_god_msg(f"Temp Files: Deleted {count}, Freed {freed / (1024*1024):.2f} MB", "info")
                success, msg = self.cleanup_mgr.empty_recycle_bin()
                self.log_god_msg(f"Recycle Bin: {msg}", "info")

                # PHASE 2
                current_step += 1; update_progress(current_step, "Phase 3/6: Network Reset")
                self.log_god_msg("\n[PHASE 3] NETWORK RESET INITIATED...", "head")
                self.cmd_runner.run_command_stream("ipconfig /flushdns", "DNS Flush", lambda m: self.log_god_msg(m, "info"))
                self.cmd_runner.run_command_stream("netsh winsock reset", "Winsock Reset", lambda m: self.log_god_msg(m, "info"))

                # PHASE 3
                current_step += 1; update_progress(current_step, "Phase 4/6: Disk Optimization")
                self.log_god_msg("\n[PHASE 4] DISK OPTIMIZATION (C:) INITIATED...", "head")
                self.disk_opt.analyze_optimize_drive("C:", progress_callback=lambda m: self.log_god_msg(m, "info"))

                # PHASE 4
                current_step += 1; update_progress(current_step, "Phase 5/6: System Health Check")
                self.log_god_msg("\n[PHASE 5] DISM HEALTH CHECK INITIATED...", "head")
                self.cmd_runner.run_command_stream("DISM /Online /Cleanup-Image /CheckHealth", "DISM Check", lambda m: self.log_god_msg(m, "info"))
                
                # PHASE 5
                current_step += 1; update_progress(current_step, "Phase 6/6: Integrity Scan (SFC)")
                self.log_god_msg("\n[PHASE 6] SFC INTEGRITY SCAN INITIATED (Please Wait)...", "head")
                self.cmd_runner.run_command_stream("sfc /scannow", "SFC Scan", lambda m: self.log_god_msg(m, "info"))

                current_step += 1; update_progress(current_step, "Protocol Complete")
                self.log_god_msg("\n=== RESURRECTION PROTOCOL COMPLETE ===", "head")
                self.log_god_msg("\n[!] CRITICAL ADVICE:", "warn")
                self.log_god_msg("1. Go to 'Apps' tab -> Uninstall unused programs.", "info")
                self.log_god_msg("2. Go to 'Apps' tab -> Disable unnecessary startup items.", "info")
                
                messagebox.showinfo("Success", "Resurrection Protocol Finished Successfully.\n\nA system restart is highly recommended.")

            except Exception as e:
                self.log_god_msg(f"\n[!] ERROR: {str(e)}", "err")
                self.lbl_status.configure(text="Protocol Failed", text_color="red")
                messagebox.showerror("Error", f"Sequence failed: {e}")
            
            finally:
                self.btn_resurrect_start.configure(state="normal", text="INITIATE PROTOCOL")
                self.lbl_status.configure(text="Ready", text_color="gray")

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
        
    def add_value(self, value):
        # value 0-100
        self.points.pop(0)
        self.points.append(value)
        self.draw()
        
    def draw(self):
        self.canvas.delete("all")
        w = self.width
        h = self.height
        step = w / (len(self.points) - 1)
        
        coords = []
        for i, val in enumerate(self.points):
            x = i * step
            # val is % so 100 is top (0 y), 0 is bottom (h y)
            # Actually 100% should be at y=0, 0% at y=h
            y = h - (val / 100 * h)
            coords.extend([x, y])
            
        if len(coords) >= 4:
            self.canvas.create_line(coords, fill=self.line_color, width=2, smooth=True)
