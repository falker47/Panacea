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
from modules.utils import resource_path

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
        self.frame_resurrect = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        
        self._setup_dashboard_frame()
        self._setup_cleaning_frame()
        self._setup_disk_frame()
        self._setup_tools_frame()
        self._setup_apps_frame()
        self._setup_resurrect_frame()
        
        self.select_frame("Dashboard")
        self.update_dashboard()

    def _setup_sidebar(self):
        self.sidebar_frame = ctk.CTkFrame(self, width=140, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, rowspan=4, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(7, weight=1)
        
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text=" PANACEA", font=ctk.CTkFont(size=24, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(30, 20))
        
        btn_pady = 8
        
        # Color Palette (Base, Hover)
        # Dashboard: Standard Blue
        col_dash = ("#1F6AA5", "#144870")
        # Cleaning: Indigo/Dark Azure as requested
        col_clean = ("#3949AB", "#283593") 
        # Disk: Green
        col_disk = ("#2da16f", "#1f7a52")
        # Tools: Orange (reused below)
        self.col_tools = ("#d65729", "#9e3f1d") # Saved for _setup_tools_frame
        # Apps: Purple (reused below)
        self.col_apps = ("#7b2cbf", "#521c85") # Saved for _setup_apps_frame
        
        self.sidebar_button_dashboard = ctk.CTkButton(self.sidebar_frame, text="Dashboard", height=35, anchor="w", 
                                                      fg_color=col_dash[0], hover_color=col_dash[1],
                                                      command=lambda: self.select_frame("Dashboard"))
        self.sidebar_button_dashboard.grid(row=1, column=0, padx=20, pady=btn_pady)
        
        self.sidebar_button_clean = ctk.CTkButton(self.sidebar_frame, text="Cleaning", height=35, anchor="w", 
                                                  fg_color=col_clean[0], hover_color=col_clean[1],
                                                  command=lambda: self.select_frame("Cleaning"))
        self.sidebar_button_clean.grid(row=2, column=0, padx=20, pady=btn_pady)
        
        self.sidebar_button_disk = ctk.CTkButton(self.sidebar_frame, text="Disk Opt", height=35, anchor="w", 
                                                 fg_color=col_disk[0], hover_color=col_disk[1],
                                                 command=lambda: self.select_frame("Disk"))
        self.sidebar_button_disk.grid(row=3, column=0, padx=20, pady=btn_pady)
        
        self.sidebar_button_tools = ctk.CTkButton(self.sidebar_frame, text="Tools", height=35, anchor="w", 
                                                  fg_color=self.col_tools[0], hover_color=self.col_tools[1],
                                                  command=lambda: self.select_frame("Tools"))
        self.sidebar_button_tools.grid(row=4, column=0, padx=20, pady=btn_pady)

        self.sidebar_button_apps = ctk.CTkButton(self.sidebar_frame, text="Apps", height=35, anchor="w", 
                                                 fg_color=self.col_apps[0], hover_color=self.col_apps[1],
                                                 command=lambda: self.select_frame("Apps"))
        self.sidebar_button_apps.grid(row=5, column=0, padx=20, pady=btn_pady)

        # Resurrection Button (God Mode) - Premium Style
        # Ghost button style: Transparent with Gold Border, fills on hover
        col_gold = "#FFD700" 
        self.sidebar_button_god = ctk.CTkButton(self.sidebar_frame, text="RESURRECT", height=35, anchor="w", 
                                                fg_color="transparent", 
                                                border_width=2,
                                                border_color=col_gold,
                                                text_color=col_gold,
                                                hover_color=col_gold,
                                                font=ctk.CTkFont(weight="bold"),
                                                command=lambda: self.select_frame("Resurrect"))
        self.sidebar_button_god.grid(row=6, column=0, padx=20, pady=btn_pady)

        # Fix hover text color AND border color AND background color
        # Normal: Transparent BG, Gold Border, Gold Text
        # Hover: Gold BG, Black Border, Black Text
        
        def on_enter(e):
            self.sidebar_button_god.configure(text_color="black", border_color="black", fg_color=col_gold)
            
        def on_leave(e):
            self.sidebar_button_god.configure(text_color=col_gold, border_color=col_gold, fg_color="transparent")

        self.sidebar_button_god.bind("<Enter>", on_enter)
        self.sidebar_button_god.bind("<Leave>", on_leave)

        # Saved for Cleaning Frame to match
        self.col_clean_tuple = col_clean
        # Saved for Disk Frame to match
        self.col_disk_tuple = col_disk

        # Footer
        year = datetime.now().year
        footer_text = f"© {year} Maurizio Falconi - falker47"
        self.footer_label = ctk.CTkLabel(self.sidebar_frame, text=footer_text, 
                                         font=ctk.CTkFont(size=10), text_color="gray", cursor="hand2")
        self.footer_label.grid(row=8, column=0, padx=10, pady=(10, 20), sticky="s")
        self.footer_label.bind("<Button-1>", lambda e: webbrowser.open("https://falker47.github.io/Nexus-portfolio/"))

    def select_frame(self, name):
        self.frame_dashboard.grid_forget()
        self.frame_cleaning.grid_forget()
        self.frame_disk.grid_forget()
        self.frame_tools.grid_forget()
        self.frame_apps.grid_forget()
        self.frame_resurrect.grid_forget()
        
        if name == "Dashboard": self.frame_dashboard.grid(row=0, column=1, sticky="nsew")
        elif name == "Cleaning": self.frame_cleaning.grid(row=0, column=1, sticky="nsew")
        elif name == "Disk": self.frame_disk.grid(row=0, column=1, sticky="nsew")
        elif name == "Tools": self.frame_tools.grid(row=0, column=1, sticky="nsew")
        elif name == "Apps": self.frame_apps.grid(row=0, column=1, sticky="nsew")
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
        # Removed truncation, allowing text to wrap if needed or just be long
        self.dash_cpu_name = ctk.CTkLabel(self.card_sys, text="CPU: ...", text_color="gray", wraplength=200)
        self.dash_cpu_name.pack(pady=5)
        self.dash_uptime_val = ctk.CTkLabel(self.card_sys, text="0d 0h 0m", font=ctk.CTkFont(size=18, weight="bold"), text_color="#3B8ED0")
        self.dash_uptime_val.pack(pady=5)
        ctk.CTkLabel(self.card_sys, text="(Time since restart)", font=ctk.CTkFont(size=10), text_color="gray").pack()

        # --- Card 2: CPU & Battery ---
        self.card_cpu = ctk.CTkFrame(self.frame_dashboard)
        self.card_cpu.grid(row=1, column=1, padx=(10, 20), pady=10, sticky="nsew")
        
        ctk.CTkLabel(self.card_cpu, text="CPU Usage", font=ctk.CTkFont(size=15, weight="bold")).pack(pady=(15, 0))
        self.dash_cpu_bar = ctk.CTkProgressBar(self.card_cpu, width=200, height=12)
        self.dash_cpu_bar.pack(pady=10)
        self.dash_cpu_val = ctk.CTkLabel(self.card_cpu, text="0%")
        self.dash_cpu_val.pack()

        ctk.CTkLabel(self.card_cpu, text="Battery Status", font=ctk.CTkFont(size=15, weight="bold")).pack(pady=(15, 0))
        self.dash_bat_bar = ctk.CTkProgressBar(self.card_cpu, width=200, height=12)
        self.dash_bat_bar.pack(pady=10)
        self.dash_bat_val = ctk.CTkLabel(self.card_cpu, text="Unknown")
        self.dash_bat_val.pack(pady=(0, 10))

        # --- Card 3: RAM Usage ---
        self.card_ram = ctk.CTkFrame(self.frame_dashboard)
        self.card_ram.grid(row=2, column=0, padx=(20, 10), pady=10, sticky="nsew")
        
        ctk.CTkLabel(self.card_ram, text="Memory (RAM)", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(15, 5))
        self.dash_ram_bar = ctk.CTkProgressBar(self.card_ram, width=200, height=15)
        self.dash_ram_bar.pack(pady=10)
        self.dash_ram_val = ctk.CTkLabel(self.card_ram, text="0GB / 0GB")
        self.dash_ram_val.pack(pady=5)
        self.dash_ram_perc = ctk.CTkLabel(self.card_ram, text="0%", font=ctk.CTkFont(size=20, weight="bold"))
        self.dash_ram_perc.pack(pady=5)

        # --- Card 4: Disk Usage ---
        self.card_disk = ctk.CTkFrame(self.frame_dashboard)
        self.card_disk.grid(row=2, column=1, padx=(10, 20), pady=10, sticky="nsew")
        
        ctk.CTkLabel(self.card_disk, text="Local Disk (C:)", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(15, 5))
        self.dash_disk_bar = ctk.CTkProgressBar(self.card_disk, width=200, height=15)
        self.dash_disk_bar.pack(pady=10)
        self.dash_disk_val = ctk.CTkLabel(self.card_disk, text="0GB Free")
        self.dash_disk_val.pack(pady=5)
        self.dash_disk_perc = ctk.CTkLabel(self.card_disk, text="0%", font=ctk.CTkFont(size=20, weight="bold"))
        self.dash_disk_perc.pack(pady=5)

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
        ctk.CTkLabel(grp3, text="Power", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=5)
        ctk.CTkButton(grp3, text="Generate Battery Report", fg_color=t_base, hover_color=t_hover, command=self.run_battery_report).pack(fill="x", padx=10, pady=5)

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

    def _update_gui(self, os_info, cpu_name, uptime, t_ram, a_ram, p_ram, t_disk, f_disk, p_disk, cpu_usage, bat_perc, bat_plug):
        if self.dash_os.cget("text").startswith("OS: Win ..."):
            self.dash_os.configure(text=os_info)
            # No truncation
            self.dash_cpu_name.configure(text=f"CPU: {cpu_name}")
        
        self.dash_uptime_val.configure(text=uptime)
        
        def get_color(perc):
            if perc < 60: return "#4CAF50"
            if perc < 85: return "#FFC107"
            return "#F44336"
            
        self.dash_cpu_bar.set(cpu_usage / 100)
        self.dash_cpu_bar.configure(progress_color=get_color(cpu_usage))
        self.dash_cpu_val.configure(text=f"{int(cpu_usage)}%")

        self.dash_bat_bar.set(bat_perc / 100)
        bat_col = "#4CAF50"
        if bat_perc < 20: bat_col = "#F44336"
        elif bat_perc < 40: bat_col = "#FFC107"
        self.dash_bat_bar.configure(progress_color=bat_col)
        self.dash_bat_val.configure(text=f"{bat_perc}% ({bat_plug})")

        self.dash_ram_bar.set(p_ram / 100)
        self.dash_ram_bar.configure(progress_color=get_color(p_ram))
        self.dash_ram_val.configure(text=f"{round(t_ram - a_ram, 1)} GB / {t_ram} GB")
        self.dash_ram_perc.configure(text=f"{p_ram}%")

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

    def log_god_msg(self, msg):
        self.god_log.configure(state="normal")
        self.god_log.insert(tk.END, msg + "\n")
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
            steps = 6 # 5 phases + complete
            current_step = 0
            
            def update_progress(step_i, status_text):
                self.progress_bar.set(step_i / steps)
                self.lbl_status.configure(text=status_text)
            
            try:
                # PHASE 1
                current_step += 1; update_progress(current_step, "Phase 1/5: System Cleanup")
                self.log_god_msg("\n[PHASE 1] SYSTEM CLEANUP INITIATED...")
                count, freed = self.cleanup_mgr.clean_temp_files(progress_callback=self.log_god_msg)
                self.log_god_msg(f"Temp Files: Deleted {count}, Freed {freed / (1024*1024):.2f} MB")
                success, msg = self.cleanup_mgr.empty_recycle_bin()
                self.log_god_msg(f"Recycle Bin: {msg}")

                # PHASE 2
                current_step += 1; update_progress(current_step, "Phase 2/5: Network Reset")
                self.log_god_msg("\n[PHASE 2] NETWORK RESET INITIATED...")
                self.cmd_runner.run_command_stream("ipconfig /flushdns", "DNS Flush", self.log_god_msg)
                self.cmd_runner.run_command_stream("netsh winsock reset", "Winsock Reset", self.log_god_msg)

                # PHASE 3
                current_step += 1; update_progress(current_step, "Phase 3/5: Disk Optimization")
                self.log_god_msg("\n[PHASE 3] DISK OPTIMIZATION (C:) INITIATED...")
                self.disk_opt.analyze_optimize_drive("C:", progress_callback=self.log_god_msg)

                # PHASE 4
                current_step += 1; update_progress(current_step, "Phase 4/5: System Health Check")
                self.log_god_msg("\n[PHASE 4] DISM HEALTH CHECK INITIATED...")
                self.cmd_runner.run_command_stream("DISM /Online /Cleanup-Image /CheckHealth", "DISM Check", self.log_god_msg)
                
                # PHASE 5
                current_step += 1; update_progress(current_step, "Phase 5/5: Integrity Scan (SFC)")
                self.log_god_msg("\n[PHASE 5] SFC INTEGRITY SCAN INITIATED (Please Wait)...")
                self.cmd_runner.run_command_stream("sfc /scannow", "SFC Scan", self.log_god_msg)

                current_step += 1; update_progress(current_step, "Protocol Complete")
                self.log_god_msg("\n=== RESURRECTION PROTOCOL COMPLETE ===")
                self.log_god_msg("\n[!] CRITICAL ADVICE:")
                self.log_god_msg("1. Go to 'Apps' tab -> Uninstall unused programs.")
                self.log_god_msg("2. Go to 'Apps' tab -> Disable unnecessary startup items.")
                
                messagebox.showinfo("Success", "Resurrection Protocol Finished Successfully.\n\nA system restart is highly recommended.")

            except Exception as e:
                self.log_god_msg(f"\n[!] ERROR: {str(e)}")
                self.lbl_status.configure(text="Protocol Failed", text_color="red")
                messagebox.showerror("Error", f"Sequence failed: {e}")
            
            finally:
                self.btn_resurrect_start.configure(state="normal", text="INITIATE PROTOCOL")
                self.lbl_status.configure(text="Ready", text_color="gray")

        threading.Thread(target=sequence, daemon=True).start()
