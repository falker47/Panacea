"""Preference writes target fixtures only; update and OS events are simulated."""
import ctypes
from ctypes import wintypes
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID

import pytest

from qt_app.i18n import I18n
from qt_app import settings as preferences
from qt_app.settings import AppSettings

_read_appearance = preferences._windows_appearance


@pytest.fixture(autouse=True)
def mock_windows_appearance(monkeypatch):
    monkeypatch.setattr(preferences, "_windows_appearance", lambda: ({}, False))


def test_windows_path_uses_local_appdata_known_folder_and_frees_the_shell_buffer(tmp_path, monkeypatch):
    buffer = ctypes.create_unicode_buffer(str(tmp_path))

    def get_path(folder_id, flags, token, output):
        assert bytes(folder_id) == UUID("f1b32785-6fba-4fcf-9d55-7b8e7f157091").bytes_le
        assert flags == 0 and token is None
        ctypes.cast(output, ctypes.POINTER(ctypes.c_void_p))[0] = ctypes.addressof(buffer)
        return 0

    free = Mock()
    libraries = SimpleNamespace(shell32=SimpleNamespace(SHGetKnownFolderPath=Mock(side_effect=get_path)),
                                ole32=SimpleNamespace(CoTaskMemFree=free))
    monkeypatch.setattr(ctypes, "windll", libraries, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", "fixture environment path must not be used")
    assert preferences._settings_file() == tmp_path / "Panacea" / "settings.json"
    free.assert_called_once()


def test_windows_accessibility_maps_real_theme_tokens_from_the_mocked_native_flags(monkeypatch):
    def get_info(code, size, output, flags):
        if code == 0x1042:
            ctypes.cast(output, ctypes.POINTER(wintypes.BOOL))[0] = 0
        else:
            assert code == 0x0042 and size == ctypes.sizeof(preferences._HighContrast)
            data = ctypes.cast(output, ctypes.POINTER(preferences._HighContrast)).contents
            assert data.cbSize == size
            data.dwFlags = 1
        return 1

    user32 = SimpleNamespace(SystemParametersInfoW=get_info,
                             GetSysColor={5: 0x302010, 8: 0xFCFAF0, 13: 0x114422, 14: 0xffffff}.get)
    monkeypatch.setattr(ctypes, "windll", SimpleNamespace(user32=user32), raising=False)
    colors, reduced = _read_appearance()
    assert set(colors) == {"bg", "surface", "surfaceAlt", "border", "text", "textMuted", "accent",
                           "onAccent", "info", "success", "warning", "danger", "focus"}
    assert colors["bg"] == "#102030" and colors["onAccent"] == "#ffffff" and reduced


def test_typed_preferences_persist_notify_and_merge_concurrent_instances(tmp_path):
    path = tmp_path / "Panacea" / "settings.json"
    one = AppSettings(path=path)
    two = AppSettings(path=path)
    assert one.languageChoice == "system" and one.autoCheck
    assert not one.reduceMotion and not one.sidebarCollapsed
    signals = []
    one.languageChoiceChanged.connect(lambda: signals.append(one.languageChoice))
    one.languageChoice = "it"
    one.languageChoice = "invalid"
    two.reduceMotion = True
    two.sidebarCollapsed = True
    one.autoCheck = False
    assert signals == ["it"]
    reopened = AppSettings(path=path)
    assert reopened.languageChoice == "it" and not reopened.autoCheck
    assert reopened.reduceMotion and reopened.sidebarCollapsed
    assert [item.name for item in path.parent.iterdir()] == ["settings.json"]


def test_atomic_failure_preserves_previous_file_and_publishes_failure(tmp_path, monkeypatch):
    path = tmp_path / "Panacea" / "settings.json"
    settings = AppSettings(path=path)
    settings.languageChoice = "it"
    previous = path.read_bytes()
    failures = []
    settings.saveFailed.connect(lambda: failures.append(True))

    def fail_write(*_):
        raise OSError("fixture disk full")

    monkeypatch.setattr(preferences, "_atomic_write", fail_write)
    settings.languageChoice = "en"
    assert failures and settings.languageChoice == "it"
    assert path.read_bytes() == previous


def test_smoke_setting_never_resolves_user_folder_nor_writes(tmp_path, monkeypatch):
    def forbidden(*_):
        pytest.fail("Smoke settings touched the real file system or Windows appearance.")

    for name in ("_settings_file", "_read", "_atomic_write", "_windows_appearance"):
        monkeypatch.setattr(preferences, name, forbidden)
    settings = AppSettings(smoke=True, path=tmp_path / "unreachable.json")
    settings.finishStartup(False)
    settings.languageChoice = "it"
    settings.cacheReleaseNotes("2.2.0", "# Fixture")
    assert settings.languageChoice == "it"
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("payload", [b"not json", b"[]", b"\xff", b'{"autoCheck":"false","languageChoice":7}'])
def test_invalid_or_old_files_default_safely(tmp_path, payload):
    path = tmp_path / "settings.json"
    path.write_bytes(payload)
    settings = AppSettings(path=path)
    assert settings.autoCheck and settings.languageChoice == "system"
    settings.reduceMotion = True
    assert AppSettings(path=path).reduceMotion


def test_verified_start_defers_all_per_user_io_and_shows_cached_notes_once(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    monkeypatch.setattr(preferences, "VERSION", "2.1.1")
    old = AppSettings(path=path)
    old.finishStartup(False)
    assert not old.whatsNewVersion
    old.cacheReleaseNotes("2.2.0", "# Upgrade\n- [Details](https://example.invalid)\n<img src=x>")
    assert "example.invalid" not in path.read_text(encoding="utf-8")
    old.languageChoice = "it"

    monkeypatch.setattr(preferences, "VERSION", "2.2.0")
    with monkeypatch.context() as startup:
        for name in ("_read", "_atomic_write", "_settings_file", "_windows_appearance", "resolve_language"):
            startup.setattr(preferences, name, lambda *_args, **_kwargs: pytest.fail("I/O before readiness"))
        new = AppSettings(path=path, defer_load=True)
        translator = I18n(new)
        assert not new.whatsNewVersion and translator.language == "en"
    new.finishStartup(verified_update=True)
    assert translator.language == "it" and new.whatsNewVersion == "2.2.0"
    assert new.whatsNewNotes == "# Upgrade\n- Details"
    new.dismissWhatsNew()
    assert not new.whatsNewVersion and not new.whatsNewNotes
    third = AppSettings(path=path)
    third.finishStartup(False)
    assert not third.whatsNewVersion
    assert json.loads(path.read_bytes())["lastSeenVersion"] == "2.2.0"


def test_uninstrumented_predecessor_and_first_install_are_distinguished(tmp_path):
    first = AppSettings(path=tmp_path / "fresh.json")
    first.finishStartup(False)
    assert first.whatsNewVersion == ""
    from_legacy = AppSettings(path=tmp_path / "legacy.json", defer_load=True)
    from_legacy.finishStartup(verified_update=True)
    assert from_legacy.whatsNewVersion == preferences.VERSION
    assert from_legacy.whatsNewNotes == ""


def test_rollback_does_not_consume_or_reannounce_an_upgrade(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    path.write_text('{"lastSeenVersion":"2.2.0","releaseVersion":"2.3.0","releaseNotes":"# Future"}')
    monkeypatch.setattr(preferences, "VERSION", "2.1.1")
    rolled_back = AppSettings(path=path)
    rolled_back.finishStartup(False)
    assert not rolled_back.whatsNewVersion
    assert json.loads(path.read_bytes())["releaseVersion"] == "2.3.0"


def test_high_contrast_and_windows_animation_events_notify_together(monkeypatch):
    settings = AppSettings(smoke=True)
    changes = []
    settings.systemAppearanceChanged.connect(lambda: changes.append((settings.systemColors, settings.systemReducedMotion)))
    monkeypatch.setattr(preferences, "_windows_appearance", lambda: ({"accent": "#ffffff"}, True))
    settings._refresh_appearance()
    settings._refresh_appearance()
    assert changes == [({"accent": "#ffffff"}, True)]
    monkeypatch.setattr(preferences, "_windows_appearance", lambda: ({}, False))
    settings._refresh_appearance()
    assert changes[-1] == ({}, False)


def test_formatter_changes_language_live_and_smoke_override_is_isolated():
    settings = AppSettings(smoke=True)
    translator = I18n(settings)
    fixture = I18n(settings, language_override="en")
    settings.languageChoice = "it"
    assert translator.t("update.status.current", {"version": "2.1.1"}) == "Panacea 2.1.1 è aggiornato."
    assert translator.number(7.5, 1) == "7,5" and "1,5" in translator.bytes(1.5 * 1024**3)
    date = "2025-06-21T12:34:56.000Z"
    ita_date = translator.dateTime(date)
    past = (datetime.now(timezone.utc) - timedelta(hours=2, seconds=1)).isoformat()
    future = (datetime.now(timezone.utc) + timedelta(minutes=3, seconds=1)).isoformat()
    assert translator.relativeTime(past) == "2 ore fa"
    assert translator.relativeTime(future) == "Tra 3 minuti"
    settings.languageChoice = "en"
    assert translator.language == fixture.language == "en"
    assert translator.number(7.5, 1) == "7.5" and "1.5" in translator.bytes(1.5 * 1024**3)
    assert translator.dateTime(date) != ita_date
    assert translator.dateTime("invalid") == translator.t("format.unknown")
