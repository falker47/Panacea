"""Capture all desktop sections using the isolated Qt smoke entry point."""
import argparse
from itertools import product
import json
import os
from pathlib import Path
import subprocess
import sys

from PySide6.QtGui import QImage

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qt_app.catalog import SECTIONS

SIZES = ((760, 480), (1366, 768), (1920, 1080))
SCALES = (100, 125, 150)
LANGUAGES = ("it", "en")


def cases():
    for size, scale, language in product(SIZES, SCALES, LANGUAGES):
        # 760x480 is the minimum client size in device-independent pixels.
        logical = size if size == SIZES[0] else tuple(round(n * 100 / scale) for n in size)
        yield size, scale, language, logical


def verify_case(directory, logical, scale, language):
    rows = []
    for section in SECTIONS:
        path = directory / (section + ".png")
        image = QImage(str(path))
        meta = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
        expected = [round(n * scale / 100) for n in logical]
        if (image.isNull() or meta["logical_size"] != list(logical) or meta["language"] != language
                or meta["section"] != section or meta["qml_warnings"] or meta["geometry"]["errors"]
                or not meta["visual_fixture"] or not meta["safe_mode"] or not meta["geometry"]["controls"]
                or meta["image_size"] != [image.width(), image.height()]
                or any(abs(actual - wanted) > 1 for actual, wanted in zip(meta["image_size"], expected))):
            raise ValueError(f"Invalid capture evidence: {path}")
        rows.append({"section": section, "image": f"{directory.name}/{path.name}",
                     "source_sha256": meta["source_sha256"], "pixels": meta["image_size"]})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = []
    for (w, h), scale, language, logical in cases():
        directory = args.output / f"{w}x{h}-{scale}-{language}"
        subprocess.run([sys.executable, str(Path(__file__).with_name("main.py")), "--smoke-test",
                        "--smoke-all-sections", "--smoke-language", language, "--smoke-width", str(logical[0]),
                        "--smoke-height", str(logical[1]), "--capture", str(directory / "home.png")],
                       env=dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software",
                                QT_SCALE_FACTOR=str(scale / 100)), timeout=90, check=True)
        manifest.extend(verify_case(directory, logical, scale, language))
    if len({row["source_sha256"] for row in manifest}) != 1:
        raise ValueError("Captures came from different shell revisions")
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
