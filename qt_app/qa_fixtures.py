"""In-memory services, deterministic scenarios and event-driven smoke captures."""
from __future__ import annotations

import json
import os
from pathlib import Path
import time
from types import SimpleNamespace

from PySide6.QtCore import QTimer

from qt_app.catalog import SECTIONS
from qt_app.maintenance import MaintenanceService
from qt_app.visual_review import inspect_window, items, source_digest


class VisualMaintenance:
    def __init__(self):
        # Only the side-effect-free prepare/reject pair is used. No manager is created.
        self._preview = MaintenanceService(is_admin=lambda: False, platform="fixture")
        self._nonce = None
        self.executed = []

    def prepare(self, action, drive):
        prepared = self._preview.prepare(action, drive)
        self._nonce = prepared["nonce"]
        return prepared

    def execute(self, nonce, **callbacks):
        if not self._nonce or self._nonce != nonce:
            raise ValueError("Stale fixture confirmation")
        self.reject()
        self.executed.append(nonce)
        return {"status": "completed", "message": "", "steps": []}

    def reject(self):
        self._nonce = None
        self._preview.reject()

    def cancel(self):
        pass

    def close(self):
        self.reject()


class VisualReads:
    def __init__(self, snapshots):
        self.snapshots = dict(snapshots)

    def collect(self, action):
        return dict(self.snapshots.get(action, {}))

    def close(self):
        pass


class VisualUpdates:
    install_eligible = False

    def __init__(self):
        self.release = None

    def check(self):
        return self.release

    def cancel_download(self):
        pass


def apply_scenario(metrics, reader, maintenance, updater, scenario, section, language):
    metrics._values.update(cpu="30.8%", ram="90.7%", disk="97.5%", details={
        "ram": [16.0, 1.5, 90.7], "disk": [256.0, 6.4, 97.5], "battery": 72,
        "power": "Plugged In", "uptime": "0d 3h 8m"})
    metrics._history.update(cpu=[17, 16, 18, 19, 17, 24, 27, 31, 30, 32, 30.8],
                            ram=[84, 84.3, 85, 85.1, 86, 88, 89, 90.7], disk=[97.5] * 8)
    reader._results.update({
        "hardware": {"os": "Windows 11", "cpu_name": "AMD Ryzen 7", "ram_info": "DDR5", "disk_model": "NVMe SSD"},
        "windows_updates": {"recommended": 0, "optional": 0, "verified": True},
        "temp_preview": {"bytes": 324 * 1024**2, "count": 128, "no_files_deleted": True, "skipped": 0, "errors": 0},
        "drives": {"drives": [{"letter": "C:", "available": True, "type": "Fixed", "total_bytes": 256 * 1024**3,
                               "free_bytes": int(6.4 * 1024**3), "used_percent": 97.5, "error": ""}]},
        "turbo_status": {"states": {"power": True, "visual": False, "sysmain": False, "wsearch": False,
                                     "spooler": False}, "master": False, "saved_count": 2, "restore_available": True},
        "guard_status": {"blocked": False, "message": ""},
    })
    reader._drives = ["C:"]
    maintenance.setLanguage(language)
    if scenario == "unknown":
        metrics._values = {"cpu": "—", "ram": "—", "disk": "—", "details": {}}
        metrics._history = {"cpu": [], "ram": [], "disk": []}
        reader._results = {"hardware": {}, "windows_updates": {"verified": False}, "turbo_status": {}}
        reader._drives = []
    if scenario == "long-text":
        reader._results["hardware"].update(os="Windows 11 Enterprise LTSC · " + "Microsoft " * 12,
                                          cpu_name="AMD Ryzen 7 · " + "PRO 8840U " * 12)
    if scenario in ("running", "completed", "partial", "failed", "cancelled"):
        maintenance._last_action = {"home": "windows_update", "repair": "sfc", "startup": "apps_settings",
                                    "performance": "power_on", "guided": "resurrection"}.get(section, "quick_cleanup")
        maintenance._result_status = scenario
        maintenance._busy = scenario == "running"
        maintenance._progress_total = 10 if section == "guided" else 3
        count = 2 if scenario in ("running", "cancelled") else 1 if scenario == "failed" else maintenance._progress_total
        maintenance._progress_done = count
        maintenance._steps = [{"success": scenario not in ("failed", "partial") or i < count-1,
                               "name": "", "message": ""} for i in range(count)]
        maintenance._output = "\n".join(f"{i+1}/{maintenance._progress_total}" for i in range(count))
        maintenance._remember_result()
        maintenance._section_logs[maintenance.activeSection] = maintenance._output
    if scenario == "confirmation":
        maintenance.prepare("quick_cleanup", "")
    if scenario != "unknown":
        notes = ("## Navigazione\n\n- Accesso rapido con **Ctrl+K**." if language == "it" else
                 "## Navigation\n\n- Quick access with **Ctrl+K**.")
        updater._flow.release = SimpleNamespace(version="2.2.0", notes=notes)
        updater._version = updater._flow.release.version
        updater._notes = notes
        updater._last_checked = "2026-05-15T12:00:00+00:00"
        updater._available = True
        updater._set_status("availableReadOnly", version=updater._version)
    reader._service = VisualReads(reader._results)


