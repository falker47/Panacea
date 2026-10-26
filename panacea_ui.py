"""Panacea desktop. Workers post callbacks; only the Tk thread drains them."""
import os
import sys
import subprocess
import threading
import webbrowser
from datetime import datetime
from collections import deque
from pathlib import Path
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
from PIL import Image
from modules.ui_icons import make_icon
from modules.cleanup import CleanupManager, CleanupResult
from modules.disk import DiskOptimizer
from modules.commands import CommandRunner
from modules.logger import Logger
from modules.system_monitor import SystemMonitor
from modules.restore import RestoreManager
from modules.performance import PerformanceManager
from modules.maintenance_guard import MaintenanceGuard
from modules.ui_dispatch import UiDispatcher, WorkerController
from modules.utils import resource_path
from version import VERSION, GITHUB_REPO

# Palette drawn from the original Panacea/Nexus Portfolio midnight-blue and gold identity.
BG = '#0b1525'
SURFACE = '#142138'
SURFACE_ALT = '#1b2b44'
BORDER = '#2e415c'
TEXT = '#f1f3f8'
MUTED = '#9eafc8'
COL_BLUE = '#76b6e2'
COL_GOLD = '#e4c579'
COL_SUCCESS = '#78c8a8'
COL_WARNING = '#e4b66d'
COL_RED = '#ee939a'
COL_GREEN = TEXT
ctk.set_appearance_mode('Dark')
ctk.set_default_color_theme('dark-blue')


