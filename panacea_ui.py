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
from modules.theme import (
    APP_VERSION, APP_NAME, Colors, Fonts, Spacing, Dimensions
)
from PIL import Image
import subprocess

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")


# ---------------------------------------------------------------------------
# Toast Notification
# ---------------------------------------------------------------------------
class ToastNotification(ctk.CTkFrame):
    """In-app toast notification that appears in the top-right corner."""

    _active_toast = None  # Class-level tracker

    def __init__(self, master, message, level="info", duration=4000):
        color_map = {
            "info": Colors.INFO,
            "success": Colors.SUCCESS,
            "warning": Colors.WARNING,
            "error": Colors.ERROR,
        }
        accent = color_map.get(level, Colors.INFO)

        super().__init__(master, fg_color="#2b2b2b", corner_radius=10,
                         border_color=accent, border_width=2)

        # Left accent bar
        accent_bar = ctk.CTkFrame(self, width=4, fg_color=accent, corner_radius=0)
        accent_bar.pack(side="left", fill="y", padx=(0, 8))

        # Message
        lbl = ctk.CTkLabel(self, text=message, font=ctk.CTkFont(size=13),
                           text_color="white", wraplength=380, justify="left")
        lbl.pack(side="left", padx=(4, 16), pady=12)

        # Close button
        close_btn = ctk.CTkButton(self, text="x", width=24, height=24,
                                  fg_color="transparent", hover_color="#444",
                                  command=self._dismiss)
        close_btn.pack(side="right", padx=8, pady=8)

        # Position in top-right
        self.place(relx=1.0, rely=0.0, x=-20, y=20, anchor="ne")
        self.lift()

        # Dismiss previous toast
        if ToastNotification._active_toast is not None:
            try:
                ToastNotification._active_toast.destroy()
            except Exception:
                pass
        ToastNotification._active_toast = self

        self._dismiss_after_id = self.after(duration, self._dismiss)

    def _dismiss(self):
        try:
            self.after_cancel(self._dismiss_after_id)
        except (ValueError, AttributeError):
            pass
        if ToastNotification._active_toast is self:
            ToastNotification._active_toast = None
        self.destroy()