def run_smoke(app, window, args, section, language, warnings, app_id, trace):
    """Wait for real async page creation before observing geometry or pixels."""
    if args.smoke_width:
        window.setWidth(args.smoke_width)
    if args.smoke_height:
        window.setHeight(args.smoke_height)
    phases = []
    if args.smoke_profile:
        phases.extend((phase, page) for phase in ("first", "warm") for page in SECTIONS)
    targets = SECTIONS if args.smoke_all_sections else (section,)
    phases.extend(("capture", page) for page in targets)
    profile = []
    started = time.perf_counter()
    digest = source_digest(Path(__file__).parent)
    failed = False

    def fail(exc):
        nonlocal failed
        failed = True
        trace("smoke failure: " + str(exc))
        print(f"Qt smoke failure: {exc}", flush=True)
        app.exit(3)

    def advance():
        if not phases:
            if args.smoke_profile:
                args.smoke_profile.parent.mkdir(parents=True, exist_ok=True)
                args.smoke_profile.write_text(json.dumps({
                    "fixture_only": True, "platform": app.platformName(),
                    "logical_size": [window.width(), window.height()], "navigation": profile,
                }, indent=2), encoding="utf-8")
            if warnings:
                fail("\n".join(warnings))
            else:
                # Preserve the visible-window observation period for packaged startup probes.
                delay = max(0, 1200 - int((time.perf_counter() - started) * 1000))
                QTimer.singleShot(delay, lambda: app.exit(0) if not failed else None)
            return
        phase, selected = phases.pop(0)
        index = SECTIONS.index(selected)
        before = time.perf_counter()
        window.setProperty("currentTab", index)
        callback = time.perf_counter()

        def settle():
            try:
                if warnings:
                    raise ValueError("\n".join(warnings))
                ready = int(window.property("loadedMask") or 0) & (1 << index)
                page = next((item for item in items(window.contentItem())
                             if item.isVisible() and item.objectName() == "page_" + selected), None)
                if not ready or page is None or not page.property("ready"):
                    if time.perf_counter() - before > 12:
                        raise TimeoutError(f"Page {selected} did not load")
                    QTimer.singleShot(16, settle)
                    return
                if phase == "capture":
                    children = list(items(page))
                    if args.smoke_scenario == "expanded":
                        for item in children:
                            if item.metaObject().indexOfProperty("expanded") >= 0:
                                item.setProperty("expanded", True)
                    if args.smoke_scroll:
                        viewport = next(item for item in children if item.objectName() == "pageViewport")
                        if viewport.metaObject().indexOfProperty("contentY") == -1:
                            viewport = viewport.property("contentItem")
                        viewport.setProperty("contentY", max(0, viewport.property("contentHeight") - viewport.height())
                                             * args.smoke_scroll)
                QTimer.singleShot(40, observe)
            except Exception as exc:
                fail(exc)

        def observe():
            try:
                measured = time.perf_counter()
                trace("fixture page configured")
                if phase != "capture":
                    if window.grabWindow().isNull():
                        raise ValueError("Qt returned an empty profile frame")
                    profile.append({"tab": index, "section": selected, "phase": phase,
                                    "callback_ms": (callback-before)*1000, "geometry_ms": (measured-callback)*1000,
                                    "frame_capture_ms": (time.perf_counter()-measured)*1000})
                else:
                    report = inspect_window(window, selected)
                    if args.capture:
                        path = args.capture.with_name(selected + ".png") if args.smoke_all_sections else args.capture
                        path.parent.mkdir(parents=True, exist_ok=True)
                        image = window.grabWindow()
                        if image.isNull() and (screen := window.screen()) is not None:
                            image = screen.grabWindow(int(window.winId()))
                        if image.isNull() or not image.save(str(path)):
                            raise ValueError("Cannot save Qt screenshot")
                        info = {"tab": index, "section": selected, "language": language, "scenario": args.smoke_scenario,
                                "logical_size": [window.width(), window.height()], "image_size": [image.width(), image.height()],
                                "qt_scale_factor": os.getenv("QT_SCALE_FACTOR", "1"), "safe_mode": True, "visual_fixture": True,
                                "scroll_fraction": args.smoke_scroll, "focus_view": args.smoke_focus, "qml_warnings": warnings,
                                "platform": app.platformName(), "windows_application_id": app_id, "source_sha256": digest,
                                "geometry": report}
                        path.with_suffix(".json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
                        trace("capture saved")
                    if report["errors"]:
                        raise ValueError(f"{selected}: " + " | ".join(report["errors"]))
                QTimer.singleShot(0, advance)
            except Exception as exc:
                fail(exc)
        QTimer.singleShot(0, settle)

    QTimer.singleShot(0, advance)
