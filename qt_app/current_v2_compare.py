"""Produce a same-size A/B review of the CURRENT Panacea V2 and Qt windows.

This is diagnostic evidence, never a declaration of pixel or functional parity.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageOps, ImageStat
from qt_app.visual_review import current_reference_is_fresh


SCREENS = ("dashboard", "cleaning", "tools", "turbo", "resurrect")


def compare(captures: Path, stable: Path, output: Path) -> dict:
    project = Path(__file__).resolve().parents[1]
    if not current_reference_is_fresh(stable / "observations.json", project):
        raise ValueError("Stable visual reference is not from the current V2 source")
    with (stable / "observations.json").open(encoding="utf-8") as handle:
        original_meta = json.load(handle)
    observed = {str(entry["section"]).lower(): tuple(entry["pixels"])
                for entry in original_meta["views"]}
    records = []
    tiles = []
    for index, screen in enumerate(SCREENS):
        stable_path = stable / f"{screen}.png"
        qt_path = captures / f"matched-v2-tab{index}-en.png"
        qt_meta_path = qt_path.with_suffix(".json")
        meta = json.loads(qt_meta_path.read_text(encoding="utf-8"))
        if meta.get("tab") != index or meta.get("safe_mode") is not True:
            raise ValueError(f"Qt screenshot isn't the isolated QA group: {screen}")
        if meta.get("language") != "en":
            raise ValueError(f"Language mismatch on {screen}")
        with Image.open(stable_path) as stable_img, Image.open(qt_path) as qt_img:
            reference = stable_img.convert("RGB")
            current = qt_img.convert("RGB")
            if reference.size != current.size or reference.size != observed[screen]:
                raise ValueError(f"Cannot compare mismatched window sizes for {screen}: "
                                 f"{reference.size} vs {current.size}")
            rgb_error = round(sum(ImageStat.Stat(ImageChops.difference(reference, current)).mean) / 3, 3)
            records.append({
                "screen": screen, "size": list(reference.size),
                "stable_sha256": hashlib.sha256(stable_path.read_bytes()).hexdigest(),
                "qt_sha256": hashlib.sha256(qt_path.read_bytes()).hexdigest(),
                "mean_rgb_difference_0_255": rgb_error,
                "interpretation": "diagnostic_only_no_visual_or_functional_pass",
            })
            tiles.append((screen, reference.copy(), current.copy()))
    tw, th = 610, 410
    margin, heading = 20, 28
    contact = Image.new("RGB", (tw * 2 + margin * 3, (th + heading + margin) * len(tiles) + margin), "#0b1525")
    painter = ImageDraw.Draw(contact)
    for index, (screen, a, b) in enumerate(tiles):
        y = margin + index * (th + heading + margin)
        painter.text((margin, y), screen.upper() + "  -  V2 CURRENT", fill="#e4c579")
        painter.text((tw + margin * 2, y), screen.upper() + "  -  QT QA", fill="#e4c579")
        contact.paste(ImageOps.fit(a, (tw, th)), (margin, y + heading))
        contact.paste(ImageOps.fit(b, (tw, th)), (tw + margin * 2, y + heading))
    output.mkdir(parents=True, exist_ok=True)
    contact.save(output / "visual-current-v2-contact-sheet.jpg", quality=90)
    result = {
        "status": "diagnostic_only_not_approved",
        "matched_current_source": True,
        "windows_display": original_meta.get("screen_pixels"),
        "scaling": "native Windows CTk 100% vs Qt offscreen 100%",
        "note": "Same physical screenshot sizes, no metric/locale fixture equivalence or user-verified functionality",
        "comparisons": records,
    }
    (output / "visual-current-v2-report.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--captures", type=Path, required=True)
    parser.add_argument("--stable", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps({"comparisons": len(compare(args.captures, args.stable, args.out)["comparisons"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
