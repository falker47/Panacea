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
from modules.cleanup import CleanupManager
from modules.disk import DiskOptimizer
from modules.commands import CommandRunner
from modules.logger import Logger
from modules.system_monitor import SystemMonitor
from modules.restore import RestoreManager
from modules.performance import PerformanceManager
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
        self._update_cancel = threading.Event()
        self._update_installing = False
        self._update_downloading = False
        self._release = self._update_job = self._update_dir = None
        self._maintenance_controls = []
        self._fonts = {}
        self._pending_logs = {}
        self._preview_summary = 'Not scanned yet · No files changed'
        self._drive_values = []
        self._turbo_states = {}
        self._turbo_master = None
        self.last_resurrection_result = None
        try:
            self.logger = Logger()
        except (OSError, KeyError):
            self.logger = None
        self.cleanup_mgr, self.disk_opt = CleanupManager(), DiskOptimizer()
        self.cmd_runner, self.monitor = CommandRunner(), SystemMonitor()
        self.restore_mgr, self.perf_mgr = RestoreManager(), PerformanceManager()
        try:
            self.iconbitmap(resource_path('assets/panacea_icon.ico'))
        except Exception:
            pass
        self._load_icons()
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._setup_sidebar()
        self._setup_update_bar()
        self.frames = {}
        for name, attr in [('Dashboard', 'dashboard'), ('Cleaning', 'cleaning'), ('Disk', 'disk'), ('Tools', 'tools'), ('Apps', 'apps'), ('Turbo', 'turbo'), ('Resurrect', 'resurrect')]:
            frame = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
            self.frames[name] = frame
            setattr(self, f'frame_{attr}', frame)
        self._setup_functions = {'Dashboard': self._setup_dashboard_frame, 'Cleaning': self._setup_cleaning_frame,
                                 'Disk': self._setup_disk_frame, 'Tools': self._setup_tools_frame,
                                 'Apps': self._setup_apps_frame, 'Turbo': self._setup_turbo_frame,
                                 'Resurrect': self._setup_resurrect_frame}
        self._built_frames = set()
        self.operation_label = ctk.CTkLabel(self, text='Ready · No operation running', text_color=MUTED, anchor='w', font=self._font(11))
        self.operation_label.grid(row=2, column=1, sticky='ew', padx=22, pady=(2, 10))
        self.protocol('WM_DELETE_WINDOW', self._on_close)
        for index, name in enumerate(self.frames, 1):
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

    def _font(self, size=13, bold=False):
        key = size, bold
        if key not in self._fonts:
            self._fonts[key] = ctk.CTkFont(family='Segoe UI', size=size, weight='bold' if bold else 'normal')
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
            if self.workers.busy() or self._update_downloading or self._update_installing:
                button.configure(state='disabled')
        return button

    def _header(self, parent, title, detail, compact=False):
        parent.grid_columnconfigure(0, weight=1)
        frame = ctk.CTkFrame(parent, fg_color='transparent')
        frame.grid(row=0, column=0, sticky='ew', padx=22, pady=(10, 8) if compact else (15, 10))
        ctk.CTkLabel(frame, text=title, font=self._font(21 if compact else 23, True), anchor='w').pack(fill='x')
        label = ctk.CTkLabel(frame, text=detail, height=22 if compact else 28, font=self._font(11 if compact else 12), text_color=MUTED, anchor='w', wraplength=650, justify='left')
        label.pack(fill='x', pady=(1, 0))
        frame.bind('<Configure>', lambda event: label.configure(wraplength=max(250, event.width - 10)))

    def _card(self, parent):
        return ctk.CTkFrame(parent, fg_color=SURFACE, border_width=1, border_color=BORDER, corner_radius=8)

    def _load_icons(self):
        """Load the original chalice logo and a consistent, vector-like icon system."""
        self.icons, self.icons_active, self.action_icons = {}, {}, {}
        for name in ('dashboard', 'clean', 'disk', 'tools', 'apps', 'turbo', 'resurrect'):
            idle = make_icon(name, '#a5b5cd', 96)
            active = make_icon(name, COL_GOLD, 96)
            self.icons[name] = ctk.CTkImage(light_image=idle, dark_image=idle, size=(20, 20))
            self.icons_active[name] = ctk.CTkImage(light_image=active, dark_image=active, size=(20, 20))
        for name in ('cpu', 'memory', 'drive', 'scan', 'restore', 'updates'):
            color = COL_GOLD if name in ('drive', 'restore') else COL_BLUE
            icon = make_icon(name, color, 96)
            self.action_icons[name] = ctk.CTkImage(light_image=icon, dark_image=icon, size=(22, 22))
        with Image.open(resource_path('assets/panacea_icon.png')) as source:
            original = source.convert('RGBA').copy()
        self.brand_icon = ctk.CTkImage(light_image=original, dark_image=original, size=(51, 51))

    def _setup_sidebar(self):
        self.sidebar_frame = ctk.CTkFrame(self, width=190, corner_radius=0, fg_color='#0e192b')
        self.sidebar_frame.grid(row=0, column=0, rowspan=3, sticky='nsew')
        self.sidebar_frame.grid_propagate(False)
        self.sidebar_frame.grid_rowconfigure(9, weight=1)
        brand = ctk.CTkFrame(self.sidebar_frame, fg_color='transparent')
        brand.grid(row=0, column=0, rowspan=2, padx=11, pady=(18, 20), sticky='ew')
        ctk.CTkLabel(brand, image=self.brand_icon, text='', width=51, height=51).grid(row=0, column=0, rowspan=2, padx=(0, 8))
        ctk.CTkLabel(brand, text='Panacea', font=self._font(21, True), text_color=TEXT, anchor='w').grid(row=0, column=1, sticky='sw', pady=(3, 0))
        ctk.CTkLabel(brand, text='SYSTEM MAINTENANCE', font=self._font(8), text_color=COL_GOLD, anchor='w').grid(row=1, column=1, sticky='nw', pady=(0, 2))
        self.nav_buttons = {}
        names = [('Dashboard', 'dashboard', 'Dashboard'), ('Cleaning', 'clean', 'Cleanup'),
                 ('Disk', 'disk', 'Disk'), ('Tools', 'tools', 'Tools'),
                 ('Apps', 'apps', 'Apps'), ('Turbo', 'turbo', 'Turbo'),
                 ('Resurrect', 'resurrect', 'Resurrection')]
        for row, (name, icon, label) in enumerate(names, 2):
            button = self._button(self.sidebar_frame, label, lambda n=name: self.select_frame(n),
                                  secondary=True, width=163, height=38, anchor='w',
                                  image=self.icons[icon], compound='left')
            button.grid(row=row, column=0, padx=10, pady=3, sticky='ew')
            self.nav_buttons[name] = button
        ctk.CTkFrame(self.sidebar_frame, fg_color=BORDER, height=1).grid(row=10, column=0, sticky='ew', padx=17, pady=(10, 6))
        ctk.CTkLabel(self.sidebar_frame, text=f'v{VERSION}', text_color=MUTED,
                     font=self._font(11), anchor='w').grid(row=11, column=0, sticky='w', padx=17)
        footer = ctk.CTkLabel(self.sidebar_frame, text=f'© {datetime.now().year} M. Falconi',
                              text_color=MUTED, font=self._font(10), cursor='hand2')
        footer.grid(row=12, column=0, sticky='w', padx=17, pady=(0, 13))
        footer.bind('<Button-1>', lambda event: webbrowser.open('https://falker47.github.io/'))

    def select_frame(self, name):
        if name not in self.frames:
            return
        if name not in self._built_frames:
            self._setup_functions[name]()
            self._built_frames.add(name)
        for frame in self.frames.values():
            frame.grid_forget()
        self.frames[name].grid(row=1, column=1, sticky='nsew')
        self.active_frame = name
        for key, button in self.nav_buttons.items():
            selected = key == name
            icon_key = {'Cleaning': 'clean', 'Resurrect': 'resurrect'}.get(key, key.lower())
            icon_set = getattr(self, 'icons_active' if selected else 'icons', None)
            kwargs = {'fg_color': '#263a56' if selected else 'transparent',
                      'border_color': COL_GOLD if selected else '#0e192b',
                      'text_color': TEXT if selected else MUTED}
            if icon_set and icon_key in icon_set:
                kwargs['image'] = icon_set[icon_key]
            button.configure(**kwargs)

    def _setup_update_bar(self):
        bar = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=0, height=42)
        bar.grid(row=0, column=1, sticky='ew')
        bar.grid_columnconfigure(0, weight=1)
        self.app_update_status = ctk.CTkLabel(bar, text='Checking Panacea updates…', anchor='w', text_color=MUTED, font=self._font(11), wraplength=350)
        self.app_update_status.grid(row=0, column=0, sticky='ew', padx=18, pady=7)
        self.btn_check_update = self._button(bar, 'Check updates', self._check_app_update, secondary=True, width=105)
        self.btn_check_update.grid(row=0, column=1, padx=(4, 12), pady=6)
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
        ctk.CTkLabel(frame, text='Dashboard', font=self._font(22, True), anchor='w').grid(
            row=0, column=0, sticky='w', padx=18, pady=(8, 7))

        # A compact system summary, with a separate truthful Windows Update status.
        info = self._card(frame)
        info.grid(row=1, column=0, padx=18, pady=(0, 7), sticky='ew')
        info.grid_columnconfigure((0, 1), weight=1, uniform='overview')
        system = ctk.CTkFrame(info, fg_color='transparent')
        system.grid(row=0, column=0, sticky='nsew', padx=(14, 7), pady=8)
        self.dash_os = ctk.CTkLabel(system, text='Loading Windows details…', anchor='w',
                                    font=self._font(15, True), text_color=TEXT)
        self.dash_os.pack(anchor='w')
        system_details = ctk.CTkFrame(system, fg_color='transparent')
        system_details.pack(fill='x', pady=(3, 0))
        self.dash_uptime_val = ctk.CTkLabel(system_details, text='Uptime: —', anchor='w',
                                            font=self._font(11), text_color=MUTED)
        self.dash_uptime_val.pack(side='left')
        self.dash_battery = ctk.CTkLabel(system_details, text='Power: —', anchor='w',
                                         font=self._font(10), text_color=MUTED)
        self.dash_battery.pack(side='left', padx=(10, 0))
        updates = ctk.CTkFrame(info, fg_color=SURFACE_ALT, corner_radius=8)
        updates.grid(row=0, column=1, sticky='nsew', padx=(7, 10), pady=7)
        updates.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(updates, text='', image=self.action_icons['updates'], width=28).grid(
            row=0, column=0, rowspan=2, padx=(10, 3))
        ctk.CTkLabel(updates, text='Windows Update', text_color=TEXT, font=self._font(12, True),
                     anchor='w').grid(row=0, column=1, sticky='sw', pady=(7, 0))
        self.lbl_update_status = ctk.CTkLabel(updates, text='Checking…', font=self._font(10),
                                              text_color=MUTED, anchor='w', wraplength=210)
        self.lbl_update_status.grid(row=1, column=1, sticky='nw', pady=(0, 7))
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
            (self.card_ram, 'Memory', 'memory'),
            (self.card_disk, 'System drive · C:', 'drive'),
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
        self.dash_ram_val = ctk.CTkLabel(self.card_ram, text='Memory: —', text_color=MUTED,
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
        ctk.CTkLabel(scan, text='Temporary files', font=self._font(12, True),
                     anchor='w').grid(row=0, column=1, sticky='sw', pady=(7, 0))
        self.dash_preview_status = ctk.CTkLabel(
            scan, text=self._preview_summary, text_color=MUTED, font=self._font(10),
            anchor='w', wraplength=226, justify='left')
        self.dash_preview_status.grid(row=1, column=1, sticky='nw', pady=(0, 9))
        self._button(scan, 'Preview', self.run_preview_temp, secondary=True,
                     maintenance=True, width=77).grid(
            row=0, column=2, rowspan=2, padx=(3, 9), pady=8)

        restore = ctk.CTkFrame(self.card_sys, fg_color=SURFACE_ALT,
                               border_color=BORDER, border_width=1, corner_radius=9)
        restore.grid(row=0, column=1, sticky='nsew', padx=(5, 0), pady=0)
        restore.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(restore, image=self.action_icons['restore'], text='', width=27).grid(
            row=0, column=0, rowspan=2, padx=(9, 5))
        ctk.CTkLabel(restore, text='Restore point', font=self._font(12, True),
                     anchor='w').grid(row=0, column=1, sticky='sw', pady=(7, 0))
        ctk.CTkLabel(restore, text='Save Windows state · confirmation required',
                     text_color=MUTED, font=self._font(10), anchor='w', wraplength=210,
                     justify='left').grid(row=1, column=1, sticky='nw', pady=(0, 9))
        self._button(restore, 'Create', self.run_create_restore, secondary=True,
                     maintenance=True, width=77).grid(
            row=0, column=2, rowspan=2, padx=(3, 9), pady=8)

        for card, labels in (
            (self.card_cpu, (self.dash_cpu_name,)),
            (self.card_ram, (self.dash_ram_val, self.dash_ram_info)),
            (self.card_disk, (self.dash_disk_val, self.dash_disk_info)),
        ):
            card.bind('<Configure>', lambda event, items=labels: [
                label.configure(wraplength=max(110, event.width / label._get_widget_scaling() - 24))
                for label in items
            ])

    def _setup_cleaning_frame(self):
        frame = self.frame_cleaning
        self._header(frame, 'Cleanup', 'Preview temporary files before permanently deleting them. Locked or protected files are skipped.')
        frame.grid_rowconfigure(3, weight=1)
        card = self._card(frame)
        card.grid(row=1, column=0, sticky='ew', padx=22, pady=(0, 12))
        card.grid_columnconfigure((0, 1), weight=1)
        self.preview_label = ctk.CTkLabel(card, text=self._preview_summary, anchor='w', text_color=MUTED, font=self._font(12))
        self.preview_label.grid(row=0, column=0, sticky='ew', padx=14, pady=12)
        self._button(card, 'Preview temporary files', self.run_preview_temp, secondary=True, maintenance=True).grid(row=0, column=1, sticky='ew', padx=14, pady=12)
        self.btn_clean_temp = self._button(card, 'Delete temporary files', self.run_clean_temp, maintenance=True)
        self.btn_clean_temp.grid(row=1, column=0, sticky='ew', padx=14, pady=(0, 10))
        self.btn_empty_bin = self._button(card, 'Empty Recycle Bin', self.run_empty_recycle, secondary=True, maintenance=True)
        self.btn_empty_bin.grid(row=1, column=1, sticky='ew', padx=14, pady=(0, 10))
        self._button(card, 'Windows Disk Cleanup', self.run_cleanmgr, secondary=True).grid(row=2, column=0, sticky='ew', padx=14, pady=(0, 12))
        self._button(card, 'Clean component store', self.run_deep_clean, secondary=True, maintenance=True).grid(row=2, column=1, sticky='ew', padx=14, pady=(0, 12))
        ctk.CTkLabel(frame, text='Cleanup log', anchor='w', font=self._font(12, True)).grid(row=2, column=0, sticky='w', padx=22)
        self.clean_log = self._create_log_textbox(frame)
        self.clean_log.grid(row=3, column=0, sticky='nsew', padx=22, pady=(5, 12))
        self._flush_section_log('clean_log')

    def _setup_disk_frame(self):
        frame = self.frame_disk
        self._header(frame, 'Disk', 'Windows chooses defragmentation or TRIM for the selected drive. Review the result in the log.')
        frame.grid_rowconfigure(3, weight=1)
        card = self._card(frame)
        card.grid(row=1, column=0, sticky='ew', padx=22, pady=(0, 12))
        ctk.CTkLabel(card, text='Drive', font=self._font(12)).pack(side='left', padx=14, pady=14)
        self.selected_drive = tk.StringVar(value='Loading…')
        self.drive_menu = ctk.CTkOptionMenu(card, variable=self.selected_drive, values=['Loading…'], width=90, fg_color=SURFACE_ALT, button_color='#2e639f', font=self._font(12))
        self.drive_menu.pack(side='left', padx=(0, 8), pady=14)
        self._button(card, 'Refresh', self.refresh_drives, secondary=True, width=80).pack(side='left', pady=14)
        self._button(card, 'Optimize drive', self.run_optimize_drive, maintenance=True, width=120).pack(side='right', padx=14, pady=14)
        self._button(frame, 'Open Windows drive optimization', self.run_dfrgui, secondary=True).grid(row=2, column=0, sticky='w', padx=22, pady=(0, 10))
        self.disk_log = self._create_log_textbox(frame)
        self.disk_log.grid(row=3, column=0, sticky='nsew', padx=22, pady=(0, 12))
        self._set_drives([{'letter': value} for value in self._drive_values])
        self._flush_section_log('disk_log')

    def _setup_tools_frame(self):
        frame = self.frame_tools
        self._header(frame, 'Tools', 'Run a specific repair or diagnostic. Each operation asks for confirmation and records its result.')
        frame.grid_rowconfigure(1, weight=3)
        frame.grid_rowconfigure(3, weight=2)
        container = ctk.CTkScrollableFrame(frame, fg_color=BG)
        container.grid(row=1, column=0, sticky='nsew', padx=16, pady=(0, 8))
        groups = [('System integrity', [('System file scan', 'Checks protected Windows files.', 'sfc /scannow', 'SFC scan'), ('Image health check', 'Checks the Windows component image.', 'DISM /Online /Cleanup-Image /CheckHealth', 'DISM health check'), ('Repair Windows image', 'Repairs the Windows image; may use Windows Update.', 'DISM /Online /Cleanup-Image /RestoreHealth', 'DISM repair')]), ('Network', [('Flush DNS cache', 'Clears cached DNS records.', 'ipconfig /flushdns', 'DNS flush'), ('Reset Winsock', 'Resets network configuration. A restart may be needed.', 'netsh winsock reset', 'Network reset')])]
        for title, entries in groups:
            card = self._card(container)
            card.pack(fill='x', pady=(0, 8))
            ctk.CTkLabel(card, text=title, font=self._font(13, True)).pack(anchor='w', padx=14, pady=(10, 4))
            for text, detail, command, name in entries:
                self._add_tool_btn(card, text, detail, command, name)
        row = ctk.CTkFrame(container, fg_color='transparent')
        row.pack(fill='x')
        self._button(row, 'Create restore point', self.run_create_restore, secondary=True, maintenance=True).pack(side='left', padx=(0, 8), pady=4)
        self._button(row, 'Battery report', self.run_battery_report, secondary=True, maintenance=True).pack(side='left', pady=4)
        ctk.CTkLabel(frame, text='Execution log', font=self._font(12, True), anchor='w').grid(row=2, column=0, sticky='w', padx=22)
        self.tools_log = self._create_log_textbox(frame, height=120)
        self.tools_log.grid(row=3, column=0, sticky='nsew', padx=22, pady=(5, 12))
        self._flush_section_log('tools_log')

    def _add_tool_btn(self, parent, text, desc, cmd, name):
        row = ctk.CTkFrame(parent, fg_color='transparent')
        row.pack(fill='x', padx=14, pady=(0, 8))
        row.grid_columnconfigure(0, weight=1)
        label = ctk.CTkLabel(row, text=desc, text_color=MUTED, font=self._font(11), anchor='w', justify='left', wraplength=390)
        label.grid(row=0, column=0, sticky='ew', padx=(0, 10))
        self._button(row, text, lambda: self.run_cmd(cmd, name), maintenance=True, width=155).grid(row=0, column=1)
        row.bind('<Configure>', lambda event: label.configure(wraplength=max(130, event.width - 175)))

    def _setup_apps_frame(self):
        frame = self.frame_apps
        self._header(frame, 'Apps', 'Review installed software and startup entries using Windows settings.')
        body = ctk.CTkScrollableFrame(frame, fg_color=BG)
        body.grid(row=1, column=0, sticky='nsew', padx=16, pady=(0, 12))
        frame.grid_rowconfigure(1, weight=1)
        for title, desc, actions in [('Installed apps', 'Review and uninstall applications you no longer need.', [('Open Apps settings', 'ms-settings:appsfeatures'), ('Classic Programs and Features', 'appwiz.cpl')]), ('Startup apps', 'Review which applications start when you sign in.', [('Open Startup settings', 'ms-settings:startupapps')])]:
            card = self._card(body)
            card.pack(fill='x', pady=(0, 12))
            ctk.CTkLabel(card, text=title, font=self._font(16, True)).pack(anchor='w', padx=16, pady=(14, 2))
            ctk.CTkLabel(card, text=desc, font=self._font(12), text_color=MUTED).pack(anchor='w', padx=16, pady=(0, 12))
            for text, uri in actions:
                self._button(card, text, lambda u=uri, t=text: self.run_launch(u, t), secondary=True).pack(fill='x', padx=16, pady=(0, 12))

    def _setup_turbo_frame(self):
        frame = self.frame_turbo
        self._header(frame, 'Turbo', 'Temporary performance settings. Turning a setting off restores its saved original state.')
        frame.grid_rowconfigure(1, weight=1)
        container = ctk.CTkScrollableFrame(frame, fg_color=BG)
        container.grid(row=1, column=0, sticky='nsew', padx=16, pady=(0, 12))
        self.turbo_vars, self.turbo_switches = {}, {}
        master = self._card(container)
        master.pack(fill='x', pady=(0, 10))
        ctk.CTkLabel(master, text='All Turbo settings', font=self._font(14, True)).pack(side='left', padx=14, pady=14)
        self.master_switch = ctk.CTkSwitch(master, text='Loading…', state='disabled', command=self._master_toggle_changed, font=self._font(12), progress_color=COL_BLUE)
        self.master_switch.pack(side='right', padx=14, pady=14)
        config = [('power', 'High performance power plan', 'Can increase power use, heat and battery drain.', lambda: self.perf_mgr.set_power_plan(True), lambda: self.perf_mgr.set_power_plan(False)), ('visual', 'Reduce visual effects', 'Reduce Windows animation and appearance effects.', lambda: self.perf_mgr.set_visual_effects(False), lambda: self.perf_mgr.set_visual_effects(True)), ('sysmain', 'Pause SysMain', 'Pause application preloading.', lambda: self.perf_mgr.set_sysmain(False), lambda: self.perf_mgr.set_sysmain(True)), ('wsearch', 'Pause Windows Search', 'Pause background search indexing.', lambda: self.perf_mgr.set_wsearch(False), lambda: self.perf_mgr.set_wsearch(True)), ('spooler', 'Pause Print Spooler', 'Printing is unavailable while this setting is active.', lambda: self.perf_mgr.set_spooler(False), lambda: self.perf_mgr.set_spooler(True))]
        for key, title, desc, on_fn, off_fn in config:
            card = self._card(container)
            card.pack(fill='x', pady=4)
            card.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(card, text=title, font=self._font(13, True), anchor='w').grid(row=0, column=0, sticky='ew', padx=14, pady=(10, 0))
            detail = ctk.CTkLabel(card, text=desc, text_color=MUTED, font=self._font(11), anchor='w', wraplength=430, justify='left')
            detail.grid(row=1, column=0, sticky='ew', padx=14, pady=(0, 10))
            var = tk.BooleanVar(value=False)
            switch = ctk.CTkSwitch(card, text='Unknown', variable=var, state='disabled', font=self._font(11), width=110, progress_color=COL_BLUE, command=lambda k=key, on=on_fn, off=off_fn: self._turbo_toggle_changed(k, on, off))
            switch.grid(row=0, column=1, rowspan=2, padx=14)
            self.turbo_vars[key], self.turbo_switches[key] = var, switch
            card.bind('<Configure>', lambda event, label=detail: label.configure(wraplength=max(150, event.width - 170)))
        self._button(container, 'Refresh actual state', self._load_turbo_states, secondary=True).pack(anchor='w', pady=10)
        if self._turbo_states:
            self._apply_turbo_states((self._turbo_states, self._turbo_master))

    def _setup_resurrect_frame(self):
        frame = self.frame_resurrect
        self._header(frame, 'Resurrection', 'A guided maintenance sequence with a verified restore point and a result for every completed step.')
        frame.grid_rowconfigure(2, weight=1)
        card = self._card(frame)
        card.grid(row=1, column=0, sticky='ew', padx=22, pady=(0, 12))
        warning = ctk.CTkLabel(card, text='Permanently deletes browser caches, temporary files and the Recycle Bin; resets network settings.\nSave your work first. Cancellation takes effect between commands.', text_color=MUTED, font=self._font(12), anchor='w', justify='left', wraplength=650)
        warning.pack(fill='x', padx=14, pady=(12, 8))
        card.bind('<Configure>', lambda event: warning.configure(wraplength=max(300, event.width - 28)))
        self.progress_bar = ctk.CTkProgressBar(card, height=9, progress_color=COL_BLUE, fg_color=BORDER)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill='x', padx=14, pady=(0, 6))
        self.lbl_status = ctk.CTkLabel(card, text='Ready · 10 steps', font=self._font(12, True), anchor='w', wraplength=650, justify='left')
        self.lbl_status.pack(fill='x', padx=14)
        row = ctk.CTkFrame(card, fg_color='transparent')
        row.pack(fill='x', padx=14, pady=12)
        self.btn_resurrect_start = self._button(row, 'Start maintenance sequence', self.run_god_mode, maintenance=True)
        self.btn_resurrect_start.pack(side='left')
        self.btn_resurrect_cancel = self._button(row, 'Cancel after current step', self._cancel_resurrect, secondary=True)
        self.god_log = self._create_log_textbox(frame)
        self.god_log.grid(row=2, column=0, sticky='nsew', padx=22, pady=(0, 12))
        self._flush_section_log('god_log')

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
        self.after(30, self._drain_callbacks)

    def _set_maintenance_state(self, busy):
        for button in self._maintenance_controls:
            button.configure(state='disabled' if busy else 'normal')
        for key, switch in self.__dict__.get('turbo_switches', {}).items():
            switch.configure(state='disabled' if busy or self._turbo_states.get(key) is None else 'normal')
        if 'master_switch' in self.__dict__:
            self.master_switch.configure(state='disabled' if busy or self._turbo_master is None else 'normal')

    def _request_operation(self, name, work, on_success=None, on_done=None):
        if self._update_installing or self._update_downloading or self.workers.busy():
            self._show_toast('Operation in progress', 'Wait for the current operation to finish.', 'warning')
            return False
        def done():
            self._set_maintenance_state(False)
            if on_done:
                on_done()
        def error(exc):
            self.operation_label.configure(text=f'Failed · {name}: {exc}', text_color=COL_RED)
            self._show_toast(f'{name} failed', str(exc), 'error')
            if name == 'Temporary file preview':
                self._set_preview_status('Scan failed · see status below', COL_RED)
        started = self.workers.start(name, work, on_success=on_success, on_error=error, on_done=done)
        if started:
            self._set_maintenance_state(True)
            self.operation_label.configure(text=f'Running · {name}', text_color=MUTED)
        return started

    def _show_result(self, name, result):
        success, message = result
        self.operation_label.configure(text=f'{"Completed" if success else "Failed / partial"} · {name}: {message}', text_color=COL_SUCCESS if success else COL_WARNING)
        self._show_toast(name, message, 'success' if success else 'warning')

    def update_dashboard(self):
        if self._shutdown.is_set():
            return
        self.workers.start('metrics', self.monitor.sample_fast, group='metrics', on_success=self._update_fast_gui, on_error=lambda exc: self.operation_label.configure(text=f'Metrics unavailable: {exc}'), on_done=lambda: self.after(3000, self.update_dashboard))

    def _load_metadata(self):
        if self._shutdown.is_set():
            return
        self.workers.start('hardware', self.monitor.sample_metadata, group='hardware', on_success=self._update_metadata_gui, on_done=lambda: self.after(120000, self._load_metadata))

    def _update_fast_gui(self, sample):
        total_ram, available_ram, ram_percent = sample['ram']
        total_disk, free_disk, disk_percent = sample['disk']
        self.dash_uptime_val.configure(text=f"Uptime: {sample['uptime']}")
        self.dash_cpu_val.configure(text=f"{sample['cpu']:.1f}%")
        self.cpu_graph.add_value(sample['cpu'])
        self.ram_graph.add_value(ram_percent)
        self.dash_ram_val.configure(text=f'{total_ram - available_ram:.1f} GB used / {total_ram:.1f} GB')
        self.dash_ram_perc.configure(text=f'{ram_percent:.1f}%', text_color=COL_WARNING if ram_percent >= 90 else TEXT)
        self.dash_disk_bar.set(max(0, min(1, disk_percent / 100)))
        disk_color = COL_RED if disk_percent >= 95 else COL_WARNING if disk_percent >= 85 else COL_GOLD
        self.dash_disk_bar.configure(progress_color=disk_color)
        self.dash_disk_state.configure(text='Low free space' if disk_percent >= 90 else 'Storage healthy',
                                       text_color=disk_color if disk_percent >= 85 else MUTED)
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
        self.lbl_update_status.configure(text=str(status), text_color=COL_SUCCESS if mandatory == optional == 0 else COL_WARNING if mandatory > 0 else MUTED)

    def refresh_drives(self):
        self.workers.start('drive-list', self.disk_opt.get_drive_info, group='drive-list', on_success=self._set_drives, on_error=lambda exc: self.log_disk_msg(f'Drive query failed: {exc}'))

    def _set_drives(self, drives):
        values = [str(drive['letter']) for drive in drives]
        self._drive_values = values
        if 'drive_menu' not in self.__dict__:
            return
        self.drive_menu.configure(values=values or ['No drives'])
        if self.selected_drive.get() not in values:
            self.selected_drive.set(values[0] if values else 'No drives')

    def _set_preview_status(self, message, color=MUTED):
        """Keep the same preview result visible from Dashboard and Cleanup."""
        self._preview_summary = str(message)
        for name in ('dash_preview_status', 'preview_label'):
            widget = self.__dict__.get(name)
            if widget is not None:
                settings = {'text': self._preview_summary}
                if name == 'dash_preview_status':
                    settings['text_color'] = color
                widget.configure(**settings)

    def run_preview_temp(self):
        previous = getattr(self, '_preview_summary', 'Not scanned yet')
        self._set_preview_status('Scanning temporary files… No files changed', COL_GOLD)
        def show(result):
            count, size = result
            details = self.cleanup_mgr.last_result
            errors, skipped = getattr(details, 'errors', []), getattr(details, 'skipped', [])
            partial = bool(errors or skipped)
            summary = f'{count:,} files · {size / 1048576:.1f} MB eligible'
            if partial:
                summary += f' · {len(skipped)} skipped · {len(errors)} errors'
            self._set_preview_status(summary, COL_WARNING if partial else COL_SUCCESS)
            self.operation_label.configure(
                text=f'{"Partial" if partial else "Completed"} · Temporary file preview',
                text_color=COL_WARNING if partial else COL_SUCCESS)
            for error in errors[:10]:
                self.log_msg(str(error))
        started = self._request_operation(
            'Temporary file preview', self.cleanup_mgr.preview_temp_files, show)
        if started is False:
            self._set_preview_status(previous)

    def _cleanup_result(self, fn, *args, **kwargs):
        count, freed = fn(*args, **kwargs)
        result = self.cleanup_mgr.last_result
        errors, skipped = getattr(result, 'errors', []), getattr(result, 'skipped', [])
        details = f'{count:,} files deleted · {freed / 1048576:.1f} MB freed'
        if skipped or errors:
            details += f' · {len(skipped)} skipped · {len(errors)} errors'
        for error in errors[:10]:
            self.log_msg(str(error))
        return not errors and not skipped, details

    def run_clean_temp(self):
        if not messagebox.askyesno('Delete temporary files', 'Permanently delete eligible files in validated temporary folders?\nLocked and protected files will be skipped. Use Preview first to inspect the size.', parent=self):
            return
        self._request_operation('Temporary file cleanup', lambda: self._cleanup_result(self.cleanup_mgr.clean_temp_files, progress_callback=self.log_msg), lambda result: self._show_result('Temporary file cleanup', result))

    def run_empty_recycle(self):
        if not messagebox.askyesno('Empty Recycle Bin', 'Permanently delete every item in the Recycle Bin?\nThese items cannot be recovered through the Recycle Bin.', parent=self):
            return
        self._request_operation('Empty Recycle Bin', self.cleanup_mgr.empty_recycle_bin, lambda result: self._show_result('Recycle Bin', result))

    def run_cleanmgr(self):
        try:
            self.cleanup_mgr.open_disk_cleanup()
        except Exception as exc:
            self._show_toast('Disk Cleanup', str(exc), 'error')

    def run_deep_clean(self):
        self.run_cmd('DISM /Online /Cleanup-Image /StartComponentCleanup', 'Component store cleanup')

    def run_optimize_drive(self):
        letter = self.selected_drive.get()
        import re
        if not re.fullmatch(r'[A-Za-z]:?', letter):
            self._show_toast('Select a drive', 'Choose a valid drive letter.', 'warning')
            return
        if messagebox.askyesno('Optimize drive', f'Run Windows optimization on {letter}?\nThis operation can take several minutes.', parent=self):
            self._request_operation('Drive optimization', lambda: self.disk_opt.analyze_optimize_drive(letter, progress_callback=self.log_disk_msg), lambda success: self._show_result('Drive optimization', (success is True, 'See the disk log for details.')))

    def run_dfrgui(self):
        try:
            self.disk_opt.open_optimize_gui()
        except Exception as exc:
            self._show_toast('Drive optimization', str(exc), 'error')

    def run_cmd(self, cmd, desc):
        detail = 'Network connections may be interrupted and a restart may be needed.' if 'winsock' in cmd.lower() else 'The operation can take several minutes. Save your work first.'
        if not messagebox.askyesno(desc, f'Run {desc}?\n{detail}', parent=self):
            return
        def work():
            self.log_tools_msg(f'> {desc}')
            success = self.cmd_runner.run_command_stream(cmd, desc, self.log_tools_msg)
            self.log_tools_msg(f'{desc}: {"completed" if success is True else "failed"}')
            return success is True, 'See the execution log for details.'
        self._request_operation(desc, work, lambda result: self._show_result(desc, result))

    def run_launch(self, target, desc):
        try:
            if target in ('ms-settings:appsfeatures', 'ms-settings:startupapps', 'ms-settings:windowsupdate', 'ms-settings:windowsupdate-optionalupdates'):
                os.startfile(target)
            elif target == 'appwiz.cpl':
                from modules.commands import system_executable
                subprocess.Popen([system_executable('control.exe'), 'appwiz.cpl'], shell=False)
            else:
                raise ValueError('Unsupported Windows settings destination')
        except Exception as exc:
            self._show_toast(desc, str(exc), 'error')

    def run_battery_report(self):
        path = Path(os.environ.get('USERPROFILE', str(Path.home()))) / 'battery_report.html'
        def report():
            from modules.commands import system_executable
            subprocess.run([system_executable('powercfg.exe'), '/batteryreport', '/output', str(path)], shell=False, check=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), capture_output=True, timeout=60)
            return path
        self._request_operation('Battery report', report, lambda result: (os.startfile(str(result)), self.operation_label.configure(text=f'Completed · Battery report saved to {result}', text_color=COL_SUCCESS)))

    def run_create_restore(self):
        if messagebox.askyesno('Create restore point', 'Create and verify a new Windows restore point?\nSystem protection must already be enabled. This may take a minute.', parent=self):
            self._request_operation('Restore point', lambda: self.restore_mgr.create_restore_point('Panacea Manual Point'), lambda result: self._show_result('Restore point', result))

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
        self.workers.start('turbo-state', self._read_turbo_states, group='turbo-state', on_success=self._apply_turbo_states)

    def _apply_turbo_states(self, result):
        states, master = result
        self._turbo_states, self._turbo_master = states, master
        if 'turbo_switches' not in self.__dict__:
            return
        busy = self.workers.busy() or self._update_downloading or self._update_installing
        for key, state in states.items():
            if state is not None:
                self.turbo_vars[key].set(state)
            self.turbo_switches[key].configure(text='Unknown' if state is None else 'Active' if state else 'Inactive', state='disabled' if busy or state is None else 'normal')
        if master is not None:
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

    def _run_resurrection_sequence(self):
        from modules.operations import OperationStep, run_sequence
        log = self.log_god_msg
        def cleanup(fn, **kwargs):
            count, size = fn(**kwargs)
            detail = self.cleanup_mgr.last_result
            errors, skipped = getattr(detail, 'errors', []), getattr(detail, 'skipped', [])
            return not errors and not skipped, f'{count} files · {size / 1048576:.1f} MB freed · {len(skipped)} skipped · {len(errors)} errors'
        def command(cmd, name):
            return self.cmd_runner.run_command_stream(cmd, name, lambda msg: log(msg)) is True, 'See command output above.'
        steps = [OperationStep('Restore point', lambda: self.restore_mgr.create_restore_point('Panacea Resurrection restore point'), True),
                 OperationStep('Browser caches', lambda: cleanup(self.cleanup_mgr.clean_browser_caches)),
                 OperationStep('Temporary files', lambda: cleanup(self.cleanup_mgr.clean_temp_files, progress_callback=log)),
                 OperationStep('Recycle Bin', self.cleanup_mgr.empty_recycle_bin),
                 OperationStep('DNS cache', lambda: command('ipconfig /flushdns', 'DNS flush')),
                 OperationStep('Network reset', lambda: command('netsh winsock reset', 'Network reset')),
                 OperationStep('Drive optimization', lambda: (self.disk_opt.analyze_optimize_drive('C:', progress_callback=log) is True, 'See drive output above.')),
                 OperationStep('Disk health scan', lambda: command('chkdsk C: /scan /perf', 'Disk health scan')),
                 OperationStep('Windows image health', lambda: command('DISM /Online /Cleanup-Image /CheckHealth', 'Image health')),
                 OperationStep('System file scan', lambda: command('sfc /scannow', 'System file scan'))]
        def progress(completed, total, result):
            log(f'{"Completed" if result.success else "Failed / partial"}: {result.name} · {result.message}', 'info' if result.success else 'err')
            self.dispatcher.post(self._resurrection_progress, completed / total, f'{completed}/{total} finished · {result.name}', critical=True)
        result = run_sequence(steps, cancel=lambda: self._shutdown.is_set() or self._resurrect_cancel.is_set(), progress=progress)
        if result.steps and not result.steps[0].success:
            log('Stopped before cleanup: a new restore point could not be verified. Enable System Protection in Windows and retry.', 'err')
        return {'status': result.status, 'steps': [{'name': row.name, 'success': row.success, 'message': row.message} for row in result.steps], 'total': len(steps)}

    def run_god_mode(self):
        if self._update_installing or self._update_downloading or self.workers.busy():
            self._show_toast('Operation in progress', 'Wait for the current operation to finish.', 'warning')
            return
        if not messagebox.askyesno('Confirm Resurrection', 'Run all 10 maintenance steps?\n\nAfter verifying a new restore point, Panacea permanently deletes browser caches, temporary files and ALL Recycle Bin items, then resets network settings and scans the system.\n\nDeletion cannot be undone through the Recycle Bin. Network connections may be interrupted; a restart may be needed. Save your work first.', parent=self):
            return
        self._resurrect_cancel.clear()
        def finished(result):
            self.last_resurrection_result = result
            text = f"{result['status'].capitalize()} · {len(result['steps'])}/{result['total']} steps finished"
            failures = [row['name'] for row in result['steps'] if not row['success']]
            if failures:
                text += ' · Failed: ' + ', '.join(failures)
            color = COL_SUCCESS if result['status'] == 'completed' else COL_WARNING if result['status'] in ('partial', 'cancelled') else COL_RED
            self.lbl_status.configure(text=text, text_color=color)
            self.operation_label.configure(text=text, text_color=color)
            self.log_god_msg(text, 'head')
        def done():
            self.btn_resurrect_cancel.pack_forget()
            self.btn_resurrect_start.configure(text='Start maintenance sequence')
        if self._request_operation('Resurrection', self._run_resurrection_sequence, finished, done):
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
                self.update_actions.grid(row=1, column=0, columnspan=2, sticky='w', padx=18)
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
        if self.workers.busy() and not messagebox.askyesno('Maintenance in progress', 'Close Panacea?\nResurrection will stop before its next step. A running command may finish in the background.', parent=self):
            return
        self._shutdown.set()
        self._resurrect_cancel.set()
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