class PanaceaApp(ctk.CTk):
    LOG_LINES = 500
    # Five primary destinations; existing screens remain available as lazy subviews.
    NAV_GROUPS = (
        ('Dashboard', 'Overview', 'dashboard', ('Dashboard',)),
        ('Cleaning', 'Space & Cleanup', 'clean', ('Cleaning', 'Apps')),
        ('Tools', 'Diagnostics & Repair', 'tools', ('Tools', 'Disk')),
        ('Turbo', 'Performance & Startup', 'turbo', ('Turbo', 'Startup')),
        ('Resurrect', 'Guided Maintenance', 'resurrect', ('Resurrect',)),
    )
    SUBVIEW_LABELS = {
        'Cleaning': 'Cleanup', 'Apps': 'Installed apps',
        'Tools': 'Repair tools', 'Disk': 'Drive optimization',
        'Turbo': 'Performance settings', 'Startup': 'Startup apps',
    }

    def __init__(self):
        super().__init__()
        self.title(f'Panacea · System maintenance · {VERSION}')
        self.configure(fg_color=BG)
        self.withdraw()
        self.geometry('1020x680')
        self.minsize(760, 480)
        self.dispatcher = UiDispatcher()
        self.workers = WorkerController(self.dispatcher)
        self._shutdown = threading.Event()
        self._resurrect_cancel = threading.Event()
        self._quick_cleanup_cancel = threading.Event()
        self._update_cancel = threading.Event()
        self._update_installing = False
        self._update_downloading = False
        self._release = self._update_job = self._update_dir = None
        self._maintenance_controls = []
        self._fonts = {}
        self._pending_logs = {}
        self._preview_summary = 'Analysis optional · No files deleted'
        self._quick_cleanup_summary = 'Ready · No cleanup started'
        self._drive_values = []
        self._turbo_states = {}
        self._turbo_master = None
        self._turbo_saved = None
        self._resurrection_states = {}
        self._resurrection_rows = {}
        self.last_resurrection_result = None
        try:
            self.logger = Logger()
        except (OSError, KeyError):
            self.logger = None
        self.cleanup_mgr, self.disk_opt = CleanupManager(), DiskOptimizer()
        self.cmd_runner, self.monitor = CommandRunner(), SystemMonitor()
        self.restore_mgr, self.perf_mgr = RestoreManager(), PerformanceManager()
        self.maintenance_guard = MaintenanceGuard()
        self._maintenance_uncertain = self.maintenance_guard.is_blocked()
        try:
            self.iconbitmap(resource_path('assets/panacea_icon.ico'))
        except Exception:
            pass
        self._load_icons()
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._setup_sidebar()
        self._setup_update_bar()
        self._setup_subnav()
        self.frames = {}
        for name, attr in [('Dashboard', 'dashboard'), ('Cleaning', 'cleaning'),
                           ('Apps', 'apps'), ('Tools', 'tools'), ('Disk', 'disk'),
                           ('Turbo', 'turbo'), ('Startup', 'startup'), ('Resurrect', 'resurrect')]:
            frame = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
            self.frames[name] = frame
            setattr(self, f'frame_{attr}', frame)
        self._setup_functions = {
            'Dashboard': self._setup_dashboard_frame, 'Cleaning': self._setup_cleaning_frame,
            'Apps': self._setup_apps_frame, 'Tools': self._setup_tools_frame,
            'Disk': self._setup_disk_frame, 'Turbo': self._setup_turbo_frame,
            'Startup': self._setup_startup_frame, 'Resurrect': self._setup_resurrect_frame,
        }
        self._built_frames = set()
        self.operation_label = ctk.CTkLabel(self, text='Ready · No operation running', text_color=MUTED, anchor='w', font=self._font(11))
        self.operation_label.grid(row=2, column=1, sticky='ew', padx=(28, 22), pady=(2, 10))
        self.operation_label.bind('<Configure>', lambda event: self.operation_label.configure(wraplength=max(200, event.width / self.operation_label._get_widget_scaling() - 4)))
        if self._maintenance_uncertain:
            self.operation_label.configure(text=self.maintenance_guard.last_error, text_color=COL_WARNING)
        self.protocol('WM_DELETE_WINDOW', self._on_close)
        for index, (name, _, _, _) in enumerate(self.NAV_GROUPS, 1):
            self.bind(f'<Control-Key-{index}>', lambda event, n=name: self.select_frame(n))
        self.select_frame('Dashboard')
        self.after(20, self._drain_callbacks)
        self.after_idle(self._center_and_show)
        self.update_dashboard()
        self._load_metadata()
        self.refresh_drives()
        self._load_turbo_states()
        self._check_updates_thread()
        self._check_app_update()

    def _font(self, size=13, bold=False, semibold=False):
        key = size, bold, semibold
        if key not in self._fonts:
            family = 'Segoe UI Semibold' if semibold else 'Segoe UI'
            self._fonts[key] = ctk.CTkFont(family=family, size=size,
                                           weight='bold' if bold else 'normal')
        return self._fonts[key]

    def _button(self, parent, text, command, *, secondary=False, maintenance=False, **kwargs):
        button_height = kwargs.pop('height', 32)
        button = ctk.CTkButton(parent, text=text, command=command, height=button_height, corner_radius=6, fg_color=SURFACE_ALT if secondary else '#765f33', hover_color='#304561' if secondary else '#957745', text_color=TEXT, font=self._font(12), border_width=1, border_color=BORDER if secondary else COL_GOLD, **kwargs)
        button.bind('<Return>', lambda event: button.invoke())
        button.bind('<FocusIn>', lambda event: button.configure(border_color=COL_BLUE))
        button.bind('<FocusOut>', lambda event: button.configure(border_color=BORDER if secondary else COL_GOLD))
        button._canvas.configure(takefocus=1)
        button.bind('<space>', lambda event: button.invoke())
        if maintenance:
            self._maintenance_controls.append(button)
            if self.workers.busy() or self._update_downloading or self._update_installing or self.__dict__.get('_maintenance_uncertain'):
                button.configure(state='disabled')
        return button

    def _header(self, parent, title, detail, compact=False):
        parent.grid_columnconfigure(0, weight=1)
        frame = ctk.CTkFrame(parent, fg_color='transparent')
        frame.grid(row=0, column=0, sticky='ew', padx=22, pady=(10, 8) if compact else (15, 10))
        ctk.CTkLabel(frame, text=title, height=24, font=self._font(21 if compact else 23, True), anchor='w').pack(fill='x')
        label = ctk.CTkLabel(frame, text=detail, height=18 if compact else 28, font=self._font(11 if compact else 12), text_color=MUTED, anchor='w', wraplength=650, justify='left')
        label.pack(fill='x', pady=(1, 0))
        frame.bind('<Configure>', lambda event: label.configure(wraplength=max(250, event.width - 10)))

    def _keyboard_switch(self, switch):
        switch._canvas.configure(takefocus=1, highlightthickness=1, highlightcolor=COL_BLUE, highlightbackground=SURFACE)
        switch.bind('<Return>', lambda event: switch.toggle())
        switch.bind('<space>', lambda event: switch.toggle())

    def _card(self, parent):
        return ctk.CTkFrame(parent, fg_color=SURFACE, border_width=1, border_color=BORDER, corner_radius=8)

    def _load_icons(self):
        """Load the original chalice logo and a consistent, vector-like icon system."""
        self.icons, self.icons_active, self.action_icons = {}, {}, {}
        for name in ('dashboard', 'clean', 'disk', 'tools', 'apps', 'turbo', 'resurrect'):
            idle = make_icon(name, '#a5b5cd', 96)
            active = make_icon(name, COL_GOLD, 96)
            self.icons[name] = ctk.CTkImage(light_image=idle, dark_image=idle, size=(31, 31))
            self.icons_active[name] = ctk.CTkImage(light_image=active, dark_image=active, size=(31, 31))
        for name in ('cpu', 'memory', 'drive', 'scan', 'restore', 'updates'):
            color = COL_GOLD if name in ('drive', 'restore') else COL_BLUE
            icon = make_icon(name, color, 96)
            size = 40 if name in ('scan', 'restore', 'updates') else 22
            self.action_icons[name] = ctk.CTkImage(light_image=icon, dark_image=icon, size=(size, size))
        with Image.open(resource_path('assets/panacea_icon.png')) as source:
            original = source.convert('RGBA').copy()
        self.brand_icon = ctk.CTkImage(light_image=original, dark_image=original, size=(68, 68))

    def _setup_sidebar(self):
        self.sidebar_frame = ctk.CTkFrame(self, width=260, corner_radius=0, fg_color='#0e192b')
        self.sidebar_frame.grid(row=0, column=0, rowspan=3, sticky='nsew')
        self.sidebar_frame.grid_propagate(False)
        self.sidebar_frame.grid_columnconfigure(0, weight=1)
        self.sidebar_frame.grid_rowconfigure(7, weight=1)
        brand = ctk.CTkFrame(self.sidebar_frame, fg_color='transparent')
        brand.grid(row=0, column=0, rowspan=2, padx=(12, 8), pady=(20, 30), sticky='ew')
        ctk.CTkLabel(brand, image=self.brand_icon, text='', width=68, height=68).grid(row=0, column=0, padx=(0, 8))
        lettering = ctk.CTkFrame(brand, fg_color='transparent')
        lettering.grid(row=0, column=1, sticky='w')
        self.brand_title = ctk.CTkLabel(lettering, text='Panacea', height=30, font=self._font(28, True), text_color=TEXT, anchor='w')
        self.brand_title.pack(anchor='w')
        self.brand_tagline = ctk.CTkLabel(lettering, text='SYSTEM MAINTENANCE', height=17, font=self._font(11, semibold=True), text_color=COL_GOLD, anchor='w')
        self.brand_tagline.pack(anchor='w')
        self.nav_buttons = {}
        for row, (name, label, icon, _) in enumerate(self.NAV_GROUPS, 2):
            button = self._button(self.sidebar_frame, label, lambda n=name: self.select_frame(n),
                                  secondary=True, width=236, height=50, anchor='w',
                                  image=self.icons[icon], compound='left')
            button.configure(font=self._font(15, semibold=True))
            button.grid(row=row, column=0, padx=11, pady=5, sticky='ew')
            self.nav_buttons[name] = button
        ctk.CTkFrame(self.sidebar_frame, fg_color=BORDER, height=1).grid(row=8, column=0, sticky='ew', padx=17, pady=(10, 6))
        self.sidebar_footer = ctk.CTkFrame(self.sidebar_frame, fg_color='transparent')
        self.sidebar_footer.grid(row=9, column=0, sticky='ew', padx=14, pady=(0, 10))
        self.sidebar_footer.grid_columnconfigure(1, weight=1)
        footer = ctk.CTkLabel(self.sidebar_footer, text=f'© {datetime.now().year} falker47',
                              height=18, text_color=MUTED, font=self._font(10), cursor='hand2')
        footer.grid(row=0, column=0, sticky='w')
        footer.bind('<Button-1>', lambda event: webbrowser.open('https://falker47.github.io/'))
        ctk.CTkLabel(self.sidebar_footer, text=f'v{VERSION}', height=18, text_color=MUTED,
                     font=self._font(10), anchor='e').grid(row=0, column=1, sticky='e')

    def _setup_subnav(self):
        """Compact secondary navigation for groups containing more than one view."""
        self.subnav_frames, self.subnav_buttons = {}, {}
        for group, _, _, pages in self.NAV_GROUPS:
            if len(pages) < 2:
                continue
            strip = ctk.CTkFrame(self.update_bar, fg_color='transparent', corner_radius=0)
            for index, page in enumerate(pages):
                button = self._button(strip, self.SUBVIEW_LABELS[page],
                                      lambda p=page: self.select_frame(p),
                                      secondary=True, height=30, width=145)
                button.grid(row=0, column=index, padx=(0, 8))
                self.subnav_buttons[page] = button
            self.subnav_frames[group] = strip

    def select_frame(self, name):
        if name not in self.frames:
            return
        if name not in self._built_frames:
            self._setup_functions[name]()
            self._built_frames.add(name)
        for frame in self.frames.values():
            frame.grid_forget()
        self.frames[name].grid(row=1, column=1, sticky='nsew', padx=(6, 0))
        group = next((root for root, _, _, pages in self.NAV_GROUPS if name in pages), name)
        self.active_frame, self.active_group = name, group
        for root, strip in self.__dict__.get('subnav_frames', {}).items():
            strip.grid_forget()
            if root == group:
                strip.grid(row=0, column=1, sticky='w', padx=(0, 6), pady=3)
        for page, button in self.__dict__.get('subnav_buttons', {}).items():
            active = page == name
            button.configure(fg_color='#263a56' if active else SURFACE_ALT,
                             border_color=COL_GOLD if active else BORDER,
                             text_color=TEXT if active else MUTED)
        for key, button in self.nav_buttons.items():
            selected = key == group
            icon_key = next((icon for root, _, icon, _ in self.NAV_GROUPS if root == key), key.lower())
            icon_set = self.__dict__.get('icons_active' if selected else 'icons', {})
            kwargs = {'fg_color': '#263a56' if selected else 'transparent',
                      'border_color': COL_GOLD if selected else '#0e192b',
                      'text_color': TEXT if selected else MUTED}
            if icon_key in icon_set:
                kwargs['image'] = icon_set[icon_key]
            button.configure(**kwargs)

    def _setup_update_bar(self):
        bar = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=0, height=42)
        self.update_bar = bar
        bar.grid(row=0, column=1, sticky='ew', padx=(6, 0))
        bar.grid_columnconfigure(0, weight=1)
        self.app_update_status = ctk.CTkLabel(bar, text='Checking Panacea updates…', anchor='w', text_color=MUTED, font=self._font(11), wraplength=350)
        self.app_update_status.grid(row=0, column=0, sticky='ew', padx=18, pady=7)
        self.btn_check_update = self._button(bar, 'Check updates', self._check_app_update, secondary=True, width=105)
        self.btn_check_update.grid(row=0, column=2, padx=(4, 12), pady=6)
        self.update_actions = ctk.CTkFrame(bar, fg_color='transparent')
        self.btn_update_install = self._button(self.update_actions, 'Download / install', self._auto_update, width=130)
        self.btn_update_notes = self._button(self.update_actions, 'Release notes', self._show_release_notes, secondary=True, width=98)
        self.btn_update_defer = self._button(self.update_actions, 'Defer', self._defer_update, secondary=True, width=60)
        for column, button in enumerate((self.btn_update_install, self.btn_update_notes, self.btn_update_defer)):
            button.grid(row=0, column=column, padx=(0, 8), pady=(0, 8))

    def _setup_dashboard_frame(self):
        outer = self.frame_dashboard
        outer.grid_columnconfigure(0, weight=1)
        outer.grid_rowconfigure(0, weight=1)
        frame = ctk.CTkScrollableFrame(outer, fg_color=BG, corner_radius=0)
        frame.grid(row=0, column=0, sticky='nsew')
        frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(frame, text='Overview', font=self._font(22, True), anchor='w').grid(
            row=0, column=0, sticky='w', padx=18, pady=(8, 7))

        # A compact system summary, with a separate truthful Windows Update status.
        info = self._card(frame)
        info.grid(row=1, column=0, padx=18, pady=(0, 7), sticky='ew')
        info.grid_columnconfigure((0, 1), weight=1, uniform='overview')
        system = ctk.CTkFrame(info, fg_color='transparent')
        system.grid(row=0, column=0, sticky='ew', padx=(14, 7), pady=10)
        self.dash_os = ctk.CTkLabel(system, text='Loading Windows details…', height=22, anchor='w',
                                    font=self._font(15, True), text_color=TEXT)
        self.dash_os.pack(anchor='w')
        system_details = ctk.CTkFrame(system, fg_color='transparent')
        system_details.pack(fill='x')
        self.dash_uptime_val = ctk.CTkLabel(system_details, text='Uptime: —', height=16, anchor='w',
                                            font=self._font(11), text_color=MUTED)
        self.dash_uptime_val.pack(side='left')
        self.dash_battery = ctk.CTkLabel(system_details, text='Power: —', height=16, anchor='w',
                                         font=self._font(10), text_color=MUTED)
        self.dash_battery.pack(side='left', padx=(10, 0))
        updates = ctk.CTkFrame(info, fg_color=SURFACE_ALT, corner_radius=8)
        updates.grid(row=0, column=1, sticky='nsew', padx=(7, 10), pady=7)
        updates.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(updates, text='', image=self.action_icons['updates'], width=28).grid(
            row=0, column=0, rowspan=2, padx=(10, 3))
        ctk.CTkLabel(updates, text='Windows Update', height=18, text_color=TEXT, font=self._font(12, True),
                     anchor='w').grid(row=0, column=1, sticky='sw', pady=(14, 0))
        self.lbl_update_status = ctk.CTkLabel(updates, text='Checking…', height=16, font=self._font(10),
                                              text_color=MUTED, anchor='w', wraplength=210)
        self.lbl_update_status.grid(row=1, column=1, sticky='nw', pady=(0, 14))
        self._button(updates, 'View', self.run_windows_update, secondary=True, width=58).grid(
            row=0, column=2, rowspan=2, padx=(5, 10), pady=10)

        body = ctk.CTkFrame(frame, fg_color='transparent')
        body.grid(row=2, column=0, padx=18, pady=(0, 5), sticky='ew')
        body.grid_columnconfigure((0, 1, 2), weight=1, uniform='metrics')
        self.card_cpu, self.card_ram, self.card_disk = [self._card(body) for _ in range(3)]
        for index, card in enumerate((self.card_cpu, self.card_ram, self.card_disk)):
            card.grid(row=0, column=index, padx=(0, 5) if index == 0 else
                      (5, 0) if index == 2 else 5, sticky='nsew')
        for card, title, icon_name in (
            (self.card_cpu, 'CPU', 'cpu'),
            (self.card_ram, 'Memory (RAM)', 'memory'),
            (self.card_disk, 'System drive', 'drive'),
        ):
            heading = ctk.CTkFrame(card, fg_color='transparent')
            heading.pack(fill='x', padx=12, pady=(7, 1))
            ctk.CTkLabel(heading, text='', image=self.action_icons[icon_name],
                         width=24, height=24).pack(side='left', padx=(0, 6))
            ctk.CTkLabel(heading, text=title, font=self._font(12, True),
                         anchor='w', text_color=TEXT).pack(side='left', fill='x')

        self.dash_cpu_val = ctk.CTkLabel(self.card_cpu, text='—', font=self._font(25, True),
                                         text_color=TEXT, anchor='w')
        self.dash_cpu_val.pack(fill='x', padx=12)
        self.cpu_graph = LiveGraph(self.card_cpu, width=175, height=36, line_color=COL_BLUE)
        self.cpu_graph.pack(fill='x', padx=12, pady=(5, 5))
        self.dash_cpu_name = ctk.CTkLabel(self.card_cpu, text='Loading processor…',
                                          text_color=MUTED, font=self._font(10),
                                          anchor='w', wraplength=185, justify='left')
        self.dash_cpu_name.pack(fill='x', padx=12, pady=(0, 9))

        self.dash_ram_perc = ctk.CTkLabel(self.card_ram, text='—', font=self._font(25, True),
                                          text_color=TEXT, anchor='w')
        self.dash_ram_perc.pack(fill='x', padx=12)
        self.ram_graph = LiveGraph(self.card_ram, width=175, height=36, line_color=COL_GOLD)
        self.ram_graph.pack(fill='x', padx=12, pady=(5, 5))
        self.dash_ram_val = ctk.CTkLabel(self.card_ram, text='RAM: —', text_color=MUTED,
                                         font=self._font(11), anchor='w', wraplength=185)
        self.dash_ram_val.pack(fill='x', padx=12)
        self.dash_ram_info = ctk.CTkLabel(self.card_ram, text='Loading memory details…',
                                          text_color=MUTED, font=self._font(10),
                                          anchor='w', wraplength=185)
        self.dash_ram_info.pack(fill='x', padx=12, pady=(0, 9))

        self.dash_disk_perc = ctk.CTkLabel(self.card_disk, text='—', font=self._font(25, True),
                                           text_color=TEXT, anchor='w')
        self.dash_disk_perc.pack(fill='x', padx=12)
        self.dash_disk_bar = ctk.CTkProgressBar(self.card_disk, height=12, corner_radius=6,
                                                 progress_color=COL_GOLD, fg_color='#26364b')
        self.dash_disk_bar.set(0)
        self.dash_disk_bar.pack(fill='x', padx=12, pady=(12, 8))
        self.dash_disk_val = ctk.CTkLabel(self.card_disk, text='Storage: —', text_color=MUTED,
                                          font=self._font(11), anchor='w', wraplength=185)
        self.dash_disk_val.pack(fill='x', padx=12)
        self.dash_disk_state = ctk.CTkLabel(self.card_disk, text='Checking space…',
                                            text_color=MUTED, font=self._font(10), anchor='w')
        self.dash_disk_state.pack(fill='x', padx=12)
        self.dash_disk_info = ctk.CTkLabel(self.card_disk, text='Loading disk details…',
                                           text_color=MUTED, font=self._font(10),
                                           anchor='w', wraplength=185)
        self.dash_disk_info.pack(fill='x', padx=12, pady=(0, 9))

        # Two meaningful actions. Navigation is already in the sidebar: no redundant
        # "Open cleanup" tile. Preview feedback remains in-place on the dashboard.
        self.card_sys = ctk.CTkFrame(frame, fg_color='transparent')
        self.card_sys.grid(row=3, column=0, padx=18, pady=(0, 4), sticky='ew')
        self.card_sys.grid_columnconfigure((0, 1), weight=1, uniform='actions')
        scan = ctk.CTkFrame(self.card_sys, fg_color=SURFACE_ALT,
                            border_color=BORDER, border_width=1, corner_radius=9)
        scan.grid(row=0, column=0, sticky='nsew', padx=(0, 5), pady=0)
        scan.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(scan, image=self.action_icons['scan'], text='', width=27).grid(
            row=0, column=0, rowspan=2, padx=(9, 5))
        ctk.CTkLabel(scan, text='Temporary files', height=18, font=self._font(12, True),
                     anchor='w').grid(row=0, column=1, sticky='sw', pady=(14, 0))
        self.dash_preview_status = ctk.CTkLabel(
            scan, text=self._preview_summary, height=16, text_color=MUTED, font=self._font(10),
            anchor='w', wraplength=226, justify='left')
        self.dash_preview_status.grid(row=1, column=1, sticky='nw', pady=(0, 14))
        self._button(scan, 'Analyze', self.run_preview_temp, secondary=True,
                     maintenance=True, width=77).grid(
            row=0, column=2, rowspan=2, padx=(3, 9), pady=8)

        restore = ctk.CTkFrame(self.card_sys, fg_color=SURFACE_ALT,
                               border_color=BORDER, border_width=1, corner_radius=9)
        restore.grid(row=0, column=1, sticky='nsew', padx=(5, 0), pady=0)
        restore.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(restore, image=self.action_icons['restore'], text='', width=27).grid(
            row=0, column=0, rowspan=2, padx=(9, 5))
        ctk.CTkLabel(restore, text='Restore point', height=18, font=self._font(12, True),
                     anchor='w').grid(row=0, column=1, sticky='sw', pady=(14, 0))
        restore_detail = ctk.CTkLabel(restore, text='Save Windows state · confirmation required',
                     height=16, text_color=MUTED, font=self._font(10), anchor='w', wraplength=210,
                     justify='left')
        restore_detail.grid(row=1, column=1, sticky='nw', pady=(0, 14))
        self._button(restore, 'Create', self.run_create_restore, secondary=True,
                     maintenance=True, width=77).grid(
            row=0, column=2, rowspan=2, padx=(3, 9), pady=8)

        for card, label, reserved in ((scan, self.dash_preview_status, 151),
                                      (restore, restore_detail, 151),
                                      (updates, self.lbl_update_status, 132)):
            card.bind('<Configure>', lambda event, item=label, space=reserved:
                      item.configure(wraplength=max(80, event.width / item._get_widget_scaling() - space)))

        for card, labels in (
            (self.card_cpu, (self.dash_cpu_name,)),
            (self.card_ram, (self.dash_ram_val, self.dash_ram_info)),
            (self.card_disk, (self.dash_disk_val, self.dash_disk_info)),
        ):
            card.bind('<Configure>', lambda event, items=labels: [
                label.configure(wraplength=max(110, event.width / label._get_widget_scaling() - 24))
                for label in items
            ])

    def _section_body(self, frame, title, detail):
        self._header(frame, title, detail, compact=True)
        frame.grid_rowconfigure(1, weight=1)
        body = ctk.CTkScrollableFrame(frame, fg_color=BG, corner_radius=0)
        body.grid(row=1, column=0, sticky='nsew', padx=14, pady=(0, 8))
        body.grid_columnconfigure(0, weight=1)
        return body

    def _section_log(self, parent, attribute, title='Activity details'):
        panel = self._card(parent)
        panel.pack(fill='x', pady=(4, 0))
        log = self._create_log_textbox(panel, height=160)
        def toggle():
            self._set_section_log_open(attribute, not bool(log.winfo_manager()))
        button = self._button(panel, f'+ {title}', toggle, secondary=True, anchor='w', height=26)
        button.pack(fill='x', padx=6, pady=4)
        setattr(self, attribute, log)
        self.__dict__.setdefault('_section_logs', {})[attribute] = (log, button, title, parent)
        self._set_section_log_open(attribute, self.__dict__.get('_section_log_open', {}).get(attribute, False))
        self._flush_section_log(attribute)
        return log

    def _set_section_log_open(self, attribute, opened):
        """UI-thread state; delivery of worker messages never changes visibility."""
        self.__dict__.setdefault('_section_log_open', {})[attribute] = opened
        entry = self.__dict__.get('_section_logs', {}).get(attribute)
        if entry:
            log, button, title, _ = entry
            if opened:
                log.pack(fill='both', expand=True, padx=10, pady=(0, 10))
            else:
                log.pack_forget()
            button.configure(text=f'{"−" if opened else "+"} {title}')

    def _open_operation_output(self, attribute):
        self._set_section_log_open(attribute, True)
        # Dashboard shortcuts open the working view so live output is visible.
        section = {'clean_log': 'Cleaning', 'tools_log': 'Tools', 'disk_log': 'Disk', 'god_log': 'Resurrect'}[attribute]
        active = self.__dict__.get('active_frame')
        if active and active != section:
            self.select_frame(section)
        entry = self.__dict__.get('_section_logs', {}).get(attribute)
        if entry and isinstance(entry[3], ctk.CTkScrollableFrame):
            body = entry[3]
            def reveal():
                # CTk updates the scrollregion after packing the textbox. Flush
                # geometry before this one-time reveal, never on streamed lines.
                body.update_idletasks()
                if self.__dict__.get('_section_log_open', {}).get(attribute):
                    body._parent_canvas.yview_moveto(1.0)
            self.after_idle(reveal)

    def _action_row(self, parent, title, detail, label, command, *, maintenance=False, icon=None):
        row = ctk.CTkFrame(parent, fg_color='transparent')
        row.pack(fill='x', padx=14, pady=2)
        row.grid_columnconfigure(1, weight=1)
        if icon:
            ctk.CTkLabel(row, text='', image=self.icons_active[icon], width=26).grid(row=0, column=0, rowspan=2, padx=(0, 10))
        ctk.CTkLabel(row, text=title, height=18, font=self._font(13, True), anchor='w').grid(row=0, column=1, sticky='ew')
        description = ctk.CTkLabel(row, text=detail, height=16, text_color=MUTED, font=self._font(11), anchor='w', justify='left')
        description.grid(row=1, column=1, sticky='ew')
        button = self._button(row, label, command, secondary=True, maintenance=maintenance, width=112)
        button.grid(row=0, column=2, rowspan=2, padx=(12, 0))
        row.bind('<Configure>', lambda event: description.configure(
            wraplength=max(100, event.width / description._get_widget_scaling() - (170 if icon else 130))))
        return button

    def _setup_cleaning_frame(self):
        body = self._section_body(
            self.frame_cleaning, 'Cleanup',
            'One confirmed cleanup or individual tools. Protected files remain untouched.')
        quick = self._card(body)
        quick.pack(fill='x', pady=(0, 8))
        quick.grid_columnconfigure(0, weight=1)
        self.quick_cleanup_card = quick
        ctk.CTkLabel(quick, text='Quick cleanup', anchor='w',
                     font=self._font(17, True)).grid(row=0, column=0, sticky='ew', padx=14, pady=(12, 2))
        ctk.CTkLabel(quick, text='Temporary files · Recycle Bin · Windows component store',
                     anchor='w', text_color=MUTED, font=self._font(11)
                     ).grid(row=1, column=0, sticky='ew', padx=14)
        ctk.CTkLabel(quick, text='Then Windows Disk Cleanup opens for manual selection.',
                     anchor='w', text_color=MUTED, font=self._font(11)
                     ).grid(row=2, column=0, sticky='ew', padx=14, pady=(0, 5))
        self.quick_cleanup_button = self._button(
            quick, 'Run quick cleanup', self.run_quick_cleanup,
            maintenance=True, height=38, width=164)
        self.quick_cleanup_button.grid(row=0, column=1, rowspan=3, padx=(8, 14), pady=10)
        self.quick_cleanup_status = ctk.CTkLabel(
            quick, text=self._quick_cleanup_summary, font=self._font(11),
            text_color=MUTED, anchor='w', justify='left', wraplength=680)
        self.quick_cleanup_status.grid(row=3, column=0, columnspan=2, sticky='ew', padx=14, pady=(2, 6))
        self.quick_cleanup_bar = ctk.CTkProgressBar(
            quick, height=7, progress_color=COL_GOLD, fg_color=BORDER)
        self.quick_cleanup_bar.set(0)
        self.quick_cleanup_bar.grid(row=4, column=0, columnspan=2, sticky='ew', padx=14, pady=(0, 11))
        quick.bind('<Configure>', lambda event: self.quick_cleanup_status.configure(
            wraplength=max(180, event.width / self.quick_cleanup_status._get_widget_scaling() - 28)))

        self.cleanup_toggle_button = self._button(
            body, 'Show individual tools', self._toggle_cleanup_tools, secondary=True)
        self.cleanup_toggle_button.pack(fill='x', pady=(0, 4))
        self.cleanup_individuals_frame = ctk.CTkFrame(body, fg_color='transparent')
        actions = self._card(self.cleanup_individuals_frame)
        actions.pack(fill='x')
        self.btn_clean_temp = self._action_row(
            actions, 'Delete temporary files',
            'Permanent deletion after confirmation; no analysis required',
            'Clean now', self.run_clean_temp, maintenance=True)
        self.btn_empty_bin = self._action_row(
            actions, 'Recycle Bin', 'Permanently empty all items · confirmation required',
            'Empty bin', self.run_empty_recycle, maintenance=True)
        self._action_row(
            actions, 'Component store', 'Windows removes superseded components.',
            'Clean store', self.run_deep_clean, maintenance=True)
        self._action_row(
            actions, 'Windows Disk Cleanup', 'Choose categories in the Windows utility.',
            'Open utility', self.run_cleanmgr)
        self._section_log(body, 'clean_log', 'Cleanup details')

    def _toggle_cleanup_tools(self):
        details = self.cleanup_individuals_frame
        if details.winfo_manager():
            details.pack_forget()
            self.cleanup_toggle_button.configure(text='Show individual tools')
        else:
            details.pack(fill='x', pady=(0, 6), before=self.clean_log.master)
            self.cleanup_toggle_button.configure(text='Hide individual tools')

    def _setup_disk_frame(self):
        body = self._section_body(self.frame_disk, 'Drive optimization', 'Select a drive; Windows chooses the correct optimization method.')
        card = self._card(body)
        card.pack(fill='x', pady=(0, 8))
        row = ctk.CTkFrame(card, fg_color='transparent')
        row.pack(fill='x', padx=14, pady=12)
        ctk.CTkLabel(row, text='', image=self.icons_active['disk'], width=28).pack(side='left', padx=(0, 8))
        self.selected_drive = tk.StringVar(value='Loading…')
        self.drive_menu = ctk.CTkOptionMenu(row, variable=self.selected_drive, values=['Loading…'], command=self._drive_selected, width=112, fg_color=SURFACE_ALT, button_color=BORDER, font=self._font(13))
        self.drive_menu.pack(side='left')
        self.drive_menu._canvas.configure(takefocus=1, highlightthickness=1, highlightcolor=COL_BLUE, highlightbackground=SURFACE)
        self.drive_menu.bind('<Down>', lambda event: self._cycle_drive(1))
        self.drive_menu.bind('<Up>', lambda event: self._cycle_drive(-1))
        self._button(row, 'Refresh', self.refresh_drives, secondary=True, width=85).pack(side='right')
        self.drive_detail = ctk.CTkLabel(card, text='Reading local drives…', anchor='w', justify='left', font=self._font(13), text_color=MUTED, wraplength=650)
        self.drive_detail.pack(fill='x', padx=14, pady=(0, 10))
        self.drive_capacity = ctk.CTkProgressBar(card, height=8, progress_color=COL_GOLD, fg_color=BORDER)
        self.drive_capacity.set(0)
        self.drive_capacity.pack(fill='x', padx=14, pady=(0, 14))
        self.btn_optimize_drive = self._action_row(card, 'Optimize selected drive', 'Windows chooses TRIM or defragmentation. May take several minutes.', 'Optimize', self.run_optimize_drive, maintenance=True)
        windows = self._card(body)
        windows.pack(fill='x')
        self._action_row(windows, 'Windows drive optimization', 'View schedules and drive health in Windows.', 'Open utility', self.run_dfrgui)
        self._section_log(body, 'disk_log', 'Optimization output')
        self._set_drives(self.__dict__.get('_drive_info', [{'letter': value} for value in self._drive_values]))

    def _setup_tools_frame(self):
        body = self._section_body(self.frame_tools, 'Repair tools', 'Check integrity or repair Windows and network issues.')
        for title, entries in [
            ('WINDOWS INTEGRITY', [('System file scan', 'Verify and repair protected files.', 'sfc /scannow', 'SFC scan'), ('Image health', 'Check the component image for recorded corruption.', 'DISM /Online /Cleanup-Image /CheckHealth', 'DISM health check'), ('Repair image', 'Repair corruption; may use Windows Update.', 'DISM /Online /Cleanup-Image /RestoreHealth', 'DISM repair')]),
            ('NETWORK', [('Flush DNS', 'Clear cached DNS records.', 'ipconfig /flushdns', 'DNS flush'), ('Reset Winsock', 'May interrupt connections and require a restart.', 'netsh winsock reset', 'Network reset')])]:
            ctk.CTkLabel(body, text=title, height=18, text_color=COL_GOLD, font=self._font(10, True), anchor='w').pack(fill='x', pady=(4, 3), padx=2)
            card = self._card(body)
            card.pack(fill='x', pady=(0, 4))
            for text, detail, command, name in entries:
                self._add_tool_btn(card, text, detail, command, name)
        row = ctk.CTkFrame(body, fg_color='transparent')
        row.pack(fill='x', pady=(6, 0))
        self._button(row, 'Restore point', self.run_create_restore, secondary=True, maintenance=True).pack(side='left', padx=(0, 8))
        self._button(row, 'Battery report', self.run_battery_report, secondary=True, maintenance=True).pack(side='left')
        self._section_log(body, 'tools_log', 'Command output')

    def _add_tool_btn(self, parent, text, desc, cmd, name):
        labels = {'SFC scan': 'Scan', 'DISM health check': 'Check', 'DISM repair': 'Repair',
                  'DNS flush': 'Flush', 'Network reset': 'Reset'}
        return self._action_row(parent, text, desc, labels.get(name, 'Run'),
                                lambda: self.run_cmd(cmd, name), maintenance=True)

    def _windows_settings_card(self, body, title, detail, actions, icon):
        card = self._card(body)
        card.pack(fill='x', pady=(0, 10))
        heading = ctk.CTkFrame(card, fg_color='transparent')
        heading.pack(fill='x', padx=16, pady=(14, 4))
        ctk.CTkLabel(heading, image=self.icons_active[icon], text='', width=28).pack(side='left', padx=(0, 10))
        ctk.CTkLabel(heading, text=title, font=self._font(16, True)).pack(side='left')
        ctk.CTkLabel(card, text=detail, font=self._font(12), text_color=MUTED, anchor='w').pack(fill='x', padx=16, pady=(0, 12))
        row = ctk.CTkFrame(card, fg_color='transparent')
        row.pack(fill='x', padx=16, pady=(0, 14))
        for text, uri in actions:
            self._button(row, text, lambda u=uri, t=text: self.run_launch(u, t),
                         secondary=True, width=150).pack(side='left', padx=(0, 8))

    def _setup_apps_frame(self):
        body = self._section_body(self.frame_apps, 'Installed apps', 'Review installed software using Windows settings.')
        self._windows_settings_card(
            body, 'Installed apps', 'Review storage use, repair or uninstall apps.',
            [('Apps settings', 'ms-settings:appsfeatures'), ('Classic programs', 'appwiz.cpl')], 'apps')
        self.apps_status = ctk.CTkLabel(body, text='Windows handles app changes. Return here when finished.',
                                        font=self._font(11), text_color=MUTED, anchor='w', wraplength=650)
        self.apps_status.pack(fill='x', padx=2, pady=5)

    def _setup_startup_frame(self):
        body = self._section_body(self.frame_startup, 'Startup apps', 'Choose which apps launch when you sign in.')
        self._windows_settings_card(
            body, 'Startup apps', 'Review startup impact and disable unnecessary auto-start entries.',
            [('Startup settings', 'ms-settings:startupapps')], 'turbo')
        self.startup_status = ctk.CTkLabel(body, text='Windows manages startup changes. Return here when finished.',
                                           font=self._font(11), text_color=MUTED, anchor='w', wraplength=650)
        self.startup_status.pack(fill='x', padx=2, pady=5)

    def _setup_turbo_frame(self):
        body = self._section_body(self.frame_turbo, 'Performance settings', 'Original settings are saved before changes and restored when turned off.')
        self.turbo_vars, self.turbo_switches = {}, {}
        master = self._card(body)
        master.pack(fill='x', pady=(0, 8))
        row = ctk.CTkFrame(master, fg_color='transparent')
        row.pack(fill='x', padx=14, pady=(10, 5))
        ctk.CTkLabel(row, text='All settings', font=self._font(15, True)).pack(side='left')
        self.master_var = tk.BooleanVar(value=False)
        self.master_switch = ctk.CTkSwitch(row, text='Loading…', variable=self.master_var, state='disabled', command=self._master_toggle_changed, font=self._font(12), progress_color=COL_GOLD)
        self.master_switch.pack(side='right')
        self._keyboard_switch(self.master_switch)
        self.turbo_saved_label = ctk.CTkLabel(master, text='Reading saved originals…', height=18, font=self._font(11), text_color=MUTED, anchor='w', wraplength=600)
        self.turbo_saved_label.pack(fill='x', padx=14, pady=(0, 8))
        actions = ctk.CTkFrame(master, fg_color='transparent')
        actions.pack(fill='x', padx=14, pady=(0, 10))
        self.btn_restore_turbo = self._button(actions, 'Restore saved settings', self._restore_saved_turbo, secondary=True, maintenance=True)
        self.btn_restore_turbo.pack(side='left')
        self._button(actions, 'Refresh state', self._load_turbo_states, secondary=True, width=112).pack(side='right')
        card = self._card(body)
        card.pack(fill='x')
        config = [('power', 'High performance', 'More power use, heat and battery drain.', lambda: self.perf_mgr.set_power_plan(True), lambda: self.perf_mgr.set_power_plan(False)), ('visual', 'Visual effects preset', 'Save the Windows performance preference.', lambda: self.perf_mgr.set_visual_effects(False), lambda: self.perf_mgr.set_visual_effects(True)), ('sysmain', 'Pause SysMain', 'Pause application preloading.', lambda: self.perf_mgr.set_sysmain(False), lambda: self.perf_mgr.set_sysmain(True)), ('wsearch', 'Pause Windows Search', 'Pause background indexing.', lambda: self.perf_mgr.set_wsearch(False), lambda: self.perf_mgr.set_wsearch(True)), ('spooler', 'Pause Print Spooler', 'Printing is unavailable while active.', lambda: self.perf_mgr.set_spooler(False), lambda: self.perf_mgr.set_spooler(True))]
        for key, title, desc, on_fn, off_fn in config:
            row = ctk.CTkFrame(card, fg_color='transparent')
            row.pack(fill='x', padx=14, pady=5)
            row.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(row, text=title, height=18, font=self._font(13, True), anchor='w').grid(row=0, column=0, sticky='ew')
            detail = ctk.CTkLabel(row, text=desc, height=16, text_color=MUTED, font=self._font(11), anchor='w', justify='left')
            detail.grid(row=1, column=0, sticky='ew')
            var = tk.BooleanVar(value=False)
            switch = ctk.CTkSwitch(row, text='Unknown', variable=var, state='disabled', font=self._font(11), width=125, progress_color=COL_GOLD, command=lambda k=key, on=on_fn, off=off_fn: self._turbo_toggle_changed(k, on, off))
            switch.grid(row=0, column=1, rowspan=2, padx=(12, 0))
            self._keyboard_switch(switch)
            self.turbo_vars[key], self.turbo_switches[key] = var, switch
            row.bind('<Configure>', lambda event, label=detail: label.configure(wraplength=max(120, event.width / label._get_widget_scaling() - 150)))
        if self._turbo_states:
            self._apply_turbo_states((self._turbo_states, self._turbo_master))
        self._apply_saved_turbo(self.__dict__.get('_turbo_saved'))

    RESURRECTION_STEPS = ('Restore point', 'Browser caches', 'Temporary files', 'Recycle Bin', 'DNS cache',
                          'Network reset', 'Drive optimization', 'Disk health scan', 'Windows image health', 'System file scan')
    RESURRECTION_HELP = {
        'Restore point': 'Safety · Verify a new Windows restore point. Deleted files are NOT recoverable.',
        'Browser caches': 'Cleanup · Remove temporary web browser cache data.',
        'Temporary files': 'Cleanup · Remove eligible temporary files; protected items are skipped.',
        'Recycle Bin': 'Cleanup · Permanently delete all items in the Recycle Bin.',
        'DNS cache': 'Network · Refresh locally cached domain-name lookups.',
        'Network reset': 'Network · Reset Winsock; a restart may be needed.',
        'Drive optimization': 'Disk · Let Windows choose TRIM or defragmentation.',
        'Disk health scan': 'Disk · Scan the file system for errors (online CHKDSK).',
        'Windows image health': 'Repair · Check recorded corruption in the Windows component image.',
        'System file scan': 'Repair · Scan and repair protected Windows files (SFC).',
    }

    def _setup_resurrect_frame(self):
        body = self._section_body(self.frame_resurrect, 'Resurrection', '10 steps · Verified restore point required')
        card = self._card(body)
        card.pack(fill='x', pady=(0, 6))
        self.lbl_status = ctk.CTkLabel(card, text='Ready · No steps run', height=22, font=self._font(15, True), anchor='w', justify='left')
        self.lbl_status.pack(fill='x', padx=14, pady=(8, 4))
        self.progress_bar = ctk.CTkProgressBar(card, height=8, progress_color=COL_GOLD, fg_color=BORDER)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill='x', padx=14, pady=(0, 6))
        row = ctk.CTkFrame(card, fg_color='transparent')
        row.pack(fill='x', padx=14, pady=(0, 8))
        self.btn_resurrect_start = self._button(row, 'Start sequence', self.run_god_mode, maintenance=True)
        self.btn_resurrect_start.pack(side='right')
        self.btn_resurrect_cancel = self._button(row, 'Cancel after step', self._cancel_resurrect, secondary=True)
        warning = ctk.CTkLabel(body, text='Permanent deletion: browser caches, temp files and all Recycle Bin items. Restore points cannot recover deleted files.\nNetwork reset may disconnect you or require a restart. Save work. Cancel stops between commands.', height=28, text_color=COL_WARNING, font=self._font(10), anchor='w', justify='left', wraplength=650)
        warning.pack(fill='x', padx=2, pady=(0, 6))
        card.bind('<Configure>', lambda event: (
            warning.configure(wraplength=max(180, event.width / warning._get_widget_scaling() - 4)),
            self.lbl_status.configure(wraplength=max(180, event.width / self.lbl_status._get_widget_scaling() - 28)),
        ))
        timeline = ctk.CTkFrame(body, fg_color='transparent')
        timeline.pack(fill='x')
        timeline.grid_columnconfigure((0, 1), weight=1, uniform='phases')
        self._resurrection_rows = {}
        self._resurrection_info_labels = {}
        for index, name in enumerate(self.RESURRECTION_STEPS):
            phase = self._card(timeline)
            phase.grid(row=index % 5, column=index // 5, sticky='nsew', padx=(0, 4) if index < 5 else (4, 0), pady=2)
            phase.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(phase, text=f'{index + 1:02}', height=24, text_color=COL_GOLD, font=self._font(13, True), width=28).grid(row=0, column=0, padx=(6, 4), pady=4)
            display = {'Drive optimization': 'Optimize drive', 'Disk health scan': 'Disk scan', 'Windows image health': 'Image health', 'System file scan': 'System files'}.get(name, name)
            ctk.CTkLabel(phase, text=display, height=20, anchor='w', font=self._font(12, True)).grid(row=0, column=1, sticky='ew')
            status = ctk.CTkLabel(phase, text='Not started', height=20, width=78, anchor='e', font=self._font(10), text_color=MUTED)
            status.grid(row=0, column=2, padx=(4, 5))
            self._button(
                phase, 'i', lambda n=name: self._toggle_resurrection_info(n),
                secondary=True, width=28, height=24).grid(row=0, column=3, padx=(0, 6), pady=2)
            explanation = ctk.CTkLabel(
                phase, text=self.RESURRECTION_HELP[name], font=self._font(10),
                text_color=MUTED, anchor='w', justify='left', wraplength=230)
            explanation.grid(row=1, column=1, columnspan=3, sticky='ew', padx=(0, 7), pady=(0, 7))
            explanation.grid_remove()
            phase.bind('<Configure>', lambda event, label=explanation: label.configure(
                wraplength=max(90, event.width / label._get_widget_scaling() - 60)))
            self._resurrection_info_labels[name] = explanation
            self._resurrection_rows[name] = status
        self._section_log(body, 'god_log', 'Full sequence output')

    def _toggle_resurrection_info(self, name):
        label = self._resurrection_info_labels.get(name)
        if label is None:
            return
        if label.winfo_manager():
            label.grid_remove()
        else:
            label.grid()
        for name, (state, detail) in self.__dict__.get('_resurrection_states', {}).copy().items():
            self._set_resurrection_step(name, state, detail)

    def _create_log_textbox(self, parent, height=150):
        log = ctk.CTkTextbox(parent, height=height, font=ctk.CTkFont(family='Consolas', size=12), fg_color='#121820', text_color=TEXT, border_width=1, border_color=BORDER, corner_radius=6, wrap='word')
        for tag, color in [('info', TEXT), ('head', COL_BLUE), ('warn', COL_WARNING), ('err', COL_RED)]:
            log.tag_config(tag, foreground=color)
        log.configure(state='disabled')
        return log

    def _log_to_widget(self, widget, msg, level='info'):
        self.dispatcher.post(self._append_log, widget, str(msg)[:4000], level)

    def _append_log(self, widget, msg, level):
        widget.configure(state='normal')
        widget.insert(tk.END, msg + '\n', level)
        lines = int(widget.index('end-1c').split('.')[0])
        if lines > self.LOG_LINES:
            widget.delete('1.0', f'{lines - self.LOG_LINES + 1}.0')
        widget.see(tk.END)
        widget.configure(state='disabled')

    def log_msg(self, msg):
        self._log_section('clean_log', msg)

    def log_disk_msg(self, msg):
        self._log_section('disk_log', msg)

    def log_tools_msg(self, msg):
        self._log_section('tools_log', msg)

    def log_god_msg(self, msg, level='info'):
        self._log_section('god_log', msg, level)

    def _log_section(self, attribute, msg, level='info'):
        self.dispatcher.post(self._append_section_log, attribute, str(msg)[:4000], level)

    def _append_section_log(self, attribute, msg, level):
        widget = self.__dict__.get(attribute)
        if widget is None:
            self._pending_logs.setdefault(attribute, deque(maxlen=self.LOG_LINES)).append((msg, level))
        else:
            self._append_log(widget, msg, level)

    def _flush_section_log(self, attribute):
        for msg, level in self._pending_logs.pop(attribute, ()):
            self._append_log(self.__dict__[attribute], msg, level)

    def _drain_callbacks(self):
        if self._shutdown.is_set():
            return
        self.dispatcher.drain(100)
        if not self._shutdown.is_set():
            self.after(30, self._drain_callbacks)

    def _set_maintenance_state(self, busy):
        busy = busy or self.__dict__.get('_maintenance_uncertain', False)
        for button in self._maintenance_controls:
            button.configure(state='disabled' if busy else 'normal')
        for key, switch in self.__dict__.get('turbo_switches', {}).items():
            switch.configure(state='disabled' if busy or self.__dict__.get('_turbo_refreshing') or self._turbo_states.get(key) is None else 'normal')
        if 'master_switch' in self.__dict__:
            self.master_switch.configure(state='disabled' if busy or self.__dict__.get('_turbo_refreshing') or self._turbo_master is None else 'normal')
        if 'btn_restore_turbo' in self.__dict__:
            self.btn_restore_turbo.configure(state='normal' if not busy and self.__dict__.get('_turbo_saved') else 'disabled')
        if 'btn_optimize_drive' in self.__dict__:
            self._drive_selected()

    def _request_operation(self, name, work, on_success=None, on_done=None, *, output=None, on_error=None):
        if self.__dict__.get('_maintenance_uncertain'):
            guard = self.__dict__.get('maintenance_guard')
            message = guard.last_error if guard is not None else 'Restart Windows before running more maintenance. A timed-out command may have left a Windows helper running.'
            self._show_toast('Command state unknown', message, 'warning')
            return False
        if self._update_installing or self._update_downloading or self.workers.busy():
            self._show_toast('Operation in progress', 'Wait for the current operation to finish.', 'warning')
            return False
        def done():
            self._set_maintenance_state(False)
            if on_done:
                on_done()
            elif self.__dict__.get('_turbo_refresh_pending'):
                self._load_turbo_states()
            if self.__dict__.get('_close_when_idle'):
                self._on_close()
        def error(exc):
            self.operation_label.configure(text=f'Failed · {name}: {exc}', text_color=COL_RED)
            self._show_toast(f'{name} failed', str(exc), 'error')
            if output:
                self._log_section(output, f'{name} failed: {exc}', 'err')
            if on_error:
                on_error(exc)
            if name == 'Resurrection':
                for step, (state, detail) in self.__dict__.get('_resurrection_states', {}).copy().items():
                    if state == 'running':
                        self._set_resurrection_step(step, 'failed', str(exc))
                self.lbl_status.configure(text='Failed · See sequence output', text_color=COL_RED)
            show_uncertainty()
        def completion_unknown():
            return any(getattr(manager, 'completion_unknown', False) is True for manager in (self.cmd_runner, self.disk_opt))
        def guarded_work():
            try:
                return work()
            finally:
                guard = self.__dict__.get('maintenance_guard')
                if completion_unknown() and guard is not None:
                    guard.mark_unknown()
        def show_uncertainty():
            if completion_unknown():
                self._maintenance_uncertain = True
                guard = self.__dict__.get('maintenance_guard')
                message = guard.last_error if guard is not None else 'Command completion unknown · Restart Windows before further maintenance'
                self.operation_label.configure(text=f'Stopped · {message}', text_color=COL_WARNING)
        def delivered(result):
            if completion_unknown():
                self._maintenance_uncertain = True
            if on_success:
                on_success(result)
            show_uncertainty()
        started = self.workers.start(name, guarded_work, on_success=delivered, on_error=error, on_done=done)
        if started:
            if output:
                self._open_operation_output(output)
            self._set_maintenance_state(True)
            self.operation_label.configure(text=f'Running · {name}', text_color=MUTED)
        return started

    def _show_result(self, name, result):
        success, message = result
        self.operation_label.configure(text=f'{"Completed" if success else "Failed / partial"} · {name}: {message}', text_color=COL_SUCCESS if success else COL_WARNING)
        self._show_toast(name, message, 'success' if success else 'warning')

    def _show_logged_result(self, name, result, output):
        self._log_section(output, f'{name}: {"completed" if result[0] else "failed / partial"} · {result[1]}')
        self._show_result(name, result)

    def update_dashboard(self):
        if self._shutdown.is_set():
            return
        self.workers.start('metrics', self.monitor.sample_fast, group='metrics', on_success=self._update_fast_gui, on_error=lambda exc: self.operation_label.configure(text=f'Metrics unavailable: {exc}'), on_done=lambda: self.after(3000, self.update_dashboard))

    def _load_metadata(self):
        if self._shutdown.is_set():
            return
        self.workers.start('hardware', self.monitor.sample_metadata, group='hardware', on_success=self._update_metadata_gui, on_done=lambda: self.after(120000, self._load_metadata))

    def _update_fast_gui(self, sample):
        self.dash_uptime_val.configure(text=f"Uptime: {sample['uptime']}")
        cpu = sample['cpu']
        self.dash_cpu_val.configure(text='—' if cpu is None else f'{cpu:.1f}%')
        if cpu is not None:
            self.cpu_graph.add_value(cpu)
        if sample['ram'] is None:
            self.dash_ram_perc.configure(text='—', text_color=MUTED)
            self.dash_ram_val.configure(text='Memory unavailable')
        else:
            total_ram, available_ram, ram_percent = sample['ram']
            self.ram_graph.add_value(ram_percent)
            self.dash_ram_val.configure(text=f'{total_ram - available_ram:.1f} GB used / {total_ram:.1f} GB')
            self.dash_ram_perc.configure(text=f'{ram_percent:.1f}%', text_color=COL_WARNING if ram_percent >= 90 else TEXT)
        if sample['disk'] is None:
            self.dash_disk_bar.set(0)
            self.dash_disk_bar.configure(progress_color=MUTED)
            self.dash_disk_state.configure(text='Unavailable', text_color=COL_WARNING)
            self.dash_disk_val.configure(text='Drive information unavailable')
            self.dash_disk_perc.configure(text='—', text_color=MUTED)
        else:
            total_disk, free_disk, disk_percent = sample['disk']
            self.dash_disk_bar.set(max(0, min(1, disk_percent / 100)))
            disk_color = COL_RED if disk_percent >= 95 else COL_WARNING if disk_percent >= 85 else COL_GOLD
            self.dash_disk_bar.configure(progress_color=disk_color)
            self.dash_disk_state.configure(text='Low free space' if disk_percent >= 90 else 'Space available', text_color=disk_color if disk_percent >= 85 else MUTED)
            self.dash_disk_val.configure(text=f'{free_disk:.1f} GB free / {total_disk:.1f} GB')
            self.dash_disk_perc.configure(text=f'{disk_percent:.1f}% used', text_color=disk_color if disk_percent >= 85 else TEXT)
        percent, power = sample['battery']
        self.dash_battery.configure(text=f'Power: {power}' if percent is None else f'Battery: {percent}% · {power}')

    def _update_metadata_gui(self, sample):
        self.dash_os.configure(text=sample['os'])
        cpu_name = (sample['cpu_name'] or 'Processor details unavailable').splitlines()[0]
        # Keep the card compact; full diagnostics still come from the Windows system.
        self.dash_cpu_name.configure(text=cpu_name.split(' with ')[0].split(' @ ')[0])
        self.dash_ram_info.configure(text=sample['ram_info'] or 'Memory details unavailable')
        self.dash_disk_info.configure(text=sample['disk_model'] or 'Disk details unavailable')

    def _check_updates_thread(self):
        self.workers.start('windows-updates', self.monitor.get_windows_update_status, group='windows-updates', on_success=lambda result: self._update_updates_gui(*result), on_error=lambda exc: self._update_updates_gui(-1, -1, 'Check failed'))

    def _update_updates_gui(self, mandatory, optional, status):
        self.lbl_update_status.configure(text=str(status), text_color=COL_SUCCESS if mandatory == optional == 0 else COL_WARNING if mandatory > 0 or optional > 0 else MUTED)

    def refresh_drives(self):
        def failed(exc):
            self._set_drives([])
            self.log_disk_msg(f'Drive query failed: {exc}')
            if 'drive_detail' in self.__dict__:
                self.drive_detail.configure(text=f'Drive information unavailable: {exc}', text_color=COL_WARNING)
        self.workers.start('drive-list', self.disk_opt.get_drive_info, group='drive-list', on_success=self._set_drives, on_error=failed)

    def _set_drives(self, drives):
        self._drive_info = list(drives)
        values = [str(drive['letter']) for drive in drives]
        self._drive_values = values
        if 'drive_menu' not in self.__dict__:
            return
        self.drive_menu.configure(values=values or ['No drives'])
        if self.selected_drive.get() not in values:
            self.selected_drive.set(values[0] if values else 'No drives')
        self.drive_menu.configure(state='normal' if values else 'disabled')
        self._drive_selected()

    def _drive_selected(self, value=None):
        selected = value or self.selected_drive.get()
        info = next((row for row in self.__dict__.get('_drive_info', ()) if row['letter'] == selected), None)
        available = info is not None and info.get('available', True)
        busy = self.workers.busy() or self._update_downloading or self._update_installing or self.__dict__.get('_maintenance_uncertain')
        self.btn_optimize_drive.configure(state='normal' if available and not busy else 'disabled')
        if not available:
            text = 'No available local drive' if info is None else f"{selected} · Unavailable: {info.get('error', 'Cannot read drive')}"
        elif info.get('total_bytes'):
            text = f"{selected} · {info.get('type', 'Local')} drive · {info['free_bytes'] / 1024**3:.1f} GB free / {info['total_bytes'] / 1024**3:.1f} GB"
        else:
            text = f'{selected} · Capacity unavailable'
        self.drive_detail.configure(text=text, text_color=MUTED if available else COL_WARNING)
        if 'drive_capacity' in self.__dict__:
            self.drive_capacity.set(max(0, min(1, (info.get('used_percent') or 0) / 100)) if info else 0)

    def _cycle_drive(self, direction):
        if self.drive_menu.cget('state') == 'disabled' or not self._drive_values:
            return
        current = self.selected_drive.get()
        index = self._drive_values.index(current) if current in self._drive_values else 0
        value = self._drive_values[(index + direction) % len(self._drive_values)]
        self.selected_drive.set(value)
        self._drive_selected(value)

    def _set_preview_status(self, message, color=MUTED):
        """Keep the same preview result visible from Dashboard and Cleanup."""
        self._preview_summary = str(message)
        for name in ('dash_preview_status', 'preview_label'):
            widget = self.__dict__.get(name)
            if widget is not None:
                settings = {'text': self._preview_summary, 'text_color': color}
                widget.configure(**settings)

    def run_preview_temp(self):
        previous = getattr(self, '_preview_summary', 'Not scanned yet')
        before = self.cleanup_mgr.last_result
        self._set_preview_status('Scanning temporary files… No files deleted', COL_GOLD)
        def show(result):
            count, size = result
            self._show_temp_result(count, size, self.cleanup_mgr.last_result, preview=True)
        started = self._request_operation(
            'Temporary file analysis', lambda: self.cleanup_mgr.preview_temp_files(progress_callback=self.log_msg), show,
            output='clean_log', on_error=lambda exc: self._show_temp_failure(exc, before, preview=True))
        if started is False:
            self._set_preview_status(previous)

    def _show_temp_result(self, count, size, result, *, preview, state=None):
        skipped = tuple(str(item) for item in getattr(result, 'skipped', ()))
        errors = tuple(str(item) for item in getattr(result, 'errors', ()))
        partial = bool(skipped or errors)
        state = state or ('failed' if errors and not count else 'partial' if partial else 'completed')
        title = f'{"Analysis" if preview else "Cleanup"} {state}'
        if preview:
            title += ' — No files deleted'
        amount = f'{size / 1024**3:.2f} GB' if size >= 1024**3 else f'{size / 1024**2:.1f} MB'
        totals = f'{count:,} candidates · about {amount} recoverable' if preview else f'{count:,} files deleted · {amount} freed'
        issues = f'{len(skipped):,} skipped · {len(errors):,} errors'
        color = COL_RED if state == 'failed' else COL_WARNING if partial else COL_SUCCESS
        self._set_preview_status(f'{title}\n{totals}\n{issues}', color)
        self.operation_label.configure(text=title, text_color=color)
        labels = {'locked': 'In use (Windows sharing/lock violation)',
                  'access_denied': 'Access denied by Windows', 'disappeared': 'No longer present',
                  'reparse_point': 'Reparse points refused', 'hard_link': 'Hard links refused',
                  'case_sensitive': 'Case-sensitive directories refused',
                  'identity_unverified': 'Object identity could not be verified',
                  'unapproved_root': 'Outside authorized paths',
                  'unsupported_path': 'Unsupported path format', 'ambiguous_path': 'Ambiguous path refused',
                  'unsupported_platform': 'Windows handle protection unavailable',
                  'not_directory': 'Expected directory unavailable', 'not_regular': 'Nonregular objects refused',
                  'location_unavailable': 'Temporary location could not be verified',
                  'filesystem_error': 'Other filesystem errors', 'unexpected_error': 'Other recorded errors',
                  'progress_callback': 'Progress reporting error', 'unknown': 'Other recorded reasons'}
        counts = getattr(result, 'skipped_counts', {})
        groups = [f'{labels.get(reason, reason)}: {value:,}' for reason, value in counts.items()]
        # Snapshot all original records: the bounded live log is not the diagnostic archive.
        self._cleanup_diagnostics = tuple([title, totals, issues, *groups,
            *(f'SKIPPED · {item}' for item in skipped), *(f'ERROR · {item}' for item in errors)]) if partial else ()
        button = self.__dict__.get('cleanup_reasons_button')
        if button is not None:
            button.configure(state='normal' if partial else 'disabled')
        for line in (title, totals, issues, *groups):
            self.log_msg(line)
        if partial:
            self.log_msg('View reasons: all original skipped/error details are available above.')

    def _show_temp_failure(self, exc, before, *, preview):
        current = self.cleanup_mgr.last_result
        # Only a result created by this pass may supply actual progress totals.
        result = CleanupResult(preview=preview)
        if current is not before and getattr(current, 'preview', None) is preview:
            result.count, result.bytes = current.count, current.bytes
            result.skipped, result.errors = list(current.skipped), list(current.errors)
            result.issues = list(getattr(current, 'issues', ()))
        result.add_issue('error', None, exc)
        self._show_temp_result(result.count, result.bytes, result, preview=preview,
                               state='interrupted' if result.count else 'failed')

    def _show_cleanup_diagnostics(self):
        details = self.__dict__.get('_cleanup_diagnostics', ())
        if not details:
            return
        dialog = ctk.CTkToplevel(self)
        dialog.title('Temporary files · Reasons and original details')
        dialog.geometry('820x480')
        dialog.minsize(500, 300)
        dialog.transient(self)
        text = ctk.CTkTextbox(dialog, wrap='word', font=self._font(12))
        text.pack(fill='both', expand=True, padx=12, pady=12)
        text.insert('1.0', '\n'.join(details))
        text.configure(state='disabled')
        text._textbox.configure(takefocus=1)
        dialog.bind('<Escape>', lambda event: dialog.destroy())
        dialog.after(50, text.focus_set)

    def run_clean_temp(self):
        if not messagebox.askyesno('Clean temporary files now', 'Permanently delete eligible files in validated temporary folders?\n\nNo analysis is required. Files are checked as they are deleted; locked and protected items are skipped. Results may differ from an earlier analysis.\n\nDeletion cannot be undone through the Recycle Bin.', parent=self):
            return
        before = self.cleanup_mgr.last_result
        self._request_operation('Temporary file cleanup',
            lambda: self.cleanup_mgr.clean_temp_files(progress_callback=self.log_msg),
            lambda result: self._show_temp_result(*result, self.cleanup_mgr.last_result, preview=False), output='clean_log',
            on_error=lambda exc: self._show_temp_failure(exc, before, preview=False))

    def run_empty_recycle(self):
        if not messagebox.askyesno('Empty Recycle Bin', 'Permanently delete every item in the Recycle Bin?\nThese items cannot be recovered through the Recycle Bin.', parent=self):
            return
        self._request_operation('Empty Recycle Bin', self.cleanup_mgr.empty_recycle_bin, lambda result: self._show_logged_result('Recycle Bin', result, 'clean_log'), output='clean_log')

    def run_cleanmgr(self):
        try:
            if self.cleanup_mgr.open_disk_cleanup() is not True:
                raise RuntimeError('Windows Disk Cleanup could not be opened.')
            self.operation_label.configure(text='Opened · Windows Disk Cleanup · Continue in Windows', text_color=MUTED)
        except Exception as exc:
            self._show_toast('Disk Cleanup', str(exc), 'error')

    def _set_quick_cleanup_status(self, message, color=MUTED):
        self._quick_cleanup_summary = str(message)
        label = self.__dict__.get('quick_cleanup_status')
        if label is not None:
            label.configure(text=self._quick_cleanup_summary, text_color=color)

    def _quick_cleanup_progress(self, finished, total, result):
        bar = self.__dict__.get('quick_cleanup_bar')
        if bar is not None:
            bar.set(finished / total)
        status = 'Completed' if result.success else 'Partial / failed'
        self._set_quick_cleanup_status(
            f'{finished}/{total} automatic steps attempted · {result.name}: {status}',
            MUTED if result.success else COL_WARNING)

    def _run_quick_cleanup_sequence(self):
        from modules.quick_cleanup import run_quick_cleanup
        return run_quick_cleanup(
            self.cleanup_mgr, self.cmd_runner, self.log_msg,
            cancel=self._quick_cleanup_cancel,
            progress=lambda finished, total, result: self.dispatcher.post(
                self._quick_cleanup_progress, finished, total, result, critical=True))

    def _finish_quick_cleanup(self, result):
        """Show actual results; never describe the external Windows UI as completed."""
        self.last_quick_cleanup_result = result
        attempted = len(result.steps)
        successes = sum(1 for item in result.steps if item.success)
        if 'quick_cleanup_bar' in self.__dict__:
            self.quick_cleanup_bar.set(attempted / 3)
        details = '; '.join(
            f'{step.name}: {"completed" if step.success else "partial / failed"}'
            for step in result.steps)
        if result.error:
            details = f'{details} · {result.error}' if details else result.error
        self.log_msg(f'Quick cleanup: {result.status} · {attempted}/3 attempted · {details}')
        # Only attempt the launch after all three internal steps have returned
        # and no command state, cancellation, or close request remains uncertain.
        ready = (attempted == 3
                 and not self._quick_cleanup_cancel.is_set()
                 and not getattr(self.cmd_runner, 'completion_unknown', False)
                 and not self.__dict__.get('_close_when_idle', False))
        external = 'Windows Disk Cleanup not opened'
        if ready:
            try:
                if self.cleanup_mgr.open_disk_cleanup() is not True:
                    raise RuntimeError('Windows Disk Cleanup could not be opened.')
                external = 'Windows Disk Cleanup opened · choose and confirm categories in Windows'
            except Exception as exc:
                external = f'Windows Disk Cleanup launch failed: {exc}'
                self.log_msg(external)
        elif getattr(self.cmd_runner, 'completion_unknown', False):
            external = 'Windows Disk Cleanup not opened · command completion unknown'
        elif attempted < 3:
            external = 'Windows Disk Cleanup not opened · sequence stopped'
        else:
            external = 'Windows Disk Cleanup not opened · closing or cancellation requested'
        completed = result.status == 'completed' and external.startswith('Windows Disk Cleanup opened')
        color = COL_SUCCESS if completed else COL_WARNING
        summary = (f'{result.status.capitalize()} · {successes}/3 automatic steps completed '
                   f'({attempted} attempted).\n{external}')
        self._set_quick_cleanup_status(summary, color)
        self.operation_label.configure(
            text=f'Quick cleanup · {result.status} · {external}',
            text_color=color)

    def run_quick_cleanup(self):
        """A single informed opt-in covers all three destructive in-app operations."""
        if self._update_installing or self._update_downloading or self.workers.busy():
            self._show_toast('Operation in progress',
                             'Wait for the current operation to finish.', 'warning')
            return False
        approved = messagebox.askyesno(
            'Confirm quick cleanup',
            'Run the following cleanup operations in sequence?\n\n'
            '1. Permanently delete eligible files in validated temporary folders.\n'
            '2. Permanently empty the ENTIRE Recycle Bin.\n'
            '3. Remove superseded Windows components using DISM.\n'
            '4. OPEN Windows Disk Cleanup for your manual selection and confirmation.\n\n'
            'Deletion is irreversible, including through Windows restore points. '
            'Some files may be skipped; DISM may take time or require a restart. '
            'Save your work first.\n\nContinue?',
            parent=self)
        if not approved:
            return False
        self._quick_cleanup_cancel.clear()
        accepted = self._request_operation(
            'Quick cleanup', self._run_quick_cleanup_sequence,
            self._finish_quick_cleanup,
            on_error=lambda exc: self._set_quick_cleanup_status(
                f'Quick cleanup failed: {exc}', COL_WARNING))
        if accepted:
            self.quick_cleanup_bar.set(0)
            self._set_quick_cleanup_status('Starting · 0/3 automatic steps attempted')
            self._set_section_log_open('clean_log', True)
        return accepted

    def run_deep_clean(self):
        self.run_cmd('DISM /Online /Cleanup-Image /StartComponentCleanup', 'Component store cleanup', log=self.log_msg, output='clean_log')

    def run_optimize_drive(self):
        letter = self.selected_drive.get()
        import re
        if not re.fullmatch(r'[A-Za-z]:', letter) or letter not in self._drive_values:
            self._show_toast('Select a drive', 'Choose a valid drive letter.', 'warning')
            return
        if messagebox.askyesno('Optimize drive', f'Run Windows optimization on {letter}?\nThis operation can take several minutes.', parent=self):
            self._request_operation('Drive optimization', lambda: self.disk_opt.analyze_optimize_drive(letter, progress_callback=self.log_disk_msg), lambda success: self._show_logged_result('Drive optimization', (success is True, 'See optimization output for details.'), 'disk_log'), output='disk_log')

    def run_dfrgui(self):
        try:
            if self.disk_opt.open_optimize_gui() is not True:
                raise RuntimeError('Windows drive optimization could not be opened.')
            self.operation_label.configure(text='Opened · Windows drive optimization', text_color=MUTED)
        except Exception as exc:
            self._show_toast('Drive optimization', str(exc), 'error')

    def run_cmd(self, cmd, desc, *, log=None, output='tools_log'):
        log = log or self.log_tools_msg
        detail = 'Network connections may be interrupted and a restart may be needed.' if 'winsock' in cmd.lower() else 'The operation can take several minutes. Save your work first.'
        if not messagebox.askyesno(desc, f'Run {desc}?\n{detail}', parent=self):
            return
        def work():
            log(f'> {desc}')
            success = self.cmd_runner.run_command_stream(cmd, desc, log)
            log(f'{desc}: {"completed" if success is True else "failed"}')
            return success is True, 'Restart required · see command output.' if getattr(self.cmd_runner, 'restart_required', False) else 'See command output for details.'
        self._request_operation(desc, work, lambda result: self._show_result(desc, result), output=output)

    def run_launch(self, target, desc):
        try:
            if target in ('ms-settings:appsfeatures', 'ms-settings:startupapps', 'ms-settings:windowsupdate', 'ms-settings:windowsupdate-optionalupdates'):
                os.startfile(target)
            elif target == 'appwiz.cpl':
                from modules.commands import system_executable
                subprocess.Popen([system_executable('control.exe'), 'appwiz.cpl'], shell=False)
            else:
                raise ValueError('Unsupported Windows settings destination')
            self.operation_label.configure(text=f'Opened · {desc} · Continue in Windows', text_color=MUTED)
            if target in ('ms-settings:appsfeatures', 'ms-settings:startupapps', 'appwiz.cpl'):
                for label_name in ('apps_status', 'startup_status'):
                    label = self.__dict__.get(label_name)
                    if label is not None:
                        label.configure(text=f'Opened {desc} · Changes are managed in Windows.', text_color=MUTED)
        except Exception as exc:
            self.operation_label.configure(text=f'Failed · {desc}: {exc}', text_color=COL_WARNING)
            if target in ('ms-settings:appsfeatures', 'ms-settings:startupapps', 'appwiz.cpl'):
                for label_name in ('apps_status', 'startup_status'):
                    label = self.__dict__.get(label_name)
                    if label is not None:
                        label.configure(text=f'{desc} unavailable: {exc}', text_color=COL_WARNING)
            self._show_toast(desc, str(exc), 'error')

    def run_battery_report(self):
        path = Path(os.environ.get('USERPROFILE', str(Path.home()))) / 'battery_report.html'
        def report():
            from modules.commands import system_executable
            subprocess.run([system_executable('powercfg.exe'), '/batteryreport', '/output', str(path)], stdin=subprocess.DEVNULL, shell=False, check=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), capture_output=True, timeout=60)
            return path
        def saved(result):
            self.operation_label.configure(text=f'Completed · Battery report saved to {result}', text_color=COL_SUCCESS)
            self.log_tools_msg(f'Battery report saved to {result}')
            try:
                os.startfile(str(result))
            except OSError as exc:
                self._show_toast('Report saved', f'{result}\nCould not open the report: {exc}', 'warning')
        self._request_operation('Battery report', report, saved, output='tools_log')

    def run_create_restore(self):
        if messagebox.askyesno('Create restore point', 'Create and verify a new Windows restore point?\nSystem protection must already be enabled. This may take a minute.', parent=self):
            self._request_operation('Restore point', lambda: self.restore_mgr.create_restore_point('Panacea Manual Point'), lambda result: self._show_logged_result('Restore point', result, 'tools_log'), output='tools_log')

    def run_windows_update(self):
        self.run_launch('ms-settings:windowsupdate', 'Windows Update')

    def run_view_optional_updates(self):
        self.run_launch('ms-settings:windowsupdate-optionalupdates', 'Optional updates')

    def _read_turbo_states(self):
        def read(fn, invert=False):
            try:
                value = fn()
                return None if value is None else (not value if invert else bool(value))
            except Exception:
                return None
        try:
            power = self.perf_mgr.get_power_plan()
            power = None if power is None else power == 'high'
        except Exception:
            power = None
        states = {'power': power, 'visual': read(self.perf_mgr.get_visual_effects, True), 'sysmain': read(self.perf_mgr.get_sysmain_status, True), 'wsearch': read(self.perf_mgr.get_wsearch_status, True), 'spooler': read(self.perf_mgr.get_spooler_status, True)}
        return states, read(self.perf_mgr.is_turbo_active)

    def _load_turbo_states(self):
        generation = self.__dict__.get('_turbo_generation', 0) + 1
        self._turbo_generation = generation
        self._turbo_refresh_pending = True
        self._turbo_refreshing = True
        for switch in self.__dict__.get('turbo_switches', {}).values():
            switch.configure(state='disabled')
        if 'master_switch' in self.__dict__:
            self.master_switch.configure(state='disabled')
        if 'btn_restore_turbo' in self.__dict__:
            self.btn_restore_turbo.configure(state='disabled')
        if self.workers.busy():
            return
        if self.workers.busy('turbo-state'):
            return
        self._turbo_refresh_pending = False
        def read():
            states = self._read_turbo_states()
            return states, self.perf_mgr.get_saved_settings()
        def apply(result):
            if self.workers.busy() or generation != self._turbo_generation:
                self._turbo_refresh_pending = True
                return  # A late read must not overwrite an in-flight mutation.
            self._apply_turbo_states(result[0])
            self._apply_saved_turbo(result[1])
        def failed(exc):
            if generation == self._turbo_generation:
                states = {key: None for key in ('power', 'visual', 'sysmain', 'wsearch', 'spooler')}
                self._apply_turbo_states((states, None))
                self._apply_saved_turbo(None)
        def done():
            if self._turbo_refresh_pending:
                self._load_turbo_states()
            else:
                self._turbo_refreshing = False
                self._set_maintenance_state(self.workers.busy() or self._update_downloading or self._update_installing)
        self.workers.start('turbo-state', read, group='turbo-state', on_success=apply,
                           on_error=failed, on_done=done)

    def _apply_saved_turbo(self, saved):
        self._turbo_saved = saved
        if 'btn_restore_turbo' not in self.__dict__:
            return
        busy = self.workers.busy() or self._update_downloading or self._update_installing or self.__dict__.get('_maintenance_uncertain')
        text = 'Saved originals unavailable · retry Refresh state' if saved is None else f'{len(saved)} original settings saved · available for restoration' if saved else 'No saved changes · switches show the current Windows state'
        self.turbo_saved_label.configure(text=text, text_color=COL_WARNING if saved is None else MUTED)
        self.btn_restore_turbo.configure(state='normal' if saved and not busy else 'disabled')

    def _restore_saved_turbo(self):
        self._request_operation('Restore Turbo settings', lambda: self.perf_mgr.set_turbo(False),
                                lambda result: self._show_result('Restore Turbo settings', result), self._load_turbo_states)

    def _apply_turbo_states(self, result):
        states, master = result
        self._turbo_states, self._turbo_master = states, master
        if 'turbo_switches' not in self.__dict__:
            return
        busy = self.workers.busy() or self._update_downloading or self._update_installing or self.__dict__.get('_maintenance_uncertain')
        for key, state in states.items():
            if state is not None:
                self.turbo_vars[key].set(state)
            self.turbo_switches[key].configure(text='Unknown' if state is None else 'Active' if state else 'Inactive', state='disabled' if busy or state is None else 'normal')
        if master is not None:
            if 'master_var' in self.__dict__:
                self.master_var.set(master)
            else:
                self.master_switch.select() if master else self.master_switch.deselect()
        self.master_switch.configure(text='Unknown' if master is None else 'Active' if master else 'Inactive', state='disabled' if busy or master is None else 'normal')

    def _turbo_toggle_changed(self, key, on_fn, off_fn):
        requested = self.turbo_vars[key].get()
        if not self._request_operation('Turbo setting', on_fn if requested else off_fn, lambda result: self._show_result('Turbo setting', result), self._load_turbo_states):
            self._load_turbo_states()

    def _master_toggle_changed(self):
        requested = bool(self.master_switch.get())
        if not self._request_operation('Turbo settings', lambda: self.perf_mgr.set_turbo(requested), lambda result: self._show_result('Turbo settings', result), self._load_turbo_states):
            self._load_turbo_states()

    def _cancel_resurrect(self):
        self._resurrect_cancel.set()
        self.btn_resurrect_cancel.configure(state='disabled', text='Cancellation requested…')
        self.log_god_msg('Cancellation requested; the current command will finish.', 'warn')

    def _resurrection_progress(self, progress, text):
        self.progress_bar.set(progress)
        self.lbl_status.configure(text=text, text_color=MUTED)

    def _set_resurrection_step(self, name, state, detail=''):
        self.__dict__.setdefault('_resurrection_states', {})[name] = (state, detail)
        label = self.__dict__.get('_resurrection_rows', {}).get(name)
        if label is not None:
            color = {'completed': COL_SUCCESS, 'failed': COL_RED, 'running': COL_GOLD}.get(state, MUTED)
            label.configure(text={'pending': 'Not started', 'running': 'Running…', 'completed': 'Completed',
                                  'failed': 'Failed / partial', 'not run': 'Not run'}.get(state, state), text_color=color)
        explanation = self.__dict__.get('_resurrection_info_labels', {}).get(name)
        if explanation is not None:
            basic = self.RESURRECTION_HELP[name]
            explanation.configure(text=f'{basic}\nResult: {detail}' if detail else basic)

    def _finish_resurrection(self, result):
        self.last_resurrection_result = result
        attempted = {row['name']: row for row in result['steps']}
        for name in self.RESURRECTION_STEPS:
            row = attempted.get(name)
            self._set_resurrection_step(name, 'completed' if row and row['success'] else 'failed' if row else 'not run', row['message'] if row else '')
        text = f"{result['status'].capitalize()} · {len(result['steps'])}/{result['total']} steps finished"
        color = COL_SUCCESS if result['status'] == 'completed' else COL_WARNING if result['status'] in ('partial', 'cancelled') else COL_RED
        self.lbl_status.configure(text=text, text_color=color)
        self.operation_label.configure(text=text, text_color=color)
        self.log_god_msg(text, 'head')
        if result.get('error'):
            self.log_god_msg(result['error'], 'err')

    def _run_resurrection_sequence(self):
        from modules.operations import OperationStep, run_sequence
        from modules.commands import validate_drive, system_executable
        import ntpath
        system_drive = validate_drive(ntpath.splitdrive(system_executable('cmd.exe'))[0])
        uncertain = False
        log = self.log_god_msg
        def cleanup(fn, **kwargs):
            count, size = fn(**kwargs)
            detail = self.cleanup_mgr.last_result
            errors, skipped = getattr(detail, 'errors', []), getattr(detail, 'skipped', [])
            return not errors and not skipped, f'{count} files · {size / 1048576:.1f} MB freed · {len(skipped)} skipped · {len(errors)} errors'
        def command(cmd, name):
            nonlocal uncertain
            success = self.cmd_runner.run_command_stream(cmd, name, lambda msg: log(msg)) is True
            if getattr(self.cmd_runner, 'completion_unknown', False) is True:
                uncertain = True
                return False, 'Command completion unknown · sequence stopped; restart Windows before retrying.'
            return success, 'Restart required.' if getattr(self.cmd_runner, 'restart_required', False) else 'See command output.'
        def optimize():
            nonlocal uncertain
            success = self.disk_opt.analyze_optimize_drive(system_drive, progress_callback=log) is True
            if getattr(self.disk_opt, 'completion_unknown', False) is True:
                uncertain = True
                return False, 'Drive command completion unknown · sequence stopped; restart Windows before retrying.'
            return success, 'See drive output.'
        steps = [OperationStep('Restore point', lambda: self.restore_mgr.create_restore_point('Panacea Resurrection restore point'), True),
                 OperationStep('Browser caches', lambda: cleanup(self.cleanup_mgr.clean_browser_caches)),
                 OperationStep('Temporary files', lambda: cleanup(self.cleanup_mgr.clean_temp_files, progress_callback=log)),
                 OperationStep('Recycle Bin', self.cleanup_mgr.empty_recycle_bin),
                 OperationStep('DNS cache', lambda: command('ipconfig /flushdns', 'DNS flush')),
                 OperationStep('Network reset', lambda: command('netsh winsock reset', 'Network reset')),
                 OperationStep('Drive optimization', optimize),
                 OperationStep('Disk health scan', lambda: command(f'chkdsk {system_drive} /scan /perf', 'Disk health scan')),
                 OperationStep('Windows image health', lambda: command('DISM /Online /Cleanup-Image /CheckHealth', 'Image health')),
                 OperationStep('System file scan', lambda: command('sfc /scannow', 'System file scan'))]
        def tracked(step):
            def action():
                self.dispatcher.post(self._set_resurrection_step, step.name, 'running', critical=True)
                return step.action()
            return OperationStep(step.name, action, step.critical)
        steps = [tracked(step) for step in steps]
        def progress(completed, total, result):
            log(f'{"Completed" if result.success else "Failed / partial"}: {result.name} · {result.message}', 'info' if result.success else 'err')
            self.dispatcher.post(self._resurrection_progress, completed / total, f'{completed}/{total} finished · {result.name}', critical=True)
            self.dispatcher.post(self._set_resurrection_step, result.name, 'completed' if result.success else 'failed', result.message, critical=True)
        result = run_sequence(steps, cancel=lambda: uncertain or self._shutdown.is_set() or self._resurrect_cancel.is_set(), progress=progress)
        if uncertain:
            result.status = 'partial' if any(row.success for row in result.steps) else 'failed'
        if result.steps and not result.steps[0].success:
            log('Stopped before cleanup: a new restore point could not be verified. Enable System Protection in Windows and retry.', 'err')
        return {'status': result.status, 'steps': [{'name': row.name, 'success': row.success, 'message': row.message} for row in result.steps], 'total': len(steps), 'error': result.error}

    def run_god_mode(self):
        if self._update_installing or self._update_downloading or self.workers.busy():
            self._show_toast('Operation in progress', 'Wait for the current operation to finish.', 'warning')
            return
        if not messagebox.askyesno('Confirm Resurrection', 'Run all 10 maintenance steps?\n\nAfter verifying a new restore point, Panacea permanently deletes browser caches, temporary files and ALL Recycle Bin items, then resets network settings and scans the system.\n\nDeletion cannot be undone through the Recycle Bin. Network connections may be interrupted; a restart may be needed. Save your work first.', parent=self):
            return
        self._resurrect_cancel.clear()
        def done():
            self.btn_resurrect_cancel.pack_forget()
            self.btn_resurrect_start.configure(text='Start sequence')
        if self._request_operation('Resurrection', self._run_resurrection_sequence, self._finish_resurrection, done, output='god_log'):
            for name in self.RESURRECTION_STEPS:
                self._set_resurrection_step(name, 'pending')
            self.btn_resurrect_start.configure(text='Maintenance running…')
            self.btn_resurrect_cancel.configure(state='normal', text='Cancel after current step')
            self.btn_resurrect_cancel.pack(side='left', padx=10)
            self.progress_bar.set(0)
            self.lbl_status.configure(text='Starting · Verifying restore point', text_color=MUTED)

    def _check_app_update(self):
        from modules.updater import UpdateClient
        if self._shutdown.is_set() or self.workers.busy('app-update') or self._update_installing:
            return
        self.app_update_status.configure(text='Checking Panacea updates…', text_color=MUTED)
        self.btn_check_update.configure(state='disabled')
        def check():
            client = UpdateClient(GITHUB_REPO, VERSION)
            return client, client.check()
        def checked(result):
            self.update_client, self._release = result
            self.update_actions.grid_forget()
            if self._release is None:
                self.app_update_status.configure(text=f'Panacea {VERSION} is up to date', text_color=MUTED)
            else:
                self.app_update_status.configure(text=f'Panacea {self._release.version} available', text_color=COL_BLUE)
                self.update_actions.grid(row=1, column=0, columnspan=3, sticky='w', padx=18)
        def failed(exc):
            self.app_update_status.configure(text=f'Update check failed: {exc}', text_color=COL_WARNING)
            self.btn_check_update.configure(text='Retry check')
        self.workers.start('app-update-check', check, group='app-update', on_success=checked, on_error=failed, on_done=lambda: self.btn_check_update.configure(state='normal'))

    def _defer_update(self):
        self.update_actions.grid_forget()
        self.app_update_status.configure(text='Update deferred · Use Check updates when ready', text_color=MUTED)

    def _show_release_notes(self):
        if self._release:
            webbrowser.open(self._release.release_url)

    @staticmethod
    def _is_newer(remote, local):
        from modules.updater import is_newer
        return is_newer(remote, local)

    def _auto_update(self):
        if not self._release:
            return
        if not getattr(sys, 'frozen', False):
            webbrowser.open(self._release.release_url)
            return
        if self.workers.busy() or self.workers.busy('app-update') or self._update_installing:
            self._show_toast('Operation in progress', 'Finish the current operation before updating.', 'warning')
            return
        if not messagebox.askyesno('Install verified update', f'Download and verify Panacea {self._release.version}?\nThe app stays open if verification or installation fails.', parent=self):
            return
        self._update_cancel.clear()
        self._update_downloading = True
        release, client = self._release, self.update_client
        def download():
            import tempfile
            directory = Path(tempfile.mkdtemp(prefix='Panacea-download-'))
            self._update_dir = directory
            def progress(received, total):
                self.dispatcher.post(self._update_download_progress, received, total, key='download-progress')
                return not self._update_cancel.is_set() and not self._shutdown.is_set()
            return client.download(release, directory, progress)
        def downloaded(staged):
            self._update_downloading = False
            self.app_update_status.configure(text='Verified · Preparing installation…', text_color=COL_BLUE)
            self._update_installing = True
            self._set_maintenance_state(True)
            def prepare():
                from modules.update_install import start_self_update
                return start_self_update(staged, Path(sys.executable), release, client)
            self.workers.start('prepare-update', prepare, group='update-install', on_success=self._update_prepared, on_error=self._update_failed)
        self.btn_update_install.configure(state='disabled')
        self.btn_check_update.configure(state='disabled')
        self._set_maintenance_state(True)
        self.app_update_status.configure(text='Downloading and verifying…', text_color=COL_BLUE)
        self.workers.start('download-update', download, group='app-update', on_success=downloaded, on_error=self._update_failed)

    def _update_download_progress(self, received, total):
        text = 'Verifying downloaded executable…' if total and received >= total else f'Downloading · {received * 100 // max(1, total)}%'
        self.app_update_status.configure(text=text, text_color=COL_BLUE)

    def _update_prepared(self, job):
        self._update_job = job
        self._poll_update_job()

    def _poll_update_job(self):
        if self._shutdown.is_set() or not self._update_job:
            return
        def status_ready(result):
            status = result.get('status', 'failed')
            self.app_update_status.configure(text=f"Update · {result.get('message') or status}", text_color=COL_BLUE)
            if status == 'ready':
                self._remove_update_download()
                self._update_installing = False
                self._on_close()
            elif status == 'failed':
                self._update_failed(RuntimeError(result.get('message', 'Installation failed; old app retained.')))
            else:
                self.after(750, self._poll_update_job)
        self.workers.start('update-status', self._update_job.poll, group='update-status', on_success=status_ready, on_error=self._update_failed)

    def _update_failed(self, exc):
        self._update_downloading = False
        self._update_installing = False
        self._update_job = None
        self._set_maintenance_state(False)
        self.btn_update_install.configure(state='normal', text='Retry install')
        self.btn_check_update.configure(state='normal')
        self.app_update_status.configure(text=f'Update failed: {exc}', text_color=COL_WARNING)
        self._remove_update_download()
        self._show_toast('Update failed', f'{exc}\nUse Release notes for manual download.', 'error')

    def _remove_update_download(self):
        # Never enumerate/delete updater or backup files. Download verification cleans
        # partial files; only remove an empty directory owned by this operation.
        directory = self._update_dir
        if directory is not None:
            try:
                directory.rmdir()
            except OSError:
                pass
        self._update_dir = None

    @staticmethod
    def _fit_window_size(width, height, work_width, work_height, scale):
        return min(width, max(1, int((work_width - 48) / scale))), min(height, max(1, int((work_height - 48) / scale)))

    def geometry(self, geometry_string=None):
        # CTk's pending Configure events can overwrite _current_width/height
        # while a new window is withdrawn. Preserve explicit size requests.
        if geometry_string is not None:
            width, height, _, _ = self._parse_geometry_string(geometry_string)
            if width is not None and height is not None:
                self._requested_window_size = (max(self._min_width, width), max(self._min_height, height))
        return super().geometry(geometry_string)

    def _center_and_show(self):
        requested_width, requested_height = self._requested_window_size
        self.update_idletasks()
        scale = self._get_window_scaling()
        try:
            import ctypes
            from ctypes import wintypes
            rect = wintypes.RECT()
            if not ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(rect), 0):
                raise OSError('Work area unavailable')
            width, height = self._fit_window_size(requested_width, requested_height, rect.right - rect.left, rect.bottom - rect.top, scale)
            self.minsize(min(760, width), min(420, height))
            self.geometry(f'{width}x{height}')
            self.update_idletasks()
            x = rect.left + max(0, int((rect.right - rect.left - width * scale) / 2))
            y = rect.top + max(0, int((rect.bottom - rect.top - height * scale) / 2))
            hwnd = ctypes.windll.user32.GetAncestor(self.winfo_id(), 2) or self.winfo_id()
            ctypes.windll.user32.SetWindowPos(hwnd, 0, x, y, 0, 0, 0x0001 | 0x0004)
        except Exception:
            pass
        self.deiconify()

    def _on_close(self):
        if self._update_installing:
            self._show_toast('Update installation in progress', 'Wait for installation to finish before closing Panacea.', 'warning')
            return
        if self.workers.busy():
            self._close_when_idle = True
            self._resurrect_cancel.set()
            if hasattr(self, '_quick_cleanup_cancel'):
                self._quick_cleanup_cancel.set()
            self.operation_label.configure(text='Closing after the current operation · No further sequence steps will start', text_color=COL_WARNING)
            return
        self._shutdown.set()
        self._resurrect_cancel.set()
        if hasattr(self, '_quick_cleanup_cancel'):
            self._quick_cleanup_cancel.set()
        self._update_cancel.set()
        self.monitor.close()
        self.workers.close()
        self.destroy()

    def _show_toast(self, title, message, msg_type='info'):
        colors = {'info': COL_BLUE, 'success': COL_SUCCESS, 'error': COL_RED, 'warning': COL_WARNING}
        toast = ctk.CTkToplevel(self)
        toast.overrideredirect(True)
        toast.attributes('-topmost', True)
        toast.configure(fg_color=SURFACE_ALT)
        width, height = 360, 110
        x = max(0, self.winfo_rootx() + self.winfo_width() - width - 16)
        y = max(0, self.winfo_rooty() + self.winfo_height() - height - 16)
        toast.geometry(f'{width}x{height}+{x}+{y}')
        ctk.CTkLabel(toast, text=title, text_color=colors.get(msg_type, COL_BLUE), font=self._font(13, True), anchor='w').pack(fill='x', padx=14, pady=(10, 2))
        ctk.CTkLabel(toast, text=str(message)[:500], text_color=TEXT, font=self._font(11), anchor='w', wraplength=330, justify='left').pack(fill='x', padx=14, pady=(0, 10))
        toast.after(6500, toast.destroy)


