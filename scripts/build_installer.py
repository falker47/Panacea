"""Build PanaceaSetup.exe from an already verified release executable.

Inno Setup is a build-time dependency only. The user-facing installer requests
administrator privileges and defaults to Program Files. Existing portable V1
copies are never touched.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from modules.updater import parse_checksum, verify_file  # noqa: E402
from scripts.release_tools import binary_sha256  # noqa: E402
from version import VERSION  # noqa: E402

SPEC = ROOT / "packaging" / "Panacea.iss"


def locate_compiler(explicit=None):
    candidates = [explicit, os.environ.get("PANACEA_ISCC"), shutil.which("ISCC.exe")]
    for variable in ("ProgramFiles(x86)", "ProgramFiles"):
        program_files = os.environ.get(variable)
        if program_files:
            candidates.append(str(Path(program_files) / "Inno Setup 6" / "ISCC.exe"))
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(Path(candidate).resolve())
    raise FileNotFoundError("Inno Setup 6 ISCC.exe is required to build PanaceaSetup.exe.")


def validate_portable(exe, checksum):
    exe, checksum = Path(exe).resolve(), Path(checksum).resolve()
    if exe.name != "Panacea.exe" or checksum.name != "Panacea.exe.sha256":
        raise ValueError("Installer inputs must be the exact Panacea.exe and Panacea.exe.sha256 files.")
    expected = parse_checksum(checksum.read_bytes())
    verify_file(exe, expected, exe.stat().st_size)
    return exe, expected


def validate_setup(path):
    """Verify Inno output is a nontrivial PE before emitting a checksum."""
    path = Path(path)
    size = path.stat().st_size
    if path.name != "PanaceaSetup.exe" or size < 1_000_000:
        raise ValueError("Inno Setup did not produce the expected installer.")
    with path.open("rb") as stream:
        if stream.read(2) != b"MZ":
            raise ValueError("Installer DOS header is missing.")
        stream.seek(60)
        offset = struct.unpack("<I", stream.read(4))[0]
        if offset < 64 or offset + 4 > size:
            raise ValueError("Installer PE header offset is invalid.")
        stream.seek(offset)
        if stream.read(4) != b"PE\0\0":
            raise ValueError("Installer PE header is missing.")
    return binary_sha256(path)


def build_installer(exe, checksum, out, iscc=None):
    exe, _ = validate_portable(exe, checksum)
    compiler = locate_compiler(iscc)
    output = Path(out).resolve()
    output.mkdir(parents=True, exist_ok=True)
    icon = (ROOT / "assets" / "panacea_icon.ico").resolve(strict=True)
    subprocess.run(
        [compiler, "/Qp", f"/DPanaceaVersion={VERSION}",
         f"/DPanaceaExePath={exe}", f"/DPanaceaIconPath={icon}",
         f"/DPanaceaOutputDir={output}", str(SPEC)],
        cwd=ROOT, check=True, timeout=240)
    installer = output / "PanaceaSetup.exe"
    digest = validate_setup(installer)
    (output / "PanaceaSetup.exe.sha256").write_text(
        f"{digest}  PanaceaSetup.exe\n", encoding="ascii")
    return installer, digest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", type=Path, default=ROOT / "dist" / "Panacea.exe")
    parser.add_argument("--checksum", type=Path, default=ROOT / "dist" / "Panacea.exe.sha256")
    parser.add_argument("--out", type=Path, default=ROOT / "dist")
    parser.add_argument("--iscc", help="Explicit path to the Inno Setup compiler")
    args = parser.parse_args()
    installer, digest = build_installer(args.exe, args.checksum, args.out, args.iscc)
    print(f"Panacea {VERSION} installer: {installer}, SHA-256: {digest}")


if __name__ == "__main__":
    main()
