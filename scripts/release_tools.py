"""Version and binary checks shared by local builds and GitHub Actions."""
import argparse
import hashlib
import json
import struct
from pathlib import Path

from packaging.version import Version


def validate_build_toolchain(tool_version):
    parsed = Version(tool_version)
    if parsed < Version('6.22.3') or parsed.is_prerelease:
        raise ValueError('Build requires patched compatible PyInstaller 6.22.3 or newer. Install requirements-dev.txt in an isolated environment.')
    return str(parsed)


def validate_tag(tag, version):
    if tag != f"v{version}" or Version(version).is_prerelease or Version(version).is_devrelease:
        raise ValueError(f"Expected exact stable tag v{version}; received {tag!r}")
    return version


def verify_package(path):
    path = Path(path)
    if path.name != "Panacea.exe" or not path.is_file() or path.stat().st_size < 1_000_000:
        raise ValueError("Expected a plausibly sized Panacea.exe")
    with path.open("rb") as binary:
        if binary.read(2) != b"MZ":
            raise ValueError("Missing Windows executable header")
        binary.seek(0x3C)
        offset = struct.unpack("<I", binary.read(4))[0]
        if offset > path.stat().st_size - 4:
            raise ValueError("Invalid PE offset")
        binary.seek(offset)
        if binary.read(4) != b"PE\0\0":
            raise ValueError("Invalid Windows PE signature")
    return {"name": path.name, "size": path.stat().st_size, "sha256": binary_sha256(path)}


def binary_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as binary:
        for chunk in iter(lambda: binary.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_checksum(path):
    path = Path(path)
    if path.name != "Panacea.exe":
        raise ValueError("The release binary must be named Panacea.exe")
    checksum = path.with_name("Panacea.exe.sha256")
    checksum.write_text(f"{binary_sha256(path)}  Panacea.exe\n", encoding="ascii")
    return checksum


def version_resource(version):
    parsed = Version(version)
    if parsed.is_prerelease or len(parsed.release) > 4 or any(n > 65535 for n in parsed.release):
        raise ValueError("Unsupported Windows version")
    numbers = parsed.release + (0,) * (4 - len(parsed.release))
    numeric = ", ".join(str(n) for n in numbers)
    return f'''VSVersionInfo(
  ffi=FixedFileInfo(filevers=({numeric}), prodvers=({numeric}), mask=0x3f,
    flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('040904B0', [
    StringStruct('CompanyName', 'Maurizio Falconi'),
    StringStruct('FileDescription', 'Panacea Windows Maintenance'),
    StringStruct('FileVersion', '{version}'),
    StringStruct('InternalName', 'Panacea'),
    StringStruct('OriginalFilename', 'Panacea.exe'),
    StringStruct('ProductName', 'Panacea'),
    StringStruct('ProductVersion', '{version}')
  ])]), VarFileInfo([VarStruct('Translation', [1033, 1200])])])
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag")
    parser.add_argument("--exe", type=Path)
    args = parser.parse_args()
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from version import VERSION
    if args.tag:
        validate_tag(args.tag, VERSION)
    if args.exe:
        print(json.dumps(verify_package(args.exe)))
        write_checksum(args.exe)
    else:
        print(VERSION)


if __name__ == "__main__":
    main()
