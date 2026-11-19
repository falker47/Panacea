from pathlib import Path

import pytest

from scripts.update_compat.stamp_candidate import choose_version, main, stamp


@pytest.mark.parametrize(("source", "tags", "expected"), [
    ("2.1.1", ["v1.47", "v2.1.1"], "2.1.101"),
    ("2.2.0", ["v2.1.1"], "2.2.0"),
    ("2.1.1", ["v2.1.1", "v2.9.8", "misc"], "2.9.108"),
    ("2.1.1", ["v2.2.0rc1"], "2.2.100"),
])
def test_selects_version_above_all_tags(source, tags, expected):
    assert choose_version(source, tags) == expected


def test_stamp_preserves_existing_notes_and_other_source_bytes(tmp_path):
    version = tmp_path / "version.py"
    version.write_bytes(b'VERSION = "2.1.1"\r\nGITHUB_REPO = "falker47/Panacea"\r\n')
    notes = tmp_path / "docs/releases"
    notes.mkdir(parents=True)
    assert stamp(tmp_path, ["v2.1.1"]) == "2.1.101"
    assert version.read_bytes() == b'VERSION = "2.1.101"\r\nGITHUB_REPO = "falker47/Panacea"\r\n'
    note = notes / "2.1.101.md"
    assert note.is_file()
    note.write_bytes(b"Existing notes")
    assert stamp(tmp_path, ["v2.1.1"]) == "2.1.101"
    assert note.read_bytes() == b"Existing notes"


def test_unavailable_tags_and_local_execution_fail_closed(monkeypatch):
    with pytest.raises(ValueError, match="No version tags"):
        choose_version("2.1.1", [])
    monkeypatch.delenv("PANACEA_ALLOW_HOSTED_PROBE", raising=False)
    original = Path("version.py").read_bytes()
    with pytest.raises(RuntimeError):
        main()
    assert Path("version.py").read_bytes() == original
