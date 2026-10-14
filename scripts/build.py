"""Build and validate the exact Windows release asset without rewriting the spec."""
import argparse
import json
import importlib.metadata
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.release_tools import verify_package, write_checksum, validate_build_toolchain
from version import VERSION


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    validate_build_toolchain(importlib.metadata.version('pyinstaller'))
    output = args.output.resolve()
    notes = ROOT / 'docs' / 'releases' / f'{VERSION}.md'
    if not notes.is_file():
        raise FileNotFoundError(f'Missing release notes for {VERSION}: {notes}')
    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--distpath", str(output), "--workpath", str(ROOT / "build" / "pyinstaller"),
        str(ROOT / "Panacea.spec"),
    ], cwd=ROOT, check=True)
    exe = output / "Panacea.exe"
    metadata = verify_package(exe)
    write_checksum(exe)
    (output / 'release-notes.md').write_text(notes.read_text(encoding='utf-8'), encoding='utf-8')
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
