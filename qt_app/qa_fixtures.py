"""Deterministic, inert presentation fixtures, imported only by --smoke-test."""
from __future__ import annotations


class VisualMaintenance:
    def prepare(self, action, drive):
        raise RuntimeError("Visual fixture: Windows operations are disabled")

    def execute(self, *args, **kwargs):
        raise RuntimeError("Visual fixture cannot execute maintenance")

    def reject(self):
        pass

    def cancel(self):
        pass

    def close(self):
        pass


class VisualReads:
    def __init__(self, snapshots):
        self.snapshots = snapshots

    def collect(self, action):
        return dict(self.snapshots.get(action, {}))

    def close(self):
        pass


def apply_scenario(metrics, reader, maintenance, scenario, group, language):
    reader._results.update({
        "windows_updates": {"recommended": 0, "optional": 0, "verified": True, "status": "Up to date"},
        "drives": {"drives": [{"letter": "C:", "available": True, "total_bytes": 256 * 1024**3,
                                 "free_bytes": 6.4 * 1024**3, "used_percent": 97.5, "error": ""}]},
        "turbo_status": {"states": {"power": True, "visual": False, "sysmain": False,
                                      "wsearch": False, "spooler": False},
                         "master": False, "saved_count": 2, "restore_available": True},
        "guard_status": {"blocked": False, "message": ""},
    })
    reader._drives = ["C:"]
    reader._service = VisualReads(reader._results)
    if scenario == "unknown":
        metrics._values = {"cpu": "—", "ram": "—", "disk": "—", "details": {}}
        metrics._history = {"cpu": [], "ram": [], "disk": []}
        reader._results = {"windows_updates": {"verified": False}, "turbo_status": {}}
        reader._drives = []
    if scenario == "long-text":
        reader._results["hardware"].update({
            "os": "Windows 11 Enterprise · Long organization-managed system description",
            "cpu_name": "AMD Ryzen 7 · " + "Extended processor information " * 3,
            "ram_info": "DDR5 · " + "Detailed memory module information " * 3,
            "disk_model": "System SSD · " + "Extended storage model information " * 3,
        })
    if scenario in ("running", "completed", "partial", "failed", "cancelled"):
        maintenance._last_action = {0: "restore_point", 1: "quick_cleanup", 2: "sfc",
                                    3: "power_on", 4: "resurrection"}[group]
        maintenance._result_status = scenario
        maintenance._busy = scenario == "running"
        maintenance._progress_total = 10 if group == 4 else 3
        count = {"running": 2, "completed": maintenance._progress_total, "partial": maintenance._progress_total,
                 "failed": 1, "cancelled": 2}[scenario]
        maintenance._progress_done = count
        maintenance._steps = [{"success": not (scenario in ("failed", "partial") and i == count - 1),
                               "message": "SIMULATED RESULTS · No Windows operation executed"}
                              for i in range(count)]
        maintenance._output = "SIMULATED RESULTS · " + scenario + "\n" + "\n".join(
            f"{i + 1}/{maintenance._progress_total}: UI fixture only" for i in range(count))
        maintenance._remember_result()
        scope = {0: "tools", 1: "cleaning", 2: "tools", 3: "turbo", 4: "resurrect"}[group]
        maintenance._section_logs[scope] = maintenance._output
    if scenario == "confirmation":
        maintenance._pending = "visual-fixture-invalid-nonce"
        maintenance._details = ("Conferma simulata · nessuna operazione Windows\n" if language == "it" else
                                "Simulated confirmation · no Windows operation\n") + (
            "Eliminazione permanente. Salva il lavoro; l'annullamento avviene fra le fasi. "
            if language == "it" else "Permanent deletion. Save work; cancellation occurs between steps. ") * 12
    reader._service = VisualReads(reader._results)