class LiveGraph(ctk.CTkFrame):
    def __init__(self, master, width=250, height=72, line_color=COL_BLUE, **kwargs):
        super().__init__(master, width=width, height=height, fg_color=SURFACE, **kwargs)
        self.canvas = ctk.CTkCanvas(self, width=width, height=height, bg=SURFACE, highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)
        self.width, self.height = width, height
        self.line_color = line_color
        self.points = [0.0] * 60
        self.canvas.bind('<Configure>', self._resized)
        self._draw_grid()
        self.fill_id = self.canvas.create_polygon(0, 0, fill='#3b342b' if line_color == COL_GOLD else '#24364c', outline='')
        self.line_id = self.canvas.create_line(0, 0, 0, 0, fill=line_color, width=2, smooth=True)

    def _resized(self, event):
        self.width, self.height = max(2, event.width), max(2, event.height)
        self.canvas.delete('grid')
        self._draw_grid()
        self.draw()

    def _draw_grid(self):
        for percent in (25, 50, 75):
            y = self.height * (1 - percent / 100)
            self.canvas.create_line(0, y, self.width, y, fill=BORDER, dash=(2, 4), tags='grid')

    def add_value(self, value):
        self.points = self.points[1:] + [max(0, min(100, float(value)))]
        self.draw()

    def draw(self):
        step = self.width / (len(self.points) - 1)
        coords = [coord for index, value in enumerate(self.points) for coord in (index * step, self.height * (1 - value / 100))]
        self.canvas.coords(self.line_id, *coords)
        self.canvas.coords(self.fill_id, *(coords + [self.width, self.height, 0, self.height]))
