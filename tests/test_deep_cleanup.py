import os
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from modules import deep_cleanup as deep
from modules.commands import CommandRunner
from qt_app.maintenance import MaintenanceService
from qt_app.tests.test_maintenance import FakeGuard


@pytest.fixture
def caches(tmp_path, monkeypatch):
    roots = {k: tmp_path / k for k in ("windows", "program_data", "local", "temp")}
    for path in roots.values():
        path.mkdir()
    deletes = []

    @contextmanager
    def guard(path):
        assert path.is_relative_to(tmp_path)
        if not path.exists():
            raise FileNotFoundError
        if path.resolve() != path or not path.is_dir():
            raise OSError("fixture reparse point")
        yield

    def stamp(path, *, directory=False):
        info = path.lstat()
        if path.name == "thumbcache_locked.db" or path.is_symlink() or (not directory and info.st_nlink != 1):
            raise PermissionError("fixture locked or linked")
        return info.st_dev, info.st_ino, 0, 0, 0, info.st_mtime_ns, 0, info.st_size

    def remove(path, preview, *, expected):
        assert path.is_relative_to(tmp_path) and not preview and stamp(path) == expected
        deletes.append(path)
        path.unlink()
        return expected[-1]

    def rmdir(path, expected):
        assert path.is_relative_to(roots["temp"]) and stamp(path, directory=True)[:5] == expected[:5]
        path.rmdir()

    monkeypatch.setattr(deep, "_guard_path", guard)
    monkeypatch.setattr(deep, "guarded_stamp", stamp)
    monkeypatch.setattr(deep.CleanupManager, "_delete_file", staticmethod(remove))
    monkeypatch.setattr(deep, "remove_guarded_empty_folder", rmdir)
    manager = deep.DeepCleanup(folder=roots.__getitem__, delivery=lambda: (2, 128))
    return roots, manager, deletes


def put(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"cache")
    return path


def test_allowlisted_locations_preview_and_reversible_selection(caches):
    roots, manager, deletes = caches
    local, windows, temp = (roots[key] for key in ("local", "windows", "temp"))
    wer = Path("Microsoft/Windows/WER")
    explorer = local / "Microsoft/Windows/Explorer"
    selected = [put(roots[key] / wer / kind / "report" / "a.wer")
                for key in ("local", "program_data") for kind in ("ReportArchive", "ReportQueue")]
    selected += [put(explorer / "thumbcache_1.db"), put(explorer / "iconcache_x.db"),
                 put(local / "D3DSCache/nested/shader.bin"), put(temp / "Panacea-Qt-update-old/Panacea-az7290_x.part")]
    old = temp / "Panacea-Qt-update-old"
    protected = [put(explorer / "other.db"), put(explorer / "thumbcache_locked.db"),
                 put(explorer / "nested/thumbcache_1.db"), put(windows / "SoftwareDistribution/Download/a"),
                 put(temp / "panacea-update-helper/job.json"), put(temp / "Panacea-Qt-update-new/Panacea-f.exe"),
                 put(old / "Panacea.exe.update-ready.json"), put(old / ".Panacea.exe.token.backup"),
                 put(old / "Panacea-updater.exe"), put(old / "Panacea-backup.exe")]
    dumps = [put(windows / "Minidump/a.dmp"), put(windows / "MEMORY.DMP"), put(local / "CrashDumps/b.DMP")]
    os.utime(old, (1000, 1000))
    rows = {r["id"]: r for r in manager.preview()["categories"]}
    assert not deletes and all(p.exists() for p in selected + protected + dumps)
    assert rows["wer_reports"]["count"] == 4 and rows["wer_reports"]["bytes"] == 20
    assert rows["thumbnail_cache"]["skipped"] == 1
    assert not rows["crash_dumps"]["default_selected"] and rows["crash_dumps"]["count"] == 3
    assert rows["panacea_leftovers"]["samples"] == [str(selected[-1])]
    target = manager.target("deep_cleanup", "shader_cache,thumbnail_cache,wer_reports,panacea_leftovers")
    result = manager.apply(target, None, lambda _: None, lambda: False)
    assert result["status"] == "partial" and len(result["steps"]) == 4
    assert set(deletes) == set(selected)
    assert all(p.exists() for p in protected + dumps)
    assert all(not p.exists() for p in selected)


def test_stale_selection_rejected_before_any_delete(caches):
    roots, manager, deletes = caches
    item = put(roots["local"] / "D3DSCache/one")
    guard = FakeGuard()
    service = MaintenanceService(platform="nt", is_admin=lambda: True,
                                 factories={"deep": lambda: manager, "guard": lambda: guard})
    manager.preview()
    token = service.prepare("deep_cleanup", target="shader_cache")["nonce"]
    item.write_bytes(b"changed")
    result = service.execute(token)
    assert result["status"] == "stale" and not deletes and item.exists()
    assert guard.started == guard.finished == 1
    with pytest.raises(ValueError):
        service.execute(token)


