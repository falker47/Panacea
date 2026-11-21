"""Evidence-based health indicators. Weights and units are published in docs/features-2.2.md."""
from __future__ import annotations

import ctypes
import ntpath
import os
import re
import shutil

from modules.cleanup import _RecycleBinInfo
from modules.commands import system_executable

GIB = 1024 ** 3
# id: (maximum deduction, recommended gateway action, destination in the shell)
RULES = {
    "space": (25, "storage_analysis", "cleanup"),
    "reboot": (15, "windows_update", "repair"),
    "uptime": (5, "windows_update", "repair"),
    "updates": (15, "windows_update", "repair"),
    "restore": (10, "restore_point", "repair"),
    "startup": (10, "startup_apps", "startup"),
    "reclaimable": (10, "deep_cleanup_preview", "cleanup"),
    "recycle": (5, "recycle_empty", "cleanup"),
    "guard": (5, "guard_status", "history"),
}


def _attempt(callback):
    try:
        return callback()
    except (OSError, AttributeError, ImportError, ValueError, RuntimeError):
        return None


def _reboot():
    import winreg
    checks = {
        "CBS": (r"SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending", None),
        "WindowsUpdate": (r"SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired", None),
        "PendingFileRenameOperations": (r"SYSTEM\CurrentControlSet\Control\Session Manager", "PendingFileRenameOperations"),
    }
    result = {}
    for name, (path, value) in checks.items():
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
                if value:
                    paths, kind = winreg.QueryValueEx(key, value)
                    result[name] = any(paths) if kind == winreg.REG_MULTI_SZ else None
                else:
                    result[name] = True
        except FileNotFoundError:
            result[name] = False
        except OSError:
            result[name] = None
    return result


def _protection(drive):
    import winreg
    access = winreg.KEY_READ | winreg.KEY_WOW64_64KEY
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Policies\Microsoft\Windows NT\SystemRestore",
                            0, access) as key:
            if winreg.QueryValueEx(key, "DisableSR") == (1, winreg.REG_DWORD):
                return False
    except FileNotFoundError:
        pass
    volume = ctypes.create_unicode_buffer(64)
    if not ctypes.windll.kernel32.GetVolumeNameForVolumeMountPointW(drive + "\\", volume, len(volume)):
        return None
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\SPP\Clients",
                        0, access) as key:
        values, kind = winreg.QueryValueEx(key, "{09F7EDC5-294E-4180-AF6A-FB0E6A0E9513}")
    if kind != winreg.REG_MULTI_SZ:
        return None
    if any(value.casefold().startswith(volume.value.casefold()) for value in values):
        return True
    if all(re.match(r"^\\\\\?\\Volume\{[0-9a-f-]{36}\}\\", value, re.I) for value in values):
        return False
    return None


def _recycle():
    info = _RecycleBinInfo()
    info.cbSize = ctypes.sizeof(info)
    if ctypes.windll.shell32.SHQueryRecycleBinW(None, ctypes.byref(info)) == 0:
        return info.i64Size if info.i64Size >= 0 else None
    return None


def native_evidence():
    if os.name != "nt":
        return {}
    drive = ntpath.splitdrive(system_executable("cmd.exe"))[0]
    usage = _attempt(lambda: shutil.disk_usage(drive + "\\"))
    tick = ctypes.windll.kernel32.GetTickCount64
    tick.restype = ctypes.c_ulonglong
    return {"drive": drive, "free_bytes": usage.free if usage else None, "total_bytes": usage.total if usage else None,
            "reboot": _attempt(_reboot), "uptime_days": tick() // 86_400_000,
            "restore": _attempt(lambda: _protection(drive)), "recycle_bytes": _attempt(_recycle)}


def collect(read, deep_preview, *, native=None):
    facts = _attempt(native or native_evidence) or {}
    updates = _attempt(lambda: read("windows_updates")) or {}
    startup = _attempt(lambda: read("startup_apps")) or {}
    temp = _attempt(lambda: read("temp_preview")) or {}
    deep = _attempt(deep_preview) or {}
    guard = _attempt(lambda: read("guard_status")) or {}
    facts["updates"] = updates.get("recommended") if updates.get("verified") else None
    facts["optional_updates"] = updates.get("optional") if updates.get("verified") else None
    apps = startup.get("apps")
    if apps is not None:
        facts["startup"] = sum(row["enabled"] is True for row in apps)
        facts["startup_partial"] = bool(startup.get("issues")) or any(row["enabled"] is None for row in apps)
    # Stale Panacea downloads overlap Temp. Crash dumps are opt-in. Windows reports
    # a service-wide DO estimate that can include pinned content. Count none twice.
    measured = [row for row in deep.get("categories", []) if row["id"] in ("wer_reports", "thumbnail_cache", "shader_cache")]
    if "bytes" in temp or any(row["available"] for row in measured):
        facts["temp_bytes"] = temp.get("bytes")
        facts["deep_bytes"] = sum(row["bytes"] for row in measured if row["available"])
        facts["reclaimable"] = (temp.get("bytes") or 0) + facts["deep_bytes"]
        facts["reclaim_partial"] = (temp.get("bytes") is None or bool(temp.get("skipped") or temp.get("errors"))
                                    or len(measured) != 3 or any(not row["available"] or row["skipped"] for row in measured))
    facts["guard"] = guard.get("blocked")
    return evaluate(facts)


def evaluate(facts):
    """Score is the upper bound given observed penalties. Unknown weight defines the lower bound."""
    findings = []
    score = 100
    unknown = 0

    def add(key, bad, evidence, *, partial=False):
        nonlocal score, unknown
        weight, action, section = RULES[key]
        deduction = weight if bad is True else 0
        score -= deduction
        if bad is None or (partial and not bad):
            unknown += weight
        severity = ("warning" if bad else "unknown" if bad is None or partial else "ok")
        findings.append({"id": key, "severity": severity, "evidence": evidence,
                         "weight": weight, "deduction": deduction, "action": action, "section": section})

    free, total = facts.get("free_bytes"), facts.get("total_bytes")
    add("space", free * 10 < total if free is not None and total else None,
        {"drive": facts.get("drive"), "free_bytes": free, "total_bytes": total})
    reboot = facts.get("reboot") or {}
    pending = True if any(v is True for v in reboot.values()) else False if reboot and None not in reboot.values() else None
    add("reboot", pending, {"indicators": [k for k, v in reboot.items() if v is True],
                            "checked": sum(v is not None for v in reboot.values())})
    days = facts.get("uptime_days")
    add("uptime", days >= 7 if days is not None else None, {"days": days})
    updates = facts.get("updates")
    add("updates", updates > 0 if updates is not None else None,
        {"recommended": updates, "optional": facts.get("optional_updates")})
    restore = facts.get("restore")
    add("restore", not restore if restore is not None else None, {"drive": facts.get("drive"), "enabled": restore})
    for key, name, limit, field, incomplete in (
            ("startup", "startup", 10, "enabled", "startup_partial"),
            ("reclaimable", "reclaimable", GIB, "bytes", "reclaim_partial"),
            ("recycle", "recycle_bytes", GIB // 2, "bytes", "")):
        value = facts.get(name)
        details = {field: value}
        if key == "reclaimable":
            details.update(temp_bytes=facts.get("temp_bytes"), deep_bytes=facts.get("deep_bytes"))
        add(key, value >= limit if value is not None else None, details, partial=bool(facts.get(incomplete)))
    add("guard", facts.get("guard"), {"blocked": facts.get("guard")})
    return {"score": score, "score_min": score - unknown, "unknown_weight": unknown, "findings": findings}
