"""Diagnostic visual comparison for five Qt groups at six V2 viewport/DPI cases.

This is NOT a pixel-parity gate: V2 used Tk, Qt has different text rendering,
and paired screens were composed differently. The contact sheet and metrics
make remaining discrepancies reviewable rather than asserting equivalence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageStat, ImageOps, ImageDraw


SCREENS = ("dashboard", "cleaning", "tools", "turbo", "resurrect")
SCALES = (100, 125, 150)
SIZES = ((1366, 768), (1920, 1080))


def inspect(root: Path, baseline: Path, target: Path) -> dict:
    """Read captures and their corresponding committed stable reference."""
    records = []
    tiles = []
    for width, height in SIZES:
        for scale in SCALES:
            for tab, screen in enumerate(SCREENS):
                key = f"{width}x{height}-{scale}"
                candidate = root / f"matrix-{key}-tab{tab}-it.png"
                original = baseline / f"v2-final-{key}" / f"{screen}.png"
                meta_file = candidate.with_suffix(".json")
                if not candidate.is_file() or not original.is_file() or not meta_file.is_file():
                    raise FileNotFoundError(f"Missing screenshot pair or metadata: {key} / {screen}")
                metadata = json.loads(meta_file.read_text(encoding="utf-8"))
                if metadata.get("tab") != tab or metadata.get("safe_mode") is not True:
                    raise ValueError(f"Invalid QA capture metadata for {candidate.name}")
                with Image.open(candidate) as read_candidate, Image.open(original) as read_original:
                    newer = read_candidate.convert("RGB")
                    older = read_original.convert("RGB")
                    if min(newer.size) < 400 or min(older.size) < 400:
                        raise ValueError(f"Suspiciously small screenshot: {candidate.name}")
                    resized = newer.resize(older.size, Image.Resampling.BILINEAR)
                    deviation = ImageStat.Stat(ImageChops.difference(older, resized)).mean
                    mean_absolute_error = round(sum(deviation) / 3, 3)
                    records.append({
                        "viewport": [width, height],
                        "scale_percent": scale,
                        "group": screen,
                        "qt_image": str(candidate),
                        "stable_image": str(original),
                        "qt_size": list(newer.size),
                        "stable_size": list(older.size),
                        "qt_sha256": hashlib.sha256(candidate.read_bytes()).hexdigest(),
                        "stable_sha256": hashlib.sha256(original.read_bytes()).hexdigest(),
                        "mean_rgb_difference_0_255": mean_absolute_error,
                        "interpretation": "diagnostic_only_not_pixel_parity",
                    })
                    if key == "1366x768-100":
                        tiles.append((screen, older.copy(), newer.copy()))
    # A compact, reviewable sheet: for every primary group stable V2 on left
    # and the Qt screenshot on right; no misleading automated PASS label.
    if len(tiles) != len(SCREENS):
        raise AssertionError("Missing a primary comparison for contact sheet")
    tile_size = (610, 343)
    margin = 20
    heading_height = 30
    sheet = Image.new(
        "RGB",
        (tile_size[0] * 2 + margin * 3,
         (tile_size[1] + heading_height + margin) * len(tiles) + margin),
        "#0b1525",
    )
    draw = ImageDraw.Draw(sheet)
    for i, (screen, original, candidate) in enumerate(tiles):
        y = margin + i * (tile_size[1] + heading_height + margin)
        draw.text((margin, y + 2), screen.upper() + "  —  V2 STABLE", fill="#e4c579")
        draw.text((tile_size[0] + margin * 2, y + 2),
                  screen.upper() + "  —  QT QA", fill="#e4c579")
        sheet.paste(ImageOps.fit(original, tile_size), (margin, y + heading_height))
        sheet.paste(ImageOps.fit(candidate, tile_size),
                    (tile_size[0] + margin * 2, y + heading_height))
    target.mkdir(parents=True, exist_ok=True)
    sheet.save(target / "visual-parity-contact-sheet.jpg", quality=88)
    report = {
        "status": "comparison_generated_not_approved",
        "method": "paired screenshots, dimensions, SHA-256, and mean RGB absolute difference",
        "limitations": [
            "Qt and Tk font rasterization differs",
            "five Qt groups show paired subviews vs V2 captures focused on an individual subview",
            "stable captures use V2 fixture data; Qt safe smoke does not simulate maintenance",
            "color difference is not a functional or accessibility certification",
        ],
        "comparisons": records,
    }
    (target / "visual-parity-matrix.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return {"screenshots_compared": len(records), "contact_sheet": str(target / "visual-parity-contact-sheet.jpg")}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--captures", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(inspect(args.captures, args.baseline, args.out)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
