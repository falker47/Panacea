"""The native HKCU test is opt-in exclusively on the guarded disposable runner."""
import os
from contextlib import nullcontext
from dataclasses import replace
import struct
import sys
import uuid

import pytest

from modules import startup_apps as startup
from qt_app.maintenance import MaintenanceService
from qt_app.tests.test_maintenance import FakeGuard


class Registry:
    HKEY_CURRENT_USER, HKEY_LOCAL_MACHINE = "HKCU", "HKLM"
    KEY_QUERY_VALUE, KEY_SET_VALUE, KEY_WOW64_64KEY, KEY_WOW64_32KEY = 1, 2, 256, 512
    REG_SZ, REG_EXPAND_SZ, REG_BINARY = 1, 2, 3

    def __init__(self):
        self.keys = {}
        self.writes = []

    def OpenKey(self, hive, path, _, access):
        key = (hive, path, access & 768)
        if key not in self.keys:
            raise FileNotFoundError
        return nullcontext(key)

    def CreateKeyEx(self, hive, path, _, access):
        key = (hive, path, access & 768)
        self.keys.setdefault(key, {})
        return nullcontext(key)

    def QueryInfoKey(self, key):
        return 0, len(self.keys[key]), 0

    def EnumValue(self, key, index):
        name = list(self.keys[key])[index]
        return name, *self.keys[key][name]

    def QueryValueEx(self, key, name):
        if name not in self.keys[key]:
            raise FileNotFoundError
        return self.keys[key][name]

    def SetValueEx(self, key, name, _, kind, value):
        self.writes.append((key, name))
        self.keys[key][name] = value, kind


@pytest.fixture
def inventory(tmp_path, monkeypatch):
    registry = Registry()
    monkeypatch.setitem(sys.modules, "winreg", registry)
    monkeypatch.setattr(startup, "known_folder", lambda name: tmp_path / name)
    monkeypatch.setattr(startup, "_guard_path", lambda path: nullcontext())
    monkeypatch.setattr(startup, "_shortcut", lambda path: (str(tmp_path / "test.exe"), "--test"))
    for folder in ("startup", "common_startup"):
        (tmp_path / folder).mkdir()
        (tmp_path / folder / "Example.lnk").write_bytes(b"fixture")
        (tmp_path / folder / "desktop.ini").touch()
    run = {"Example": ('"C:\\Fixture\\app.exe" -quiet', registry.REG_SZ)}
    for hive, view in (("HKCU", 256), ("HKLM", 256), ("HKLM", 512)):
        registry.keys[hive, startup.RUN, view] = run.copy()
    native = startup.WindowsStartup()
    monkeypatch.setattr(native, "version", lambda path: ("Fixture company", "Example app"))
    monkeypatch.setattr(native, "image_identity", lambda path: (1, 1, 20, 1))
    return startup.StartupApps(native), registry


def test_all_sources_unique_ids_and_only_approval_writes(inventory):
    apps, registry = inventory
    rows = apps.inventory()["apps"]
    assert len(rows) == len({r["id"] for r in rows}) == 5
    assert all(row["publisher"] == "Fixture company" and row["enabled"] is True for row in rows)
    assert all(row["description"] == "Example app" for row in rows)
    assert any("--test" in row["command"] for row in rows)
    sources = {key: value.copy() for key, value in registry.keys.items()}
    guard = FakeGuard()
    gateway = MaintenanceService(platform="nt", is_admin=lambda: True,
                                 factories={"startup": lambda: apps, "guard": lambda: guard})
    for row in rows:
        for action, flag in (("startup_disable", 3), ("startup_enable", 2)):
            prepared = gateway.prepare(action, target=row["id"])
            assert row["name"] in prepared["details"]
            assert gateway.execute(prepared["nonce"])["success"]
            with pytest.raises(ValueError):
                gateway.execute(prepared["nonce"])
            key, name = registry.writes[-1]
            assert key == ("HKCU" if row["scope"] == "user" else "HKLM", startup.APPROVED + "\\" + row["location"], 256)
            value, kind = registry.keys[key][name]
            state, changed = struct.unpack("<IQ", value)
            assert state == flag and (changed > 0) == (flag == 3) and kind == registry.REG_BINARY
    assert len(registry.writes) == guard.finished == 10
    assert all(registry.keys[k] == v for k, v in sources.items())