# ---------------------------------------------------------------------------
# Live Graph
# ---------------------------------------------------------------------------
class LiveGraph(ctk.CTkFrame):
    def __init__(self, master, width=350, height=100, line_color="#00EE00", **kwargs):
        super().__init__(master, **kwargs)
        self.canvas = ctk.CTkCanvas(self, width=width, height=height,
                                    bg=Colors.BG_PRIMARY, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.graph_width = width
        self.graph_height = height
        self.line_color = line_color
        self.points = [0] * (width // 5)

        # Compute fill color (blend line_color 30% with bg)
        self.fill_color = self._blend(line_color, Colors.BG_PRIMARY, 0.30)

        # Grid lines
        self._draw_grid()

        # Fill polygon (behind line)
        self.fill_id = self.canvas.create_polygon(0, 0, fill=self.fill_color,
                                                  outline="", stipple="gray25")
        # Data line
        self.line_id = self.canvas.create_line(0, 0, 0, 0, fill=self.line_color,
                                               width=2, smooth=True)

    @staticmethod
    def _blend(fg_hex, bg_hex, alpha):
        r1, g1, b1 = int(fg_hex[1:3], 16), int(fg_hex[3:5], 16), int(fg_hex[5:7], 16)
        r2, g2, b2 = int(bg_hex[1:3], 16), int(bg_hex[3:5], 16), int(bg_hex[5:7], 16)
        r = int(r1 * alpha + r2 * (1 - alpha))
        g = int(g1 * alpha + g2 * (1 - alpha))
        b = int(b1 * alpha + b2 * (1 - alpha))
        return f"#{r:02x}{g:02x}{b:02x}"

    def _draw_grid(self):
        h, w = self.graph_height, self.graph_width
        for pct in [25, 50, 75]:
            y = h - (pct / 100 * h)
            self.canvas.create_line(0, y, w, y, fill=Colors.GRAPH_GRID, dash=(2, 4))
            self.canvas.create_text(w - 4, y - 8, text=f"{pct}%",
                                    fill=Colors.GRAPH_LABEL, font=("Segoe UI", 7), anchor="e")

    def add_value(self, value):
        self.points.pop(0)
        self.points.append(value)
        self._redraw()

    def _redraw(self):
        w = self.graph_width
        h = self.graph_height
        n = len(self.points)
        step = w / (n - 1) if n > 1 else w

        coords = []
        for i, val in enumerate(self.points):
            x = i * step
            y = h - (val / 100 * h)
            coords.extend([x, y])

        if len(coords) >= 4:
            self.canvas.coords(self.line_id, *coords)
            fill_coords = list(coords) + [w, h, 0, h]
            self.canvas.coords(self.fill_id, *fill_coords)


# ---------------------------------------------------------------------------
# Main Application
# ---------------------------------------------------------------------------
class PanaceaApp(ctk.CTk):
    def __init__(self, root_is_deprecated_use_self):
        super().__init__()

        self.title(f"{APP_NAME} v{APP_VERSION}")

        # Center and size window
        w, h = Dimensions.WINDOW_WIDTH, Dimensions.WINDOW_HEIGHT
        sx = self.winfo_screenwidth()
        sy = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sx - w) // 2}+{(sy - h) // 2}")
        self.minsize(Dimensions.MIN_WIDTH, Dimensions.MIN_HEIGHT)

        # Icon
        try:
            self.iconbitmap(resource_path("assets/panacea_icon.ico"))
        except Exception:
            pass

        # Managers
        self.logger = Logger()
        self.cleanup_mgr = CleanupManager()
        self.disk_opt = DiskOptimizer()
        self.cmd_runner = CommandRunner()
        self.monitor = SystemMonitor()
        self.restore_mgr = RestoreManager()
        self.perf_mgr = PerformanceManager()

        # Icons
        self._load_icons()

        # Grid: sidebar col0, content col1
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self._setup_sidebar()

        # Content frames
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

        self.select_frame("Dashboard")
        self.update_dashboard()

        # Background: check for Windows updates
        threading.Thread(target=self._check_updates_thread, daemon=True).start()

    # -----------------------------------------------------------------------
    # Icons
    # -----------------------------------------------------------------------
    def _load_icons(self):
        self.icons = {}
        icon_names = ["dashboard", "clean", "disk", "tools", "apps", "turbo", "resurrect"]
        for name in icon_names:
            try:
                img = Image.open(resource_path(f"assets/icons/{name}.png"))
                self.icons[name] = ctk.CTkImage(light_image=img, dark_image=img, size=(24, 24))
            except Exception:
                self.icons[name] = None

        try:
            img_neg = Image.open(resource_path("assets/panacea_icon_negative.png"))
            self.icons["resurrect_negative"] = ctk.CTkImage(light_image=img_neg, dark_image=img_neg, size=(24, 24))
        except Exception:
            self.icons["resurrect_negative"] = self.icons.get("resurrect")

    # -----------------------------------------------------------------------
    # Sidebar
    # -----------------------------------------------------------------------
    def _setup_sidebar(self):
        self.sidebar_frame = ctk.CTkFrame(self, width=Spacing.SIDEBAR_WIDTH, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(8, weight=1)  # Push footer down
        self.sidebar_frame.grid_columnconfigure(0, weight=0)  # Indicator col: fixed
        self.sidebar_frame.grid_columnconfigure(1, weight=1)  # Buttons col: expand

        # Logo
        self.logo_label = ctk.CTkLabel(
            self.sidebar_frame, text="Panacea",
            font=ctk.CTkFont(*Fonts.LOGO))
        self.logo_label.grid(row=0, column=0, columnspan=2, padx=20, pady=(20, 4))

        # Subtitle
        ctk.CTkLabel(
            self.sidebar_frame, text="System Optimizer",
            font=ctk.CTkFont(size=10), text_color=Colors.TEXT_MUTED
        ).grid(row=1, column=0, columnspan=2, padx=20, pady=(0, 16))

        pad_y = Spacing.SIDEBAR_BTN_PAD_Y
        btn_h = Spacing.SIDEBAR_BTN_HEIGHT

        # Sidebar buttons config: (row, name, label, icon_key, colors)
        btn_config = [
            (2, "Dashboard", "Dashboard", "dashboard", Colors.DASH),
            (3, "Cleaning", "Cleaning", "clean", Colors.CLEAN),
            (4, "Disk", "Disk Opt", "disk", Colors.DISK),
            (5, "Tools", "Tools", "tools", Colors.TOOLS),
            (6, "Apps", "Apps", "apps", Colors.APPS),
            (7, "Turbo", "Turbo", "turbo", Colors.TURBO),
        ]

        self.sidebar_buttons = {}
        for row, name, label, icon_key, colors in btn_config:
            btn = ctk.CTkButton(
                self.sidebar_frame, text=label, height=btn_h, anchor="w",
                fg_color="transparent", hover_color=colors[1],
                text_color="gray70",
                image=self.icons.get(icon_key), compound="left",
                command=lambda n=name: self.select_frame(n))
            btn.grid(row=row, column=1, padx=(4, 16), pady=pad_y, sticky="ew")
            self.sidebar_buttons[name] = (btn, colors)

        # Active indicator bar (fixed height, not stretching)
        self.active_indicator = ctk.CTkFrame(
            self.sidebar_frame, width=4, height=btn_h - 4, corner_radius=2,
            fg_color=Colors.DASH[0])
        self.active_indicator.grid_propagate(False)
        self.active_indicator.grid(row=2, column=0, padx=(8, 0), pady=pad_y)

        # Resurrect button (special gold style)
        self.sidebar_button_god = ctk.CTkButton(
            self.sidebar_frame, text="RESURRECT", height=btn_h, anchor="w",
            fg_color="transparent", border_width=2,
            border_color=Colors.RESURRECT_GOLD,
            text_color=Colors.RESURRECT_GOLD,
            hover_color=Colors.RESURRECT_GOLD,
            image=self.icons.get("resurrect"), compound="left",
            font=ctk.CTkFont(weight="bold"),
            command=lambda: self.select_frame("Resurrect"))
        self.sidebar_button_god.grid(row=8, column=0, columnspan=2, padx=20, pady=pad_y, sticky="s")

        def on_enter(e):
            self.sidebar_button_god.configure(
                text_color="black", border_color="black", fg_color=Colors.RESURRECT_GOLD,
                image=self.icons.get("resurrect_negative"))

        def on_leave(e):
            self.sidebar_button_god.configure(
                text_color=Colors.RESURRECT_GOLD, border_color=Colors.RESURRECT_GOLD,
                fg_color="transparent", image=self.icons.get("resurrect"))

        self.sidebar_button_god.bind("<Enter>", on_enter)
        self.sidebar_button_god.bind("<Leave>", on_leave)

        # Footer: version + copyright
        footer_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        footer_frame.grid(row=9, column=0, columnspan=2, padx=10, pady=(10, 14), sticky="s")

        ctk.CTkLabel(
            footer_frame, text=f"v{APP_VERSION}",
            font=ctk.CTkFont(size=9), text_color="#555"
        ).pack()

        year = datetime.now().year
        self.footer_label = ctk.CTkLabel(
            footer_frame,
            text=f"\u00a9 {year} Maurizio Falconi",
            font=ctk.CTkFont(size=9), text_color="#555", cursor="hand2")
        self.footer_label.pack()
        self.footer_label.bind("<Button-1>",
                               lambda e: webbrowser.open("https://falker47.github.io/Nexus-portfolio/"))

    # -----------------------------------------------------------------------
    # Frame Selection (with active sidebar state)
    # -----------------------------------------------------------------------
    def select_frame(self, name):
        frames = {
            "Dashboard": self.frame_dashboard,
            "Cleaning": self.frame_cleaning,
            "Disk": self.frame_disk,
            "Tools": self.frame_tools,
            "Apps": self.frame_apps,
            "Turbo": self.frame_turbo,
            "Resurrect": self.frame_resurrect,
        }

        for f in frames.values():
            f.grid_forget()
        frames[name].grid(row=0, column=1, sticky="nsew")

        # Update sidebar active state
        for btn_name, (btn, colors) in self.sidebar_buttons.items():
            if btn_name == name:
                btn.configure(fg_color=colors[0], text_color="white")
                row = btn.grid_info()["row"]
                self.active_indicator.configure(fg_color=colors[0])
                self.active_indicator.grid(row=row, column=0, padx=(8, 0),
                                           pady=Spacing.SIDEBAR_BTN_PAD_Y)
            else:
                btn.configure(fg_color="transparent", text_color="gray70")

        # Special handling for Resurrect
        if name == "Resurrect":
            self.active_indicator.configure(fg_color=Colors.RESURRECT_GOLD)
            self.active_indicator.grid(row=8, column=0, padx=(8, 0),
                                       pady=Spacing.SIDEBAR_BTN_PAD_Y)

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------
    def _create_page_header(self, parent, title, subtitle, row=0):
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.grid(row=row, column=0, columnspan=2,
                    padx=Spacing.PAGE_PAD_X, pady=(Spacing.PAGE_PAD_Y, 10), sticky="w")
        ctk.CTkLabel(header, text=title,
                     font=ctk.CTkFont(*Fonts.PAGE_TITLE)).pack(anchor="w")
        ctk.CTkLabel(header, text=subtitle,
                     font=ctk.CTkFont(*Fonts.PAGE_SUBTITLE),
                     text_color=Colors.TEXT_MUTED).pack(anchor="w", pady=(2, 0))
        return header

    def _create_card(self, parent, **grid_kwargs):
        return ctk.CTkFrame(
            parent,
            corner_radius=Spacing.CARD_CORNER_RADIUS,
            border_width=Spacing.CARD_BORDER_WIDTH,
            border_color=Colors.BG_CARD_BORDER,
            **{k: v for k, v in grid_kwargs.items() if k not in
               ("row", "column", "padx", "pady", "sticky", "columnspan", "rowspan")}
        )

    def _grid_card(self, parent, **grid_kwargs):
        card = ctk.CTkFrame(
            parent,
            corner_radius=Spacing.CARD_CORNER_RADIUS,
            border_width=Spacing.CARD_BORDER_WIDTH,
            border_color=Colors.BG_CARD_BORDER)
        card.grid(**grid_kwargs)
        return card

    def show_toast(self, message, level="info", duration=4000):
        self.after(0, lambda: ToastNotification(self, message, level, duration))

    # -----------------------------------------------------------------------
    # Dashboard
    # -----------------------------------------------------------------------
    def _setup_dashboard_frame(self):
        self.frame_dashboard.grid_columnconfigure((0, 1), weight=1)

        self._create_page_header(self.frame_dashboard,
                                 "Live System Monitor",
                                 "Real-time hardware metrics and system status")

        _ph = "#444"  # placeholder color (muted)

        # Card 1: System Specs
        self.card_sys = self._grid_card(self.frame_dashboard,
                                        row=1, column=0, padx=(24, 12), pady=12, sticky="nsew")
        ctk.CTkLabel(self.card_sys, text="System Specs & Uptime",
                     font=ctk.CTkFont(*Fonts.CARD_TITLE)).pack(pady=(15, 5))
        self.dash_os = ctk.CTkLabel(self.card_sys, text="\u2014", text_color=_ph)
        self.dash_os.pack()

        self.lbl_update_status = ctk.CTkLabel(
            self.card_sys, text="Checking updates\u2026",
            font=ctk.CTkFont(size=12), text_color=_ph)
        self.lbl_update_status.pack(pady=(10, 5))

        self.btn_update_row = ctk.CTkFrame(self.card_sys, fg_color="transparent")
        self.btn_run_update = ctk.CTkButton(
            self.btn_update_row, text="Install Required", height=28, width=140,
            fg_color=Colors.ERROR, hover_color="#C62828",
            command=self.run_windows_update)
        self.btn_view_optional = ctk.CTkButton(
            self.btn_update_row, text="View Optional", height=28, width=140,
            fg_color=Colors.WARNING, hover_color="#FFA000", text_color="black",
            command=self.run_view_optional_updates)

        self.dash_uptime_val = ctk.CTkLabel(
            self.card_sys, text="\u2014",
            font=ctk.CTkFont(*Fonts.STAT_LARGE), text_color=_ph)
        self.dash_uptime_val.pack(pady=5)
        ctk.CTkLabel(self.card_sys, text="(Restart recommended once a week)",
                     font=ctk.CTkFont(size=10), text_color=Colors.TEXT_MUTED).pack(pady=(0, 10))

        # Card 2: Disk Usage
        self.card_disk = self._grid_card(self.frame_dashboard,
                                         row=1, column=1, padx=(12, 24), pady=12, sticky="nsew")
        ctk.CTkLabel(self.card_disk, text="Disk Usage (C:)",
                     font=ctk.CTkFont(*Fonts.CARD_TITLE)).pack(pady=(15, 5))
        self.dash_disk_bar = ctk.CTkProgressBar(self.card_disk, width=220, height=15,
                                                progress_color=_ph)
        self.dash_disk_bar.set(0)
        self.dash_disk_bar.pack(pady=10)
        self.dash_disk_val = ctk.CTkLabel(self.card_disk, text="\u2014", text_color=_ph)
        self.dash_disk_val.pack()
        self.dash_disk_info = ctk.CTkLabel(self.card_disk, text="",
                                           text_color=Colors.TEXT_MUTED,
                                           font=ctk.CTkFont(size=11), wraplength=300)
        self.dash_disk_info.pack()
        self.dash_disk_perc = ctk.CTkLabel(self.card_disk, text="\u2014",
                                           font=ctk.CTkFont(*Fonts.STAT_LARGE), text_color=_ph)
        self.dash_disk_perc.pack(pady=(5, 10))

        # Card 3: CPU Graph
        self.card_cpu = self._grid_card(self.frame_dashboard,
                                        row=2, column=0, padx=(24, 12), pady=12, sticky="nsew")
        ctk.CTkLabel(self.card_cpu, text="CPU Usage History",
                     font=ctk.CTkFont(*Fonts.CARD_TITLE)).pack(pady=(15, 5))
        self.cpu_graph = LiveGraph(self.card_cpu,
                                  width=Dimensions.GRAPH_WIDTH,
                                  height=Dimensions.GRAPH_HEIGHT,
                                  line_color=Colors.GRAPH_CPU)
        self.cpu_graph.pack(pady=5, padx=10, fill="x")
        self.dash_cpu_name = ctk.CTkLabel(self.card_cpu, text="\u2014",
                                          text_color=_ph, wraplength=300)
        self.dash_cpu_name.pack()
        self.dash_cpu_val = ctk.CTkLabel(self.card_cpu, text="\u2014",
                                         font=ctk.CTkFont(*Fonts.STAT_LARGE), text_color=_ph)
        self.dash_cpu_val.pack(pady=(5, 10))

        # Card 4: RAM Graph
        self.card_ram = self._grid_card(self.frame_dashboard,
                                        row=2, column=1, padx=(12, 24), pady=12, sticky="nsew")
        ctk.CTkLabel(self.card_ram, text="Memory (RAM) History",
                     font=ctk.CTkFont(*Fonts.CARD_TITLE)).pack(pady=(15, 5))
        self.ram_graph = LiveGraph(self.card_ram,
                                  width=Dimensions.GRAPH_WIDTH,
                                  height=Dimensions.GRAPH_HEIGHT,
                                  line_color=Colors.GRAPH_RAM)
        self.ram_graph.pack(pady=5, padx=10, fill="x")
        self.dash_ram_val = ctk.CTkLabel(self.card_ram, text="\u2014", text_color=_ph)
        self.dash_ram_val.pack()
        self.dash_ram_info = ctk.CTkLabel(self.card_ram, text="",
                                          text_color=Colors.TEXT_MUTED, font=ctk.CTkFont(size=11))
        self.dash_ram_info.pack()
        self.dash_ram_perc = ctk.CTkLabel(self.card_ram, text="\u2014",
                                          font=ctk.CTkFont(*Fonts.STAT_LARGE), text_color=_ph)
        self.dash_ram_perc.pack(pady=(5, 10))

    # -----------------------------------------------------------------------
    # Cleaning
    # -----------------------------------------------------------------------
    def _setup_cleaning_frame(self):
        self.frame_cleaning.grid_columnconfigure(0, weight=1)
        self.frame_cleaning.grid_rowconfigure(2, weight=1)

        self._create_page_header(self.frame_cleaning,
                                 "System Cleanup",
                                 "Remove temporary files and free disk space")

        btn_frame = self._grid_card(self.frame_cleaning,
                                    row=1, column=0, padx=24, pady=12, sticky="nsew")

        c_base, c_hover = Colors.CLEAN
        ctk.CTkButton(btn_frame, text="Clean Temporary Files",
                      fg_color=c_base, hover_color=c_hover,
                      command=self.run_clean_temp).pack(fill="x", padx=20, pady=10)
        ctk.CTkButton(btn_frame, text="Empty Recycle Bin",
                      fg_color=c_base, hover_color=c_hover,
                      command=self.run_empty_recycle).pack(fill="x", padx=20, pady=10)
        ctk.CTkButton(btn_frame, text="Open Windows Disk Cleanup",
                      fg_color=c_base, hover_color=c_hover,
                      command=self.run_cleanmgr).pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(btn_frame, text="Expert Warning: Takes 10+ minutes.",
                     text_color="orange").pack(anchor="w", padx=20, pady=(10, 0))
        ctk.CTkButton(btn_frame, text="Run Deep Clean (WinSxS)",
                      fg_color="darkred", hover_color="#800000",
                      command=self.run_deep_clean).pack(fill="x", padx=20, pady=10)

        self.clean_log = ctk.CTkTextbox(
            self.frame_cleaning, height=150,
            font=ctk.CTkFont(*Fonts.TERMINAL),
            fg_color=Colors.BG_TERMINAL, text_color=Colors.TEXT_TERMINAL)
        self.clean_log.grid(row=2, column=0, padx=24, pady=12, sticky="nsew")
        self.clean_log.configure(state="disabled")
        self.clean_log.tag_config("info", foreground=Colors.TEXT_TERMINAL)
        self.clean_log.tag_config("warn", foreground=Colors.RESURRECT_GOLD)
        self.clean_log.tag_config("err", foreground=Colors.ERROR)

    # -----------------------------------------------------------------------
    # Disk Optimization
    # -----------------------------------------------------------------------
    def _setup_disk_frame(self):
        self.frame_disk.grid_columnconfigure(0, weight=1)
        self.frame_disk.grid_rowconfigure(4, weight=1)

        self._create_page_header(self.frame_disk,
                                 "Disk Optimization",
                                 "Defragment HDD or TRIM SSD for peak performance")

        drive_row = ctk.CTkFrame(self.frame_disk, fg_color="transparent")
        drive_row.grid(row=1, column=0, padx=24, pady=5, sticky="w")

        ctk.CTkLabel(drive_row, text="Select Drive:",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=(0, 10))

        self.selected_drive = tk.StringVar()
        self.drive_menu = ctk.CTkOptionMenu(drive_row, variable=self.selected_drive,
                                            values=["Loading..."], width=120)
        self.drive_menu.pack(side="left", padx=(0, 10))

        d_base, d_hover = Colors.DISK
        ctk.CTkButton(drive_row, text="Refresh", fg_color=d_base, hover_color=d_hover,
                      width=80, command=self.refresh_drives).pack(side="left")

        btn_row = ctk.CTkFrame(self.frame_disk, fg_color="transparent")
        btn_row.grid(row=2, column=0, padx=24, pady=5, sticky="w")

        ctk.CTkButton(btn_row, text="Run Optimization (Defrag/Trim)",
                      fg_color=d_base, hover_color=d_hover,
                      command=self.run_optimize_drive).pack(side="left", padx=(0, 10))
        ctk.CTkButton(btn_row, text="Open Windows Defrag GUI",
                      fg_color=d_base, hover_color=d_hover,
                      command=self.run_dfrgui).pack(side="left")

        self.disk_log = ctk.CTkTextbox(
            self.frame_disk, height=150,
            font=ctk.CTkFont(*Fonts.TERMINAL),
            fg_color=Colors.BG_TERMINAL, text_color=Colors.TEXT_TERMINAL)
        self.disk_log.grid(row=4, column=0, padx=24, pady=12, sticky="nsew")
        self.disk_log.configure(state="disabled")
        self.disk_log.tag_config("info", foreground=Colors.TEXT_TERMINAL)
        self.disk_log.tag_config("warn", foreground=Colors.RESURRECT_GOLD)
        self.disk_log.tag_config("err", foreground=Colors.ERROR)

        self.refresh_drives()

    # -----------------------------------------------------------------------
    # Tools
    # -----------------------------------------------------------------------
    def _setup_tools_frame(self):
        self.frame_tools.grid_columnconfigure(0, weight=1)
        self.frame_tools.grid_rowconfigure(1, weight=0)
        self.frame_tools.grid_rowconfigure(3, weight=1)

        self._create_page_header(self.frame_tools,
                                 "Advanced Tools",
                                 "System integrity scans and network utilities")

        container = ctk.CTkScrollableFrame(self.frame_tools)
        container.grid(row=1, column=0, padx=24, pady=12, sticky="nsew")

        t_base, t_hover = Colors.TOOLS

        grp1 = self._create_card(container)
        grp1.pack(fill="x", pady=8)
        ctk.CTkLabel(grp1, text="System Integrity",
                     font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=12, pady=8)
        self._add_tool_btn(grp1, "Run SFC Scan", "Scans system files.",
                           "sfc /scannow", "SFC", t_base, t_hover)
        self._add_tool_btn(grp1, "Check Health (DISM)", "Checks system image.",
                           "DISM /Online /Cleanup-Image /CheckHealth", "DISM Check", t_base, t_hover)
        self._add_tool_btn(grp1, "Restore Health (DISM)", "Repairs system image.",
                           "DISM /Online /Cleanup-Image /RestoreHealth", "DISM Restore", t_base, t_hover)

        grp2 = self._create_card(container)
        grp2.pack(fill="x", pady=8)
        ctk.CTkLabel(grp2, text="Network Tools",
                     font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=12, pady=8)
        self._add_tool_btn(grp2, "Flush DNS", "Clears DNS cache.",
                           "ipconfig /flushdns", "DNS", t_base, t_hover)
        self._add_tool_btn(grp2, "Reset Winsock", "Resets network adapter.",
                           "netsh winsock reset", "Winsock", t_base, t_hover)

        grp3 = self._create_card(container)
        grp3.pack(fill="x", pady=8)
        ctk.CTkLabel(grp3, text="Power & Backup",
                     font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=12, pady=8)
        ctk.CTkButton(grp3, text="Generate Battery Report",
                      fg_color=t_base, hover_color=t_hover,
                      command=self.run_battery_report).pack(fill="x", padx=12, pady=5)
        ctk.CTkButton(grp3, text="Create Restore Point (Now)",
                      fg_color=t_base, hover_color=t_hover,
                      command=self.run_create_restore).pack(fill="x", padx=12, pady=(5, 12))

        # Execution log
        ctk.CTkLabel(self.frame_tools, text="> EXECUTION LOG",
                     font=ctk.CTkFont(*Fonts.TERMINAL),
                     text_color=Colors.TEXT_TERMINAL).grid(
            row=2, column=0, padx=24, pady=(8, 0), sticky="w")

        self.tools_log = ctk.CTkTextbox(
            self.frame_tools, height=150,
            font=ctk.CTkFont(*Fonts.TERMINAL),
            fg_color=Colors.BG_TERMINAL, text_color=Colors.TEXT_TERMINAL)
        self.tools_log.grid(row=3, column=0, padx=24, pady=12, sticky="nsew")
        self.tools_log.configure(state="disabled")
        self.tools_log.tag_config("info", foreground=Colors.TEXT_TERMINAL)
        self.tools_log.tag_config("warn", foreground=Colors.RESURRECT_GOLD)
        self.tools_log.tag_config("err", foreground=Colors.ERROR)

    def _add_tool_btn(self, parent, text, desc, cmd, name, col, hover_col):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="x", padx=12, pady=2)
        ctk.CTkLabel(f, text=desc, width=200, anchor="w").pack(side="left")
        ctk.CTkButton(f, text=text, fg_color=col, hover_color=hover_col,
                      command=lambda: self.run_cmd(cmd, name)).pack(side="right", fill="x", expand=True)

    # -----------------------------------------------------------------------
    # Apps
    # -----------------------------------------------------------------------
    def _setup_apps_frame(self):
        self.frame_apps.grid_columnconfigure(0, weight=1)

        self._create_page_header(self.frame_apps,
                                 "App Management",
                                 "Manage installed programs and startup applications")

        frame = self._grid_card(self.frame_apps, row=1, column=0, padx=24, pady=12, sticky="nsew")

        a_base, a_hover = Colors.APPS

        ctk.CTkLabel(frame, text="Uninstall Programs",
                     font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=12, pady=12)
        ctk.CTkButton(frame, text="Open Settings (Apps)",
                      fg_color=a_base, hover_color=a_hover,
                      command=lambda: self.run_launch("start ms-settings:appsfeatures", "Settings")
                      ).pack(fill="x", padx=20, pady=5)
        ctk.CTkButton(frame, text="Open Control Panel",
                      fg_color=a_base, hover_color=a_hover,
                      command=lambda: self.run_launch("control appwiz.cpl", "Control Panel")
                      ).pack(fill="x", padx=20, pady=5)

        ctk.CTkLabel(frame, text="Startup",
                     font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=12, pady=12)
        ctk.CTkButton(frame, text="Manage Startup Apps",
                      fg_color=a_base, hover_color=a_hover,
                      command=lambda: self.run_launch("start ms-settings:startupapps", "Startup")
                      ).pack(fill="x", padx=20, pady=(5, 16))

    # -----------------------------------------------------------------------
    # Turbo Mode
    # -----------------------------------------------------------------------
    def _setup_turbo_frame(self):
        self.frame_turbo.grid_columnconfigure(0, weight=1)
        self.frame_turbo.grid_rowconfigure(2, weight=1)

        self._create_page_header(self.frame_turbo,
                                 "Turbo Mode",
                                 "Toggle performance settings \u2014 changes apply immediately")

        container = ctk.CTkScrollableFrame(self.frame_turbo)
        container.grid(row=2, column=0, padx=24, pady=12, sticky="nsew")

        self.turbo_vars = {}
        self.turbo_switches = {}

        # Master Toggle
        master_frame = ctk.CTkFrame(container, fg_color=Colors.TURBO[0], corner_radius=10)
        master_frame.pack(fill="x", pady=(0, 15))
        ctk.CTkLabel(master_frame, text="MASTER TOGGLE",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color="black").pack(side="left", padx=15, pady=10)
        self.master_switch = ctk.CTkSwitch(master_frame, text="Enable All",
                                           text_color="black",
                                           command=self._master_toggle_changed)
        self.master_switch.pack(side="right", padx=15, pady=10)

        toggle_config = [
            ("power", "High Performance Power Plan",
             "Switch from Balanced to High Performance",
             lambda: self.perf_mgr.get_power_plan() == "high",
             lambda: self.perf_mgr.set_power_plan(True),
             lambda: self.perf_mgr.set_power_plan(False)),
            ("visual", "Disable Visual Effects",
             "Turn off animations, shadows, transparency",
             lambda: not self.perf_mgr.get_visual_effects(),
             lambda: self.perf_mgr.set_visual_effects(False),
             lambda: self.perf_mgr.set_visual_effects(True)),
            ("sysmain", "Disable SysMain (Superfetch)",
             "Stop app pre-loading service",
             lambda: not self.perf_mgr.get_sysmain_status(),
             lambda: self.perf_mgr.set_sysmain(False),
             lambda: self.perf_mgr.set_sysmain(True)),
            ("wsearch", "Disable Windows Search",
             "Stop background indexing",
             lambda: not self.perf_mgr.get_wsearch_status(),
             lambda: self.perf_mgr.set_wsearch(False),
             lambda: self.perf_mgr.set_wsearch(True)),
            ("spooler", "Disable Print Spooler",
             "Stop print service (if no printer)",
             lambda: not self.perf_mgr.get_spooler_status(),
             lambda: self.perf_mgr.set_spooler(False),
             lambda: self.perf_mgr.set_spooler(True)),
        ]

        for key, label, desc, get_fn, on_fn, off_fn in toggle_config:
            self._create_turbo_toggle(container, key, label, desc, get_fn, on_fn, off_fn)

        threading.Thread(target=self._load_turbo_states, daemon=True).start()

    def _create_turbo_toggle(self, parent, key, label, desc, get_fn, on_fn, off_fn):
        frame = self._create_card(parent)
        frame.pack(fill="x", pady=5)

        left = ctk.CTkFrame(frame, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True, padx=12, pady=10)
        ctk.CTkLabel(left, text=label,
                     font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(left, text=desc,
                     font=ctk.CTkFont(size=11), text_color=Colors.TEXT_MUTED).pack(anchor="w")

        var = tk.BooleanVar(value=False)
        self.turbo_vars[key] = var

        switch = ctk.CTkSwitch(frame, text="", variable=var,
                               command=lambda k=key, on=on_fn, off=off_fn: self._turbo_toggle_changed(k, on, off))
        switch.pack(side="right", padx=15, pady=10)
        self.turbo_switches[key] = switch

    def _load_turbo_states(self):
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
            except Exception:
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
        for key, var in self.turbo_vars.items():
            var.set(state)

        def apply_all():
            if state:
                self.perf_mgr.set_power_plan(True)
                self.perf_mgr.set_visual_effects(False)
                self.perf_mgr.set_sysmain(False)
                self.perf_mgr.set_wsearch(False)
                self.perf_mgr.set_spooler(False)
            else:
                self.perf_mgr.set_power_plan(False)
                self.perf_mgr.set_visual_effects(True)
                self.perf_mgr.set_sysmain(True)
                self.perf_mgr.set_wsearch(True)
                self.perf_mgr.set_spooler(True)
        threading.Thread(target=apply_all, daemon=True).start()

    # -----------------------------------------------------------------------
    # Resurrect (God Mode)
    # -----------------------------------------------------------------------
    def _setup_resurrect_frame(self):
        self.frame_resurrect.grid_columnconfigure(0, weight=1)
        self.frame_resurrect.grid_rowconfigure(2, weight=1)

        # Hero
        hero = ctk.CTkFrame(self.frame_resurrect, fg_color="transparent")
        hero.grid(row=0, column=0, padx=24, pady=Spacing.PAGE_PAD_Y, sticky="ew")
        ctk.CTkLabel(hero, text="SYSTEM RESURRECTION",
                     font=ctk.CTkFont(size=32, weight="bold"),
                     text_color=Colors.RESURRECT_GOLD).pack(anchor="center")
        ctk.CTkLabel(hero, text="Advanced Safety Protocol & Deep Optimization",
                     font=ctk.CTkFont(*Fonts.PAGE_SUBTITLE),
                     text_color=Colors.TEXT_MUTED).pack(anchor="center")

        # Action Area
        self.action_frame = self._grid_card(self.frame_resurrect,
                                            row=1, column=0, padx=40, pady=12, sticky="ew")

        self.progress_bar = ctk.CTkProgressBar(self.action_frame, orientation="horizontal",
                                               height=20, progress_color=Colors.RESURRECT_GOLD)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=20, pady=(20, 10))

        self.lbl_status = ctk.CTkLabel(self.action_frame, text="Ready to Start",
                                       font=ctk.CTkFont(size=14, weight="bold"))
        self.lbl_status.pack(pady=(5, 0))

        self.lbl_warning = ctk.CTkLabel(
            self.action_frame,
            text="(Includes: Auto System Restore, Browser Cleanup, Disk Health Scan)",
            font=ctk.CTkFont(size=11), text_color="gray70")
        self.lbl_warning.pack(pady=(0, 5))

        self.btn_resurrect_start = ctk.CTkButton(
            self.action_frame, text="INITIATE PROTOCOL",
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=Colors.RESURRECT_GOLD, hover_color=Colors.RESURRECT_HOVER,
            text_color="black", height=40,
            command=self.run_god_mode)
        self.btn_resurrect_start.pack(pady=20)

        # Log
        log_frame = ctk.CTkFrame(self.frame_resurrect, corner_radius=10,
                                 fg_color=Colors.BG_TERMINAL,
                                 border_width=Spacing.CARD_BORDER_WIDTH,
                                 border_color=Colors.BG_CARD_BORDER)
        log_frame.grid(row=2, column=0, padx=24, pady=12, sticky="nsew")

        ctk.CTkLabel(log_frame, text="> EXECUTION LOG",
                     font=ctk.CTkFont(*Fonts.TERMINAL),
                     text_color=Colors.TEXT_TERMINAL).pack(anchor="w", padx=10, pady=5)

        self.god_log = ctk.CTkTextbox(log_frame, font=ctk.CTkFont(*Fonts.TERMINAL),
                                      fg_color=Colors.BG_TERMINAL,
                                      text_color=Colors.TEXT_TERMINAL)
        self.god_log.pack(fill="both", expand=True, padx=5, pady=5)
        self.god_log.insert("0.0", "Waiting for user command...\n")
        self.god_log.configure(state="disabled")

        self.god_log.tag_config("info", foreground=Colors.TEXT_TERMINAL)
        self.god_log.tag_config("warn", foreground=Colors.RESURRECT_GOLD)
        self.god_log.tag_config("err", foreground=Colors.ERROR)
        self.god_log.tag_config("head", foreground="#00BFFF")

    # -----------------------------------------------------------------------
    # Dashboard Update Loop
    # -----------------------------------------------------------------------
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
            self.after(0, lambda: self._update_gui(
                os_info, cpu_name, uptime, t_ram, a_ram, p_ram,
                t_disk, f_disk, p_disk, cpu_usage, bat_perc, bat_plug))
        except Exception:
            pass
        self.after(3000, self.update_dashboard)

    def _check_updates_thread(self):
        try:
            mandatory, optional, status = self.monitor.get_windows_update_status()
            self.after(0, lambda: self._update_updates_gui(mandatory, optional, status))
        except Exception:
            self.after(0, lambda: self._update_updates_gui(-1, -1, "Check Failed"))

    def _update_updates_gui(self, mandatory, optional, status):
        self.btn_update_row.pack_forget()
        self.btn_run_update.pack_forget()
        self.btn_view_optional.pack_forget()

        if mandatory > 0 or optional > 0:
            self.lbl_update_status.pack_forget()
            self.btn_update_row.pack(pady=(10, 5), before=self.dash_uptime_val)
            if mandatory > 0:
                self.btn_run_update.configure(text=f"Install Required ({mandatory})")
                self.btn_run_update.pack(side="left", padx=5)
            if optional > 0:
                self.btn_view_optional.configure(text=f"View Optional ({optional})")
                self.btn_view_optional.pack(side="left", padx=5)
        elif mandatory == 0 and optional == 0:
            self.lbl_update_status.configure(text="\u2713 System is up to date",
                                             text_color=Colors.SUCCESS)
        else:
            self.lbl_update_status.configure(text="Update check failed",
                                             text_color=Colors.TEXT_MUTED)

    def _update_gui(self, os_info, cpu_name, uptime, t_ram, a_ram, p_ram,
                    t_disk, f_disk, p_disk, cpu_usage, bat_perc, bat_plug):
        # First load: replace placeholders with real data + proper colors
        if self.dash_os.cget("text") == "\u2014":
            self.dash_os.configure(text=os_info, text_color=Colors.TEXT_MUTED)
            self.dash_cpu_name.configure(text=cpu_name, text_color=Colors.TEXT_MUTED)
            self.dash_cpu_val.configure(text_color="white")
            self.dash_ram_val.configure(text_color="white")
            self.dash_ram_perc.configure(text_color="white")
            self.dash_disk_val.configure(text_color="white")
            self.dash_disk_perc.configure(text_color="white")
            self.dash_uptime_val.configure(text_color=Colors.INFO)
            ram_info = self.monitor.get_ram_info()
            if ram_info:
                self.dash_ram_info.configure(text=ram_info)
            disk_model = self.monitor.get_disk_model()
            if disk_model:
                self.dash_disk_info.configure(text=disk_model)

        # Uptime
        new_uptime = f"Time since restart: {uptime}"
        if self.dash_uptime_val.cget("text") != new_uptime:
            self.dash_uptime_val.configure(text=new_uptime)

        # CPU
        self.cpu_graph.add_value(cpu_usage)
        new_cpu_val = f"{round(cpu_usage, 1)}%"
        if self.dash_cpu_val.cget("text") != new_cpu_val:
            self.dash_cpu_val.configure(text=new_cpu_val)

        # RAM
        self.ram_graph.add_value(p_ram)
        new_ram_val = f"{round(t_ram - a_ram, 1)} GB / {t_ram} GB"
        if self.dash_ram_val.cget("text") != new_ram_val:
            self.dash_ram_val.configure(text=new_ram_val)
        new_ram_perc = f"{round(p_ram, 1)}%"
        if self.dash_ram_perc.cget("text") != new_ram_perc:
            self.dash_ram_perc.configure(text=new_ram_perc)

        # Disk
        def get_color(perc):
            if perc < 60:
                return Colors.SUCCESS
            if perc < 85:
                return Colors.WARNING
            return Colors.ERROR

        target_prog = p_disk / 100
        if abs(self.dash_disk_bar.get() - target_prog) > 0.01:
            self.dash_disk_bar.set(target_prog)
        try:
            self.dash_disk_bar.configure(progress_color=get_color(p_disk))
        except Exception:
            pass

        new_disk_val = f"{f_disk} GB Free / {t_disk} GB"
        if self.dash_disk_val.cget("text") != new_disk_val:
            self.dash_disk_val.configure(text=new_disk_val)
        new_disk_perc = f"{p_disk}%"
        if self.dash_disk_perc.cget("text") != new_disk_perc:
            self.dash_disk_perc.configure(text=new_disk_perc)

    # -----------------------------------------------------------------------
    # Logging helpers
    # -----------------------------------------------------------------------
    def log_tools_msg(self, msg):
        self.after(0, lambda: self._log_to_widget(self.tools_log, msg))

    def log_msg(self, msg):
        self.after(0, lambda: self._log_to_widget(self.clean_log, msg))

    def log_disk_msg(self, msg):
        self.after(0, lambda: self._log_to_widget(self.disk_log, msg))

    def log_god_msg(self, msg, level="info"):
        self.after(0, lambda: self._log_to_widget(self.god_log, msg, level))

    def _log_to_widget(self, widget, msg, tag=None):
        widget.configure(state="normal")
        if tag:
            widget.insert(tk.END, f"{msg}\n", tag)
        else:
            widget.insert(tk.END, f"{msg}\n")
        widget.see(tk.END)
        widget.configure(state="disabled")

    # -----------------------------------------------------------------------
    # Action handlers
    # -----------------------------------------------------------------------
    def refresh_drives(self):
        def task():
            drives = self.disk_opt.get_drive_info()
            drive_values = [d['letter'] for d in drives]
            if drive_values:
                self.after(0, lambda: self._update_drive_menu(drive_values))
            else:
                self.after(0, lambda: self._update_drive_menu(["No drives"]))
        threading.Thread(target=task, daemon=True).start()

    def _update_drive_menu(self, values):
        self.drive_menu.configure(values=values)
        self.selected_drive.set(values[0])

    def run_clean_temp(self):
        def task():
            self.log_msg("Starting cleanup...")
            count, freed = self.cleanup_mgr.clean_temp_files(progress_callback=self.log_msg)
            self.log_msg(f"Finished. Deleted {count} files. Freed {freed / (1024 * 1024):.2f} MB.")
            self.show_toast(f"Cleanup complete: {count} files, {freed / (1024 * 1024):.1f} MB freed", "success")
        threading.Thread(target=task, daemon=True).start()

    def run_empty_recycle(self):
        def task():
            self.log_msg("Emptying Recycle Bin...")
            success, msg = self.cleanup_mgr.empty_recycle_bin()
            self.log_msg(msg)
            level = "success" if success else "error"
            self.show_toast(msg, level)
        threading.Thread(target=task, daemon=True).start()

    def run_cleanmgr(self):
        self.cleanup_mgr.open_disk_cleanup()
        self.log_msg("Opened Disk Cleanup.")

    def run_deep_clean(self):
        if messagebox.askyesno("Deep Clean Warning",
                               "Run DISM Component Store Cleanup?\nTarget: WinSxS.\nTime: 10-20mins.\n\nProceed?"):
            self.cmd_runner.run_command("DISM /Online /Cleanup-Image /StartComponentCleanup", "Deep Clean")

    def run_optimize_drive(self):
        letter = self.selected_drive.get()
        if not letter:
            self.show_toast("Select a drive first.", "warning")
            return

        def task():
            self.log_disk_msg("--- Optimization Task Started ---")
            self.disk_opt.analyze_optimize_drive(letter, progress_callback=self.log_disk_msg)
            self.log_disk_msg("--- Optimization Task Finished ---")

        if messagebox.askyesno("Confirm", f"Optimize {letter}?"):
            threading.Thread(target=task, daemon=True).start()

    def run_dfrgui(self):
        self.disk_opt.open_optimize_gui()

    def run_cmd(self, cmd, desc):
        if not messagebox.askyesno("Confirm", f"Run {desc}?"):
            return

        def task():
            self.log_tools_msg(f"\n> RUNNING: {desc}...")
            self.cmd_runner.run_command_stream(cmd, desc, self.log_tools_msg)
            self.log_tools_msg(f"> FINISHED: {desc}")
        threading.Thread(target=task, daemon=True).start()

    def run_launch(self, cmd, desc):
        try:
            subprocess.Popen(cmd, shell=True)
        except Exception as e:
            self.show_toast(str(e), "error")

    def run_battery_report(self):
        import os

        def task():
            try:
                path = os.path.join(os.environ['USERPROFILE'], 'battery_report.html')
                subprocess.run(f'powercfg /batteryreport /output "{path}"',
                               shell=True, check=True,
                               creationflags=subprocess.CREATE_NO_WINDOW)
                os.startfile(path)
                self.show_toast("Battery report generated.", "success")
            except Exception as e:
                self.show_toast(f"Battery report failed: {e}", "error")
        threading.Thread(target=task, daemon=True).start()

    def run_create_restore(self):
        if messagebox.askyesno("Create Restore Point",
                               "Create a Windows System Restore Point?\n(Requires Admin privileges)\nThis may take a minute."):
            def task():
                success, msg = self.restore_mgr.create_restore_point("Panacea Manual Point")
                level = "success" if success else "error"
                self.show_toast(msg, level)
            threading.Thread(target=task, daemon=True).start()

    def run_windows_update(self):
        import time, os

        def task():
            try:
                self.after(0, lambda: os.system("start ms-settings:windowsupdate"))
                subprocess.Popen("USOClient.exe StartInteractiveScan", shell=True,
                                 creationflags=subprocess.CREATE_NO_WINDOW)
                self.after(0, self._set_updating_status)
                time.sleep(30)
                threading.Thread(target=self._check_updates_thread, daemon=True).start()
            except Exception as e:
                self.show_toast(f"Failed to launch updater: {e}", "error")
        threading.Thread(target=task, daemon=True).start()

    def _set_updating_status(self):
        self.btn_update_row.pack_forget()
        self.lbl_update_status.configure(text="Updating... please wait",
                                         text_color=Colors.TEXT_MUTED)
        self.lbl_update_status.pack(pady=(10, 5), before=self.dash_uptime_val)

    def run_view_optional_updates(self):
        import time, os

        def task():
            try:
                self.after(0, lambda: os.system("start ms-settings:windowsupdate-optionalupdates"))
                self.after(0, self._set_looking_status)
                time.sleep(30)
                threading.Thread(target=self._check_updates_thread, daemon=True).start()
            except Exception as e:
                self.show_toast(f"Failed to open settings: {e}", "error")
        threading.Thread(target=task, daemon=True).start()

    def _set_looking_status(self):
        self.btn_update_row.pack_forget()
        self.lbl_update_status.configure(text="Looking for updates...",
                                         text_color=Colors.TEXT_MUTED)
        self.lbl_update_status.pack(pady=(10, 5), before=self.dash_uptime_val)

    # -----------------------------------------------------------------------
    # God Mode (Resurrect)
    # -----------------------------------------------------------------------
    def run_god_mode(self):
        if not messagebox.askyesno("Confirm Resurrection",
                                   "Initiate System Resurrection Protocol?\n\n"
                                   "This process is intensive and may take time.\n"
                                   "Ensure all work is saved."):
            return

        self.btn_resurrect_start.configure(state="disabled", text="PROTOCOL RUNNING...")
        self.lbl_status.configure(text="Initializing...", text_color=Colors.RESURRECT_GOLD)
        self.progress_bar.set(0)
        self.god_log.configure(state="normal")
        self.god_log.delete("0.0", tk.END)
        self.god_log.configure(state="disabled")

        def health_filter(line):
            bad_phrases = [
                "Avvio in corso", "Attendere", "L'operazione richieder",
                "100%", "completed", "Avanzamento:", "ETA:", "Fase:",
                "totale:", "percent complete",
                "Il file system", "etichetta del volume", "Durata fase",
                "Verifica file", "Verifica indici", "Verifica descrittori",
                "journal USN", "KB di spazio", "KB in", "KB occupati",
                "KB disponibili", "byte in ogni", "unit", "allocazione"
            ]
            for phrase in bad_phrases:
                if phrase in line:
                    return False
            return bool(line.strip())

        def sequence():
            steps = 8
            current_step = 0

            def update_progress(step_i, status_text):
                self.after(0, lambda: self.progress_bar.set(step_i / steps))
                self.after(0, lambda: self.lbl_status.configure(text=status_text))

            try:
                # PHASE 1: Safety Backup
                current_step += 1
                update_progress(current_step, "Phase 1: Safety Backup")
                self.log_god_msg("\n[PHASE 1] SAFETY BACKUP INITIATED...", "head")
                self.log_god_msg("Verifying System Restore state...", "info")
                self.restore_mgr.ensure_restore_enabled("C:\\")
                success, msg = self.restore_mgr.create_restore_point("Panacea GodMode Auto-Restore")
                if success:
                    self.log_god_msg(f"Restore Point: {msg}", "info")
                else:
                    self.log_god_msg(f"Restore Point Warning: {msg}", "warn")

                # PHASE 2: Browser Cleanup
                current_step += 1
                update_progress(current_step, "Phase 2: Browser Cleanup")
                self.log_god_msg("\n[PHASE 2] BROWSER CLEANUP...", "head")
                bc_count, bc_size = self.cleanup_mgr.clean_browser_caches()
                self.log_god_msg(
                    f"Browser Cache: Cleared {bc_count} files ({bc_size / (1024 * 1024):.2f} MB)", "info")

                # PHASE 3: System Cleanup
                current_step += 1
                update_progress(current_step, "Phase 3: System Junk Cleanup")
                self.log_god_msg("\n[PHASE 3] SYSTEM JUNK CLEANUP...", "head")
                count, freed = self.cleanup_mgr.clean_temp_files(
                    progress_callback=lambda m: self.log_god_msg(m, "info"))
                self.log_god_msg(
                    f"Temp Files: Deleted {count}, Freed {freed / (1024 * 1024):.2f} MB", "info")
                success, msg = self.cleanup_mgr.empty_recycle_bin()
                self.log_god_msg(f"Recycle Bin: {msg}", "info")

                # PHASE 4: Network Reset
                current_step += 1
                update_progress(current_step, "Phase 4: Network Reset")
                self.log_god_msg("\n[PHASE 4] NETWORK RESET...", "head")
                self.cmd_runner.run_command_stream(
                    "ipconfig /flushdns", "DNS Flush",
                    lambda m: self.log_god_msg(m, "info"))
                self.cmd_runner.run_command_stream(
                    "netsh winsock reset", "Winsock Reset",
                    lambda m: self.log_god_msg(m, "info"))

                # PHASE 5: Disk Optimization
                current_step += 1
                update_progress(current_step, "Phase 5: Disk Defrag/Trim")
                self.log_god_msg("\n[PHASE 5] DISK OPTIMIZATION (C:)...", "head")
                self.disk_opt.analyze_optimize_drive(
                    "C:", progress_callback=lambda m: self.log_god_msg(m, "info"))

                # PHASE 6: Disk Health
                current_step += 1
                update_progress(current_step, "Phase 6: Disk Health Scan")
                self.log_god_msg("\n[PHASE 6] DISK HEALTH CHECK (CHKDSK)...", "head")
                self.cmd_runner.run_command_stream(
                    "chkdsk C: /scan /perf", "CHKDSK",
                    lambda m: self.log_god_msg(m, "info"), filter_func=health_filter)

                # PHASE 7: DISM Health
                current_step += 1
                update_progress(current_step, "Phase 7: DISM Health Check")
                self.log_god_msg("\n[PHASE 7] DISM IMAGE HEALTH...", "head")
                self.cmd_runner.run_command_stream(
                    "DISM /Online /Cleanup-Image /CheckHealth", "DISM Check",
                    lambda m: self.log_god_msg(m, "info"), filter_func=health_filter)

                # PHASE 8: SFC Scan
                current_step += 1
                update_progress(current_step, "Phase 8: Integrity Scan (SFC)")
                self.log_god_msg("\n[PHASE 8] SFC INTEGRITY SCAN...", "head")
                self.cmd_runner.run_command_stream(
                    "sfc /scannow", "SFC Scan",
                    lambda m: self.log_god_msg(m, "info"), filter_func=health_filter)

                update_progress(steps, "Protocol Complete")
                self.log_god_msg("\n=== RESURRECTION PROTOCOL COMPLETE ===", "head")
                self.log_god_msg(
                    "\n[TIP] For best results: Uninstall useless programs and manage "
                    "startup apps from the APPS tab and then restart your PC.", "warn")
                self.show_toast("Resurrection complete. Restart recommended.", "success", 6000)

            except Exception as e:
                self.log_god_msg(f"\n[!] ERROR: {e}", "err")
                self.after(0, lambda: self.lbl_status.configure(text="Protocol Failed", text_color="red"))
                self.show_toast(f"Sequence failed: {e}", "error")

            finally:
                self.after(0, lambda: self.btn_resurrect_start.configure(
                    state="normal", text="INITIATE PROTOCOL"))
                self.after(0, lambda: self.lbl_status.configure(text="Ready", text_color=Colors.TEXT_MUTED))

        threading.Thread(target=sequence, daemon=True).start()