def test_empty_old_download_folder_is_removed_but_recent_folder_survives(caches):
    roots, manager, _ = caches
    older = roots["temp"] / "Panacea-Qt-update-a"
    recent = roots["temp"] / "Panacea-Qt-update-b"
    older.mkdir()
    recent.mkdir()
    os.utime(older, (1000, 1000))
    result = manager.apply(manager.target("deep_cleanup", "panacea_leftovers"), None, None, lambda: False)
    assert result["success"] and not older.exists() and recent.is_dir()


def test_delivery_command_exact_and_missing_cmdlet(caches):
    _, manager, _ = caches
    args = CommandRunner.command_args(deep.DELIVERY_COMMAND)
    assert Path(args[0]).name == "powershell.exe"
    assert args[1:4] == ["-NoProfile", "-NonInteractive", "-Command"]
    assert args[4].endswith(r"DeliveryOptimization\Delete-DeliveryOptimizationCache -Force")
    for suffix in (" -IncludePinnedFiles", " ; whoami", "\n"):
        with pytest.raises(ValueError):
            CommandRunner.command_args(deep.DELIVERY_COMMAND + suffix)
    calls = []
    def run(command, description, log):
        calls.append(command)
        return True
    runner = SimpleNamespace(run_command_stream=run, completion_unknown=False)
    target = manager.target("deep_cleanup", "delivery_optimization")
    assert target.inventory[0].row()["bytes"] == 128
    assert manager.apply(target, runner, None, lambda: False)["success"]
    manager.delivery = lambda: None
    target = manager.target("deep_cleanup", "delivery_optimization")
    assert not target.inventory[0].row()["available"]
    assert manager.apply(target, runner, None, lambda: False)["steps"][0]["status"] == "unavailable"
    assert calls == [deep.DELIVERY_COMMAND]


def test_cmdlet_disappearing_during_confirmation_reports_unavailable(caches):
    _, manager, deletes = caches
    service = MaintenanceService(platform="nt", is_admin=lambda: True,
                                 factories={"deep": lambda: manager, "guard": FakeGuard})
    token = service.prepare("deep_cleanup", target="delivery_optimization")["nonce"]
    manager.delivery = lambda: None
    result = service.execute(token)
    assert result["status"] == result["steps"][0]["status"] == "unavailable"
    assert not deletes


@pytest.mark.parametrize("bad", [None, "", "../Windows", "unknown", "shader_cache,", "shader_cache,shader_cache", 42])
def test_unknown_target_never_reaches_filesystem(bad):
    service = MaintenanceService(factories={"deep": lambda: deep.DeepCleanup(folder=lambda _: pytest.fail("read"))})
    with pytest.raises(ValueError):
        service.prepare("deep_cleanup", target=bad)


@pytest.mark.skipif(os.name != "nt", reason="Native guarded file handles")
def test_native_preview_delete_and_replaced_leaf_in_temporary_tree(tmp_path):
    root = tmp_path / "D3DSCache"
    original = put(root / "one.bin")
    manager = deep.DeepCleanup(folder=lambda _: tmp_path, delivery=lambda: None)
    target = manager.target("deep_cleanup", "shader_cache")
    assert target.inventory[0].row()["count"] == 1 and original.exists()
    original.write_bytes(b"replace before opening")
    assert manager.apply(target, None, None, lambda: False)["status"] == "partial"
    assert original.read_bytes() == b"replace before opening"
    target = manager.target("deep_cleanup", "shader_cache", fresh=True)
    assert manager.apply(target, None, None, lambda: False)["success"]
    assert not original.exists()


def test_reparse_point_is_skipped_before_descending(caches, monkeypatch):
    roots, manager, deletes = caches
    directory = roots["local"] / "D3DSCache"
    sentinel = put(directory / "junction" / "sentinel")
    original = deep.os.scandir

    class Reparse:
        name = "junction"

        def stat(self, *, follow_symlinks):
            assert not follow_symlinks
            return SimpleNamespace(st_mode=0o040755, st_file_attributes=0x400)

    @contextmanager
    def scan(path):
        if path == directory:
            yield [Reparse()]
        else:
            assert Path(path) != sentinel.parent
            with original(path) as entries:
                yield entries

    monkeypatch.setattr(deep.os, "scandir", scan)
    target = manager.target("deep_cleanup", "shader_cache")
    assert target.inventory[0].skipped == 1 and not target.inventory[0].files
    assert manager.apply(target, None, None, lambda: False)["status"] == "partial"
    assert not deletes and sentinel.exists()
