"""Capture eight current-source views with inert fixtures; retain honest A/B evidence.

Scaling is simulated in each toolkit. This never changes Windows display settings,
executes maintenance, certifies visual parity, or resizes a mismatched image pair.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from PIL import Image, ImageChops, ImageDraw, ImageStat

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qt_app.visual_review import current_reference_is_fresh  # noqa: E402

VIEWS = (("dashboard", 0), ("cleaning", 1), ("apps", 1), ("tools", 2),
         ("disk", 2), ("turbo", 3), ("startup", 3), ("resurrect", 4))
SIZES = ((976, 672), (1366, 768), (1920, 1080))


def compare_images(legacy: Path, qt: Path, target: Path) -> dict:
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(legacy) as original, Image.open(qt) as candidate:
        a, b = original.convert("RGB"), candidate.convert("RGB")
    same = a.size == b.size
    difference = ImageChops.difference(a, b) if same else None
    error = round(sum(ImageStat.Stat(difference).mean) / 3, 3) if same else None
    if difference is not None:
        difference.save(target.with_name(target.name + "-diff.png"))
    sheet = Image.new("RGB", (a.width + b.width + 36, max(a.height, b.height) + 42), "#0b1525")
    draw = ImageDraw.Draw(sheet)
    draw.text((12, 9), f"CURRENT V2 - {a.width} x {a.height}", fill="#e4c579")
    draw.text((a.width + 24, 9), f"QT QA - {b.width} x {b.height}", fill="#e4c579")
    sheet.paste(a, (12, 30))
    sheet.paste(b, (a.width + 24, 30))
    sheet.save(target.with_suffix(".jpg"), quality=90)
    return {"status": "diagnostic_only_not_approved", "same_dimensions": same,
            "legacy_size": list(a.size), "qt_size": list(b.size),
            "mean_rgb_difference": error,
            "legacy_sha256": hashlib.sha256(legacy.read_bytes()).hexdigest(),
            "qt_sha256": hashlib.sha256(qt.read_bytes()).hexdigest(),
            "legacy": str(legacy), "qt": str(qt), "ab": str(target.with_suffix(".jpg"))}


def cases(quick=False):
    for width, height in SIZES[:1] if quick else SIZES:
        for scale in (1,) if quick else (1, 1.25, 1.5):
            for language in ("it", "en"):
                yield width, height, scale, language


def capture(output: Path, mode: str, quick=False, reuse_matching=False):
    for width, height, scale, language in cases(quick):
        case = output / f"{width}x{height}-{round(scale * 100)}-{language}"
        if mode in ("all", "legacy"):
            command = [sys.executable, str(ROOT / "scripts/visual_check.py"), "--smoke-fixture",
                       "--focus-subviews", "--language", language, "--width", str(width),
                       "--height", str(height), "--scale", str(scale), "--settle-ms", "800",
                       "--output", str(case / "legacy")]
            subprocess.run(command, cwd=ROOT, check=True, timeout=120)
            print(f"legacy {case.name}: captured", flush=True)
        if mode in ("all", "qt"):
            actual_width, actual_height = width, height
            reference = case / "legacy/observations.json"
            if reference.exists():
                observed = json.loads(reference.read_text(encoding="utf-8"))
                actual_width, actual_height = observed["views"][0]["pixels"]
            logical_width = max(760, round(actual_width / scale))
            logical_height = max(480, round(actual_height / scale))
            env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software",
                       QT_SCALE_FACTOR=str(scale), PYTHONUTF8="1")
            for view, tab in VIEWS:
                target = case / "qt" / f"{view}.png"
                if reuse_matching and target.exists() and target.with_suffix(".json").exists():
                    metadata = json.loads(target.with_suffix(".json").read_text(encoding="utf-8"))
                    expected = {name: hashlib.sha256((ROOT / "qt_app" / name).read_bytes()).hexdigest()
                                for name in ("Main.qml", "ParityPage.qml")}
                    focus = None if view in ("dashboard", "resurrect") else view
                    if (metadata.get("source_sha256") == expected and metadata.get("tab") == tab
                            and metadata.get("language") == language and metadata.get("visual_fixture") is True
                            and metadata.get("logical_size") == [logical_width, logical_height]
                            and metadata.get("qt_scale_factor") == str(scale)
                            and metadata.get("focus_view") == focus and metadata.get("scenario") == "default"
                            and metadata.get("qml_warnings") == []):
                        continue
                command = [sys.executable, str(ROOT / "qt_app/main.py"), "--smoke-test",
                           "--smoke-tab", str(tab), "--smoke-language", language,
                           "--smoke-width", str(logical_width), "--smoke-height", str(logical_height),
                           "--capture", str(target)]
                if view not in ("dashboard", "resurrect"):
                    command.extend(("--smoke-focus", view))
                subprocess.run(command, cwd=ROOT, env=env, check=True, timeout=45)
            print(f"Qt {case.name}: eight views captured", flush=True)


def report(output: Path, quick=False):
    records = []
    for width, height, scale, language in cases(quick):
        case = output / f"{width}x{height}-{round(scale * 100)}-{language}"
        reference = case / "legacy/observations.json"
        if not current_reference_is_fresh(reference, ROOT):
            raise ValueError(f"Reference does not match current V2: {reference}")
        legacy_meta = json.loads(reference.read_text(encoding="utf-8"))
        if legacy_meta.get("callback_errors") or not legacy_meta.get("visual_fixture"):
            raise ValueError(f"Invalid legacy fixture: {case.name}")
        for view, tab in VIEWS:
            qt = case / "qt" / f"{view}.png"
            metadata = json.loads(qt.with_suffix(".json").read_text(encoding="utf-8"))
            if metadata.get("tab") != tab or metadata.get("language") != language or metadata.get("qml_warnings"):
                raise ValueError(f"Invalid Qt fixture: {qt}")
            expected = {name: hashlib.sha256((ROOT / "qt_app" / name).read_bytes()).hexdigest()
                        for name in ("Main.qml", "ParityPage.qml")}
            if metadata.get("source_sha256") != expected:
                raise ValueError(f"Qt evidence is from a different QML revision: {qt}")
            result = compare_images(case / "legacy" / f"{view}.png", qt, case / "comparison" / view)
            result.update(view=view, requested_viewport=[width, height], scale=scale, language=language,
                          native_legacy_dpi=legacy_meta.get("native_window_dpi"),
                          qt_minimum_clamped=width / scale < 760 or height / scale < 480)
            result["dimension_discrepancy"] = ("none" if result["same_dimensions"] else
                "qt_dpr_rounding_one_pixel" if max(abs(a - b) for a, b in zip(result["legacy_size"], result["qt_size"])) <= 1
                else "minimum_logical_window_clamped")
            records.append(result)
    result = {"status": "comparison_generated_not_approved", "views": [v for v, _ in VIEWS],
              "limitations": ["Tk widget and QT_SCALE_FACTOR simulation; physical DPI not changed",
                              "976x672 at simulated 150% exceeds the Qt minimum logical window; unmatched pairs are retained",
                              "RGB difference is diagnostic; font rasterization differs",
                              "Inert synthetic data; no maintenance, UAC, update installation or rollback exercised"],
              "comparisons": records}
    (output / "eight-view-report.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"comparisons": len(records), "matched_dimensions": sum(r["same_dimensions"] for r in records)}), flush=True)
    return result


def capture_states(output: Path):
    cases = [(view, tab, "unknown") for view, tab in VIEWS if view in ("dashboard", "cleaning", "tools", "turbo", "resurrect")]
    cases += [("cleaning", 1, state) for state in ("expanded", "running", "completed", "partial", "failed", "cancelled")]
    cases += [(view, 2, state) for view in ("tools", "disk") for state in ("expanded", "running", "completed")]
    cases += [("resurrect", 4, state) for state in ("expanded", "running", "completed", "partial", "failed", "cancelled")]
    cases += [("dashboard", 0, state) for state in ("long-text", "confirmation")]
    records = []
    for language in ("it", "en"):
        for view, tab, state in cases:
            target = output / "states" / f"{view}-{state}-{language}.png"
            command = [sys.executable, str(ROOT / "qt_app/main.py"), "--smoke-test", "--smoke-tab", str(tab),
                       "--smoke-language", language, "--smoke-scenario", state, "--capture", str(target),
                       "--smoke-width", "760" if state in ("long-text", "confirmation") else "976",
                       "--smoke-height", "480" if state in ("long-text", "confirmation") else "672"]
            if view in ("cleaning", "tools", "disk", "turbo"):
                command.extend(("--smoke-focus", view))
            subprocess.run(command, cwd=ROOT, check=True, timeout=45,
                           env=dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software", QT_SCALE_FACTOR="1", PYTHONUTF8="1"))
            records.append({"view": view, "scenario": state, "language": language, "image": str(target)})
    (output / "state-report.json").write_text(json.dumps({"fixture_only": True, "captures": records}, indent=2) + "\n", encoding="utf-8")
    print(f"{len(records)} inert state captures completed", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=("all", "legacy", "qt", "report", "states"), default="all")
    parser.add_argument("--quick", action="store_true", help="976x672 at 100%, both languages")
    parser.add_argument("--reuse-matching", action="store_true", help="Reuse only Qt captures matching current QML and viewport metadata")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    capture(args.output, args.mode, args.quick, args.reuse_matching)
    if args.mode in ("all", "states"):
        capture_states(args.output)
    if args.mode in ("all", "report"):
        report(args.output, args.quick)


if __name__ == "__main__":
    main()