@pytest.mark.parametrize("change", ["command", "removed", "approval", "image"])
def test_target_is_fresh_inside_guard_and_stale_nonce_consumed(inventory, change, monkeypatch):
    apps, registry = inventory
    row = next(r for r in apps.inventory()["apps"] if r["scope"] == "user" and r["location"] == "Run")
    guard = FakeGuard()
    service = MaintenanceService(platform="nt", is_admin=lambda: True,
                                 factories={"startup": lambda: apps, "guard": lambda: guard})
    token = service.prepare("startup_disable", target=row["id"])["nonce"]
    key = ("HKCU", startup.RUN, 256)
    if change == "command":
        registry.keys[key]["Example"] = ("other.exe", 1)
    elif change == "removed":
        del registry.keys[key]["Example"]
    elif change == "approval":
        registry.keys["HKCU", startup.APPROVED + "\\Run", 256] = {"Example": (struct.pack("<IQ", 6, 0), 3)}
    else:
        monkeypatch.setattr(apps.backend, "image_identity", lambda path: (4, 7, 20, 1))
    assert service.execute(token)["status"] == "stale"
    assert guard.started == guard.finished == 1
    assert not registry.writes
    with pytest.raises(ValueError):
        service.execute(token)


def test_state_parsing_and_unknown_values_preserved(inventory):
    apps, registry = inventory
    assert startup.approval_state(struct.pack("<IQ", 6, 0)) == (True, None)
    assert startup.approval_state(struct.pack("<IQ", 3, 116444736000000000)) == (False, "1970-01-01T00:00:00+00:00")
    assert startup.approval_state(b"bad") == (None, None)
    key = ("HKCU", startup.APPROVED + "\\Run", 256)
    registry.keys[key] = {"Example": (b"foreign", registry.REG_BINARY)}
    with pytest.raises(ValueError):
        apps.target("startup_enable", startup.stable_id("user", "Run", "Example"))
    assert not registry.writes


def test_location_identity_is_stable_across_command_change():
    entry = startup.Entry("user", "Run", "NAME", "one", "", ())
    assert entry.id == replace(entry, command="two").id


def test_unquoted_executable_with_spaces_uses_first_resolving_prefix(monkeypatch):
    path = r"C:\Program Files\Example\App.exe"
    monkeypatch.setattr(startup, "_image_identity", lambda p: p == path)
    assert startup._executable(path + " -silent") == path
    monkeypatch.setattr(startup, "_image_identity", lambda p: p == r"C:\Program.exe")
    assert startup._executable(path + " -silent") == r"C:\Program.exe"


@pytest.mark.skipif(os.name != "nt" or os.getenv("PANACEA_FEATURE_STARTUP_FIXTURE") != "1",
                    reason="Only the dedicated disposable Windows feature job enables this fixture")
def test_disposable_hkcu_round_trip():
    import winreg
    from modules.maintenance_guard import MaintenanceGuard
    from scripts.hosted_installer_probe import disposable_guard
    temp, _ = disposable_guard()
    name = "Panacea-Startup-Test-" + uuid.uuid4().hex
    command = '"' + str(temp / (name + "-does-not-exist.exe")) + '"'
    hive, view = winreg.HKEY_CURRENT_USER, winreg.KEY_WOW64_64KEY
    approval_path = startup.APPROVED + "\\Run"
    access = view | winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE
    guard = MaintenanceGuard(temp / name / "maintenance-guard")
    gateway = MaintenanceService(factories={"guard": lambda: guard})
    with winreg.CreateKeyEx(hive, startup.RUN, 0, access) as run:
        with pytest.raises(FileNotFoundError):
            winreg.QueryValueEx(run, name)
        with pytest.raises(FileNotFoundError):
            with winreg.OpenKey(hive, approval_path, 0, access) as approved:
                winreg.QueryValueEx(approved, name)
        try:
            winreg.SetValueEx(run, name, 0, winreg.REG_SZ, command)
            for action, expected in (("startup_disable", 3), ("startup_enable", 2)):
                token = gateway.prepare(action, target=startup.stable_id("user", "Run", name))["nonce"]
                assert gateway.execute(token)["success"]
                with winreg.OpenKey(hive, approval_path, 0, view | winreg.KEY_QUERY_VALUE) as approved:
                    raw, kind = winreg.QueryValueEx(approved, name)
                state, ticks = struct.unpack("<IQ", raw)
                assert kind == winreg.REG_BINARY and state == expected and (ticks > 0) == (expected == 3)
                assert winreg.QueryValueEx(run, name) == (command, winreg.REG_SZ)
        finally:
            try:
                with winreg.OpenKey(hive, approval_path, 0, access) as approved:
                    winreg.DeleteValue(approved, name)
            except FileNotFoundError:
                pass
            winreg.DeleteValue(run, name)
        with pytest.raises(FileNotFoundError):
            winreg.QueryValueEx(run, name)
        with winreg.OpenKey(hive, approval_path, 0, access) as approved, pytest.raises(FileNotFoundError):
            winreg.QueryValueEx(approved, name)
