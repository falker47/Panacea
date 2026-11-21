import ast
from contextlib import contextmanager, nullcontext
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace
import threading

import pytest

from modules import storage_analysis as storage


class Entry:
    def __init__(self, name, *, size=0, directory=False, reparse=False):
        self.name = name
        self.info = SimpleNamespace(st_mode=0o040755 if directory else 0o100644, st_size=size,
                                    st_file_attributes=0x400 if reparse else 0)

    def stat(self, *, follow_symlinks):
        assert follow_symlinks is False
        return self.info


def test_depth_aggregates_top_k_reparse_points_and_session_cache(tmp_path, monkeypatch):
    root = tmp_path
    tree = {root: [Entry("link", directory=True, reparse=True), Entry("a", directory=True)],
            root / "a": [Entry("b", directory=True)],
            root / "a/b": [Entry("c", directory=True)],
            root / "a/b/c": [Entry("d", directory=True)],
            root / "a/b/c/d": [Entry(str(i), size=storage.LARGE_FILE + i) for i in range(62)]}
    for i in range(24):
        tree[root].append(Entry(f"f{i}", directory=True))
        tree[root / f"f{i}"] = [Entry("small", size=i)]
    visited = []

    @contextmanager
    def entries(path):
        visited.append(path)
        yield tree[path]

    monkeypatch.setattr(storage, "_entries", entries)
    subject = storage.StorageAnalysis(root=lambda selection: root)
    progress = []
    result = subject.scan(progress=progress.append)
    assert result["status"] == "completed" and progress[-1] == result["entries"]
    assert result["reparse_points"] == 1 and root / "link" not in visited
    assert len(result["folders"]) == 20 and len(result["files"]) == 50
    expected = sum(storage.LARGE_FILE + i for i in range(62))
    assert all(row["bytes"] == expected for row in result["folders"][:3])
    assert all(len(Path(r["path"]).relative_to(root).parts) <= 3 for r in result["folders"])
    assert [r["bytes"] for r in result["files"]] == list(range(storage.LARGE_FILE + 61, storage.LARGE_FILE + 11, -1))
    before = visited.copy()
    assert subject.scan()["cached"] and visited == before
    assert not subject.scan(refresh=True)["cached"] and len(visited) == 2 * len(before)


def test_cancel_entry_deadline_and_inaccessible_root(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "_entries", lambda _: nullcontext([Entry(str(i)) for i in range(12)]))
    subject = storage.StorageAnalysis(root=lambda _: tmp_path, max_entries=3)
    assert subject.scan()["entries"] == 3 and subject.scan()["status"] == "entry_limit"
    cancel = threading.Event()
    out = subject.scan(cancel=cancel, refresh=True, progress=lambda _: cancel.set())
    assert out["status"] == "cancelled" and out["entries"] == 1
    clock = iter(range(30)).__next__
    subject = storage.StorageAnalysis(root=lambda _: tmp_path, seconds=4, clock=clock)
    assert subject.scan()["status"] == "time_limit"
    cancel.set()
    assert subject.scan(cancel=cancel)["entries"] == 0
    root = tmp_path / "missing"

    def denied(path):
        raise PermissionError(str(path))

    monkeypatch.setattr(storage, "_entries", denied)
    out = storage.StorageAnalysis(root=lambda _: root).scan()
    assert out["status"] == "unavailable" and out["skipped"] == 1


def test_open_requires_listed_item_and_uses_system_explorer(tmp_path, monkeypatch):
    folder = tmp_path / "one folder"
    folder.mkdir()
    manager = storage.StorageAnalysis(root=lambda _: tmp_path)
    assert manager.scan()["folders"][0]["path"] == str(folder)
    monkeypatch.setattr(storage, "_guard_path", lambda path: nullcontext())
    monkeypatch.setattr(storage, "system_executable", lambda name: str(tmp_path / "Windows/System32" / name))
    calls = []
    monkeypatch.setattr(storage.subprocess, "Popen", lambda args, **kwargs: calls.append((args, kwargs)))
    manager.open_in_explorer("profile", str(folder))
    assert calls == [([str(tmp_path / "Windows/explorer.exe"), "/select,", str(folder)], {"shell": False})]
    with pytest.raises(ValueError):
        manager.open_in_explorer("profile", str(tmp_path / "unlisted.exe"))
    assert len(calls) == 1


@pytest.mark.parametrize("choice", ["..", "//server/share", "C:\\folder", "file:///C:/", "C: & run"])
def test_no_arbitrary_scan_roots(choice):
    with pytest.raises(ValueError):
        storage.StorageAnalysis().scan(choice)


def test_module_has_no_filesystem_write_api_or_shell():
    tree = ast.parse(Path(storage.__file__).read_text(encoding="utf-8"))
    banned = {"unlink", "remove", "rmdir", "rmtree", "rename", "replace", "write", "write_bytes",
              "write_text", "mkdir", "makedirs", "touch", "chmod", "truncate", "system", "startfile"}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = ast.unparse(node.func)
        assert name.split(".")[-1] not in banned
        if name == "os.open":
            assert ast.unparse(node.args[1]) == "os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW"
        else:
            assert name not in {"open", "io.open", "Path.open"}
        assert all(kw.arg != "shell" or ast.literal_eval(kw.value) is False for kw in node.keywords)


def test_native_directory_link_in_fixture_never_enters_rankings(tmp_path):
    root, outside = tmp_path / "scan", tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (outside / "sentinel").write_bytes(b"outside")
    if os.name == "nt":
        subprocess.run([storage.system_executable("cmd.exe"), "/d", "/c", "mklink", "/J",
                        str(root / "redirected"), str(outside)], check=True, capture_output=True)
    else:
        os.symlink(outside, root / "redirected", target_is_directory=True)
    result = storage.StorageAnalysis(root=lambda _: root).scan()
    assert result["reparse_points"] == 1 and not result["folders"] and not result["files"]
