import ctypes
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from modules import logger


def test_folder_api_uses_guid_and_releases_shell_memory(tmp_path, monkeypatch):
    calls = []
    def get(guid, flags, token, output):
        calls.append((guid, flags, token))
        output._obj.value = str(tmp_path)
        return 0
    free = Mock()
    fake = SimpleNamespace(shell32=SimpleNamespace(SHGetKnownFolderPath=Mock(side_effect=get)),
                           ole32=SimpleNamespace(CoTaskMemFree=free))
    monkeypatch.setattr(ctypes, "windll", fake, raising=False)
    if logger.os.name != "nt":
        pytest.skip("Windows Known Folder ABI")
    for name in ("local", "downloads"):
        assert logger._shell_path(logger._FOLDER_IDS[name]) == tmp_path
    assert calls == [(logger._FOLDER_IDS[name].bytes_le, 0, None) for name in ("local", "downloads")]
    assert free.call_count == 2


def test_utf8_rotation_leaves_documents_untouched(tmp_path, monkeypatch):
    old = tmp_path / "Documents" / "SystemOptimizer" / "log.txt"
    old.parent.mkdir(parents=True)
    old.write_bytes(b"legacy")
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "decoy"))
    calls = []
    def folder(name):
        calls.append(name)
        return tmp_path
    monkeypatch.setattr(logger, "known_folder", folder)
    log = logging.getLogger("PanaceaLogger")
    monkeypatch.setattr(log, "handlers", [])
    monkeypatch.setattr(logger.Logger, "_instance", None)
    instance = logger.Logger()
    file = next(h for h in log.handlers if isinstance(h, logger.RotatingFileHandler))
    try:
        assert calls == ["local"]
        assert (file.maxBytes, file.backupCount) == (1024 * 1024, 5)
        file.maxBytes = 100
        for i in range(12):
            instance.log(f"rotazione più {i} " + "x" * 60, "WARNING")
        path = Path(file.baseFilename)
        assert path == tmp_path / "Panacea" / "logs" / "panacea.log"
        assert "più 11" in path.read_text(encoding="utf-8")
        assert len(list(path.parent.glob("panacea.log.*"))) == 5
        assert old.read_bytes() == b"legacy" and not (tmp_path / "decoy").exists()
    finally:
        for handler in log.handlers:
            handler.close()
