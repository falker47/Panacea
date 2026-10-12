"""Equivalent read-only startup measurements; no system maintenance."""
import argparse
import json
import platform
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=ROOT)
    parser.add_argument("--label", required=True)
    parser.add_argument("--samples", type=int, default=5)
    args = parser.parse_args()
    if not args.label.replace("-", "").isalnum() or args.samples < 5:
        parser.error("Use an alphanumeric label and at least five samples")
    results = []
    for index in range(args.samples):
        output = ROOT / "build" / "validation" / f"{args.label}-sample-{index}.json"
        subprocess.run([
            sys.executable, str(ROOT / "scripts" / "gui_probe.py"),
            "--source", str(args.source.resolve()), "--output", str(output), "--duration", "5",
        ], cwd=ROOT, check=True, timeout=40, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        results.append(json.loads(output.read_text(encoding="utf-8")))
    latencies = [x for sample in results for x in sample["event_loop_delay_ms"]]
    metric = [s["first_metric_seconds"] for s in results if s["first_metric_seconds"] is not None]
    summary = {
        "environment": platform.platform(), "python": platform.python_version(),
        "method": "Five fresh source processes; direct PanaceaApp import/constructor plus event-loop readiness. Excludes main UAC/splash and PyInstaller extraction. Host read-only monitoring remains enabled; duration five seconds each.",
        "samples": results,
        "median_ready_seconds": statistics.median(s["ready_seconds"] for s in results),
        "median_first_metric_seconds": statistics.median(metric) if metric else None,
        "event_loop_delay_p95_ms": sorted(latencies)[int(len(latencies) * 0.95)] if latencies else None,
        "event_loop_delay_max_ms": max(latencies) if latencies else None,
    }
    path = ROOT / "docs" / "validation" / f"{args.label}-startup.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "samples"}, indent=2))


if __name__ == "__main__":
    main()
