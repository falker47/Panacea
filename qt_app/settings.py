"""Per-user Qt preferences and post-readiness update presentation."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import logging
import os
from pathlib import Path
from uuid import UUID

from packaging.version import InvalidVersion, Version
from PySide6.QtCore import (
    QAbstractNativeEventFilter, QCoreApplication, QIODevice, QLockFile, QObject, Property,
    QSaveFile, QTimer, Signal, Slot,
)

from modules.localization import resolve_language
from modules.updater import UpdateVerificationError, _assert_plain_path
from qt_app.i18n.release_notes import sanitize_notes
from version import VERSION


def _settings_file() -> Path:
    # FOLDERID_LocalAppData; the Shell allocates the Unicode path even when
    # the location is redirected. Never derive the elevated writer's path
    # from an editable environment variable.
    folder_id = UUID("f1b32785-6fba-4fcf-9d55-7b8e7f157091").bytes_le
    folder = ctypes.c_wchar_p()
    get_folder = ctypes.windll.shell32.SHGetKnownFolderPath
    get_folder.argtypes = [ctypes.c_void_p, wintypes.DWORD, wintypes.HANDLE,
                           ctypes.POINTER(ctypes.c_wchar_p)]
    get_folder.restype = ctypes.c_long
    free = ctypes.windll.ole32.CoTaskMemFree
    free.argtypes = [ctypes.c_void_p]
    free.restype = None
    try:
        if get_folder(folder_id, 0, None, ctypes.byref(folder)) != 0 or not folder.value:
            raise OSError("LocalAppData is unavailable")
        return Path(folder.value) / "Panacea" / "settings.json"
    finally:
        if folder:
            free(folder)


class _HighContrast(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwFlags", wintypes.DWORD),
                ("lpszDefaultScheme", ctypes.c_void_p)]


def _windows_appearance():
    user32 = ctypes.windll.user32
    info = _HighContrast()
    info.cbSize = ctypes.sizeof(info)
    animations = wintypes.BOOL(1)
    reduced = bool(user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(animations), 0)
                   and not animations.value)  # SPI_GETCLIENTAREAANIMATION
    if not (user32.SystemParametersInfoW(0x0042, info.cbSize, ctypes.byref(info), 0)
            and info.dwFlags & 1):  # SPI_GETHIGHCONTRAST, HCF_HIGHCONTRASTON
        return {}, reduced

    def color(index):
        value = user32.GetSysColor(index)  # COLORREF is 0x00BBGGRR.
        return f"#{value & 255:02x}{value >> 8 & 255:02x}{value >> 16 & 255:02x}"

    window, text = color(5), color(8)  # COLOR_WINDOW, COLOR_WINDOWTEXT
    selected, selected_text = color(13), color(14)  # COLOR_HIGHLIGHT, COLOR_HIGHLIGHTTEXT
    return {
        "bg": window, "surface": window, "surfaceAlt": window, "border": text,
        "text": text, "textMuted": text, "accent": selected, "onAccent": selected_text,
        "info": text, "success": text, "warning": text, "danger": text, "focus": text,
    }, reduced


class _AppearanceEvents(QAbstractNativeEventFilter):
    def __init__(self, refresh):
        super().__init__()
        self._refresh = refresh

    def nativeEventFilter(self, event_type, message):
        if bytes(event_type) in (b"windows_generic_MSG", b"windows_dispatcher_MSG") and message:
            # WM_SYSCOLORCHANGE, WM_SETTINGCHANGE, WM_THEMECHANGED.
            if wintypes.MSG.from_address(int(message)).message in (0x15, 0x1A, 0x031A):
                QTimer.singleShot(0, self._refresh)
        return False, 0


def _read(path):
    _assert_plain_path(path)
    try:
        with path.open("rb") as stream:
            payload = stream.read(256 * 1024 + 1)
    except FileNotFoundError:
        return {}
    try:
        data = json.loads(payload) if len(payload) <= 256 * 1024 else None
    except (ValueError, RecursionError):
        data = None
    return data if isinstance(data, dict) else {}


def _atomic_write(path, data):
    output = QSaveFile(str(path))
    output.setDirectWriteFallback(False)
    if not output.open(QIODevice.WriteOnly):
        raise OSError(output.errorString())
    payload = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if output.write(payload) != len(payload):
        output.cancelWriting()
        raise OSError(output.errorString())
    if not output.commit():
        raise OSError(output.errorString())


def _version(value):
    if not isinstance(value, str) or not 0 < len(value) <= 64:
        return None
    try:
        return Version(value)
    except InvalidVersion:
        return None


class AppSettings(QObject):
    languageChoiceChanged = Signal()
    autoCheckChanged = Signal()
    reduceMotionChanged = Signal()
    sidebarCollapsedChanged = Signal()
    systemAppearanceChanged = Signal()
    whatsNewChanged = Signal()
    saveFailed = Signal()

    def __init__(self, smoke=False, *, path=None, defer_load=False, parent=None):
        super().__init__(parent)
        self._memory = smoke or (path is None and os.name != "nt")
        self._path = Path(path) if path is not None and not smoke else None
        self._observe_windows = not smoke and os.name == "nt"
        self._deferred = defer_load
        self._data = {}
        self._colors = {}
        self._system_reduced = False
        self._filter = None
        self._whats_new = ("", "")
        if not self._deferred:
            self._load()

    def _load(self):
        if not self._memory:
            try:
                self._path = self._path or _settings_file()
                self._replace(_read(self._path))
            except (OSError, UpdateVerificationError):
                logging.getLogger(__name__).warning("Could not read Panacea preferences.")
        if self._observe_windows:
            self._refresh_appearance()
            app = QCoreApplication.instance()
            if app is not None and self._filter is None:
                self._filter = _AppearanceEvents(self._refresh_appearance)
                app.installNativeEventFilter(self._filter)

    def _refresh_appearance(self):
        colors, reduced = _windows_appearance()
        if (colors, reduced) != (self._colors, self._system_reduced):
            self._colors, self._system_reduced = colors, reduced
            self.systemAppearanceChanged.emit()

    def _replace(self, data):
        previous, self._data = self._data, data
        for key, signal in (("languageChoice", self.languageChoiceChanged), ("autoCheck", self.autoCheckChanged),
                            ("reduceMotion", self.reduceMotionChanged), ("sidebarCollapsed", self.sidebarCollapsedChanged)):
            if previous.get(key) != data.get(key):
                signal.emit()

    def _edit(self, change):
        """Merge under a short cross-process lock, then replace the file atomically.

        The old and new executable can coexist during verified startup. A
        preference changed in one must not erase a version marker in the other.
        """
        if self._memory:
            data = dict(self._data)
            change(data)
            self._replace(data)
            return True
        try:
            if self._path is None:
                raise OSError("Settings folder unavailable")
            _assert_plain_path(self._path)
            self._path.parent.mkdir(exist_ok=True)
            lock_path = self._path.with_suffix(".lock")
            _assert_plain_path(lock_path)
            lock = QLockFile(str(lock_path))
            if not lock.tryLock(250):
                raise OSError("Settings file in use")
            try:
                previous = _read(self._path)
                data = dict(previous)
                change(data)
                if data != previous:
                    _atomic_write(self._path, data)
            finally:
                lock.unlock()
            self._replace(data)
            return True
        except (OSError, UpdateVerificationError, UnicodeError, RecursionError):
            logging.getLogger(__name__).warning("Could not save Panacea preferences.")
            self.saveFailed.emit()
            return False

    def _set(self, key, value):
        if self._data.get(key) != value:
            self._edit(lambda data: data.update({key: value}))

    @Property(str, notify=languageChoiceChanged)
    def languageChoice(self):
        choice = self._data.get("languageChoice")
        return choice if choice in ("it", "en") else "system"

    @languageChoice.setter
    def languageChoice(self, value):
        if value in ("system", "it", "en"):
            self._set("languageChoice", value)

    def resolved_language(self):
        if self._deferred:
            # Protected startup shows its first frame before reading per-user
            # preferences or the installer's language file.
            return "en"
        return resolve_language(user_choice=self._data.get("languageChoice"))

    def _bool(self, key, default):
        value = self._data.get(key)
        return value if isinstance(value, bool) else default

    @Property(bool, notify=autoCheckChanged)
    def autoCheck(self):
        return self._bool("autoCheck", True)

    @autoCheck.setter
    def autoCheck(self, value):
        self._set("autoCheck", bool(value))

    @Property(bool, notify=reduceMotionChanged)
    def reduceMotion(self):
        return self._bool("reduceMotion", False)

    @reduceMotion.setter
    def reduceMotion(self, value):
        self._set("reduceMotion", bool(value))

    @Property(bool, notify=sidebarCollapsedChanged)
    def sidebarCollapsed(self):
        return self._bool("sidebarCollapsed", False)

    @sidebarCollapsed.setter
    def sidebarCollapsed(self, value):
        self._set("sidebarCollapsed", bool(value))

    @Property("QVariantMap", notify=systemAppearanceChanged)
    def systemColors(self):
        return self._colors.copy()

    @Property(bool, notify=systemAppearanceChanged)
    def systemReducedMotion(self):
        return self._system_reduced

    def cacheReleaseNotes(self, version, notes):
        if _version(version) is not None:
            self._edit(lambda data: data.update(releaseVersion=version, releaseNotes=sanitize_notes(notes)))

    def finishStartup(self, verified_update=False):
        """Call after QML load, and only after a required readiness ack succeeds."""
        if self._deferred:
            self._deferred = False
            self._load()
            self.languageChoiceChanged.emit()
        whats_new = ("", "")
        current = Version(VERSION)

        def record(data):
            nonlocal whats_new
            seen = _version(data.get("lastSeenVersion"))
            if seen is not None and seen >= current:
                return
            if seen is not None or verified_update:
                notes = ""
                if _version(data.get("releaseVersion")) == current:
                    notes = sanitize_notes(data.get("releaseNotes", ""))
                whats_new = (VERSION, notes)
            data["lastSeenVersion"] = VERSION
            cached = _version(data.get("releaseVersion"))
            if cached is not None and cached <= current:
                data.pop("releaseNotes", None)
                data.pop("releaseVersion", None)

        if self._edit(record) and whats_new[0]:
            self._whats_new = whats_new
            self.whatsNewChanged.emit()

    @Property(str, notify=whatsNewChanged)
    def whatsNewVersion(self):
        return self._whats_new[0]

    @Property(str, notify=whatsNewChanged)
    def whatsNewNotes(self):
        return self._whats_new[1]

    @Slot()
    def dismissWhatsNew(self):
        if self._whats_new[0]:
            self._whats_new = ("", "")
            self.whatsNewChanged.emit()
