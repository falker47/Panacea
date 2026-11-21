from contextlib import nullcontext
import sys
from types import SimpleNamespace

from modules import health_check as health
from qt_app.maintenance import ACTIONS
from qt_app.services import READ_ACTIONS, ReadService


def facts():
    return {"drive": "C:", "free_bytes": 10, "total_bytes": 100, "reboot": {"CBS": False, "WindowsUpdate": False,
            "PendingFileRenameOperations": False}, "uptime_days": 6, "restore": True, "recycle_bytes": 0,
            "updates": 0, "optional_updates": 1, "startup": 2, "reclaimable": 0, "guard": False}


def test_boundaries_each_deduction_and_action_exists():
    source = facts()
    good = health.evaluate(source)
    assert good["score"] == good["score_min"] == 100
    assert sum(r["weight"] for r in good["findings"]) == 100
    source.update(free_bytes=9, reboot={"CBS": True}, uptime_days=7, restore=False, recycle_bytes=health.GIB // 2,
                  updates=1, startup=10, reclaimable=health.GIB, guard=True)
    bad = health.evaluate(source)
    assert bad == health.evaluate(source)
    assert bad["score"] == bad["score_min"] == 0
    for finding in bad["findings"]:
        assert finding["severity"] == "warning" and finding["evidence"]
        assert finding["action"] in READ_ACTIONS | ACTIONS
        assert finding["deduction"] == finding["weight"]
    assert health.evaluate({})["score_min"] == 0
    assert all(row["severity"] == "unknown" for row in health.evaluate({})["findings"])


def test_health_reads_existing_evidence_excludes_overlap_and_preserves_unknowns():
    rows = {"windows_updates": {"recommended": -1, "optional": -1, "verified": False},
            "guard_status": {"blocked": True}, "startup_apps": {"apps": [{"enabled": True}, {"enabled": None}]},
            "temp_preview": {"bytes": 24, "skipped": 1}}
    deep = [{"id": key, "available": True, "bytes": 40, "skipped": 0}
            for key in ("wer_reports", "thumbnail_cache", "shader_cache", "crash_dumps", "panacea_leftovers", "delivery_optimization")]
    result = health.collect(rows.__getitem__, lambda: {"categories": deep}, native=lambda: {})
    by_id = {row["id"]: row for row in result["findings"]}
    assert by_id["updates"]["severity"] == "unknown"
    assert by_id["startup"]["evidence"]["enabled"] == 1 and by_id["startup"]["severity"] == "unknown"
    assert by_id["reclaimable"]["evidence"] == {"bytes": 144, "temp_bytes": 24, "deep_bytes": 120}
    assert by_id["guard"]["deduction"] == 5
    assert result["score_min"] < result["score"]


def test_reboot_reads_all_three_indicators_without_treating_denied_as_clear(monkeypatch):
    opened = []
    def open_key(hive, key, _, access):
        opened.append(key)
        if key.endswith("RebootRequired"):
            raise PermissionError
        if key.endswith("RebootPending"):
            raise FileNotFoundError
        return nullcontext(key)
    registry = SimpleNamespace(OpenKey=open_key, HKEY_LOCAL_MACHINE=1, KEY_READ=1, KEY_WOW64_64KEY=256, REG_MULTI_SZ=7,
                               QueryValueEx=lambda *args: (["source", ""], 7))
    monkeypatch.setitem(sys.modules, "winreg", registry)
    flags = health._reboot()
    assert len(opened) == 3
    assert flags == {"CBS": False, "WindowsUpdate": None, "PendingFileRenameOperations": True}
    out = health.evaluate({"reboot": flags})
    assert next(r for r in out["findings"] if r["id"] == "reboot")["deduction"] == 15


def test_read_gateway_uses_only_fake_managers_and_health_does_not_replace_user_preview(monkeypatch):
    monkeypatch.setattr(health, "native_evidence", lambda: {})
    seen = []
    class Preview:
        def preview(self, *, remember=True):
            seen.append(remember)
            return {"categories": []}

    reader = ReadService(factories={
        "startup": lambda: SimpleNamespace(inventory=lambda: {"apps": [], "issues": []}),
        "deep": Preview, "storage": lambda: SimpleNamespace(scan=lambda: {"status": "completed"}),
        "cleanup": lambda: SimpleNamespace(preview_temp_files=lambda: (0, 0), last_result=None),
        "monitor": lambda: SimpleNamespace(get_windows_update_status=lambda: (0, 0, ""), close=lambda: None),
        "guard": lambda: SimpleNamespace(is_blocked=lambda: False, last_error=""),
    })
    assert reader.collect("startup_apps")["apps"] == []
    assert reader.collect("storage_analysis")["status"] == "completed"
    assert reader.collect("deep_cleanup_preview") == {"categories": []}
    assert reader.collect("health_check")["findings"]
    assert seen == [True, False]
    reader.close()


def test_protection_matches_system_volume_or_explicit_disabled_policy(monkeypatch):
    volume = "\\\\?\\Volume{00000000-0000-0000-0000-000000000002}\\"
    state = {"DisableSR": (0, 4), "{09F7EDC5-294E-4180-AF6A-FB0E6A0E9513}": ([volume + ":(C%3A)"], 7)}
    def mount_name(drive, output, length):
        assert drive == "C:\\"
        output.value = volume
        return 1
    kernel = SimpleNamespace(GetVolumeNameForVolumeMountPointW=mount_name)
    monkeypatch.setattr(health.ctypes, "windll", SimpleNamespace(kernel32=kernel), raising=False)
    reg = SimpleNamespace(KEY_READ=1, KEY_WOW64_64KEY=256, REG_DWORD=4, REG_MULTI_SZ=7, HKEY_LOCAL_MACHINE=1,
                          OpenKey=lambda *args: nullcontext(1), QueryValueEx=lambda key, name: state[name])
    monkeypatch.setitem(sys.modules, "winreg", reg)
    assert health._protection("C:") is True
    state["DisableSR"] = (1, 4)
    assert health._protection("C:") is False
    state["DisableSR"] = (0, 4)
    state["{09F7EDC5-294E-4180-AF6A-FB0E6A0E9513}"] = (["unrecognized record"], 7)
    assert health._protection("C:") is None
