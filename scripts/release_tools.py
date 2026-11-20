"""Version and binary checks shared by local builds and GitHub Actions."""
import argparse
import base64
import hashlib
import json
import os
import re
import struct
import subprocess
import tempfile
from urllib.parse import urlsplit
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
    import pefile  # Windows dependency of the pinned PyInstaller build tool
    from PyInstaller.archive.readers import CArchiveReader
    from version import VERSION

    toc = CArchiveReader(path).toc
    if (not any(name.lower().startswith("python3") and name.endswith(".dll") for name in toc)
            or not any(entry[-1] == "z" for entry in toc.values())):
        raise ValueError("Expected embedded Python DLL and PYZ in the one-file executable")
    with pefile.PE(str(path), fast_load=True) as pe:
        pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_RESOURCE"]])
        resources = {node.id: node for node in pe.DIRECTORY_ENTRY_RESOURCE.entries}
        strings = [table.entries for group in pe.FileInfo for item in group
                   for table in getattr(item, "StringTable", [])]
        if not any(s.get(b"ProductVersion") == VERSION.encode() and s.get(b"OriginalFilename") == b"Panacea.exe"
                   for s in strings):
            raise ValueError("PE version resource differs from the release identity")
        if not {3, 14} <= resources.keys():  # RT_ICON and RT_GROUP_ICON
            raise ValueError("PE icon resources missing")
        images = set()
        for icon in resources[3].directory.entries:
            for language in icon.directory.entries:
                data = language.data.struct
                images.add(pe.get_data(data.OffsetToData, data.Size))
        ico = (Path(__file__).resolve().parents[1] / "assets/panacea_icon.ico").read_bytes()
        count, = struct.unpack_from("<H", ico, 4)
        for index in range(count):
            size, offset = struct.unpack_from("<II", ico, 6 + 16 * index + 8)
            if ico[offset:offset + size] not in images:
                raise ValueError("PE icon differs from assets/panacea_icon.ico")
    return {"name": path.name, "size": path.stat().st_size, "sha256": binary_sha256(path),
            "one_file": True, "product_version": VERSION, "icon_images": count}


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


SIGN_SECRETS = ("PANACEA_SIGN_PFX_BASE64", "PANACEA_SIGN_PASSWORD", "PANACEA_SIGN_TIMESTAMP_URL")


def optional_sign(path, *, dry_run=False):
    values = [os.environ.get(key, "") for key in SIGN_SECRETS]
    if not any(values):
        print(f"::notice::No signing credentials configured. Keeping {path.name} unsigned.")
        return
    if not all(values):
        raise ValueError("Incomplete PANACEA_SIGN_* configuration")
    encoded, password, timestamp = values
    if urlsplit(timestamp).scheme != "https" or not urlsplit(timestamp).hostname:
        raise ValueError("The RFC 3161 timestamp service must use HTTPS")
    if dry_run:
        print(f"::notice::Validated signing configuration for {path.name} (dry run).")
        return
    if (os.name != "nt" or os.getenv("GITHUB_ACTIONS") != "true"
            or os.getenv("RUNNER_ENVIRONMENT") != "github-hosted"
            or os.getenv("PANACEA_ALLOW_HOSTED_PROBE") != "true"
            or os.getenv("GITHUB_REF") != "refs/heads/main"):
        raise RuntimeError("Signing requires the authorized GitHub-hosted Windows main workflow")
    sdk = Path(os.environ["ProgramFiles(x86)"]) / "Windows Kits/10/bin"
    versions = sorted((p for p in sdk.glob("*/x64/signtool.exe")
                       if re.fullmatch(r"\d+(?:\.\d+)+", p.parents[1].name)),
                      key=lambda p: tuple(map(int, p.parents[1].name.split("."))), reverse=True)
    if not versions:
        raise FileNotFoundError("Windows SDK x64 signtool.exe is missing")
    tool = str(versions[0])
    # Never log the argument vector (it includes the PFX password).
    with tempfile.TemporaryDirectory(dir=os.environ["RUNNER_TEMP"]) as directory:
        pfx = Path(directory) / "signing.pfx"
        pfx.write_bytes(base64.b64decode(encoded, validate=True))
        commands = [
            ["sign", "/fd", "SHA256", "/f", str(pfx), "/p", password,
             "/tr", timestamp, "/td", "SHA256", str(path)],
            ["verify", "/pa", str(path)],
        ]
        for args in commands:
            try:
                result = subprocess.run([tool, *args], check=False, capture_output=True, timeout=180)
            except (OSError, subprocess.TimeoutExpired):
                raise RuntimeError(f"signtool {args[0]} could not finish for {path.name}") from None
            if result.returncode:
                raise RuntimeError(f"signtool {args[0]} failed for {path.name} (exit {result.returncode})")


def finalize_asset(path, *, dry_run=False):
    if path.name not in {"Panacea.exe", "PanaceaSetup.exe"} or not path.is_file():
        raise ValueError("Expected a built Panacea release asset")
    optional_sign(path, dry_run=dry_run)
    if path.name == "Panacea.exe":
        print(json.dumps(verify_package(path)))
        write_checksum(path)
    else:
        from scripts.build_installer import validate_setup
        digest = validate_setup(path)
        path.with_suffix(".exe.sha256").write_text(f"{digest}  {path.name}\n", encoding="ascii")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag")
    parser.add_argument("--exe", type=Path)
    parser.add_argument("--finalize", type=Path, help="Optionally sign, verify and checksum a release asset")
    parser.add_argument("--dry-run-signing", action="store_true")
    args = parser.parse_args()
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from version import VERSION
    if args.tag:
        validate_tag(args.tag, VERSION)
    if args.finalize:
        finalize_asset(args.finalize, dry_run=args.dry_run_signing)
    elif args.exe:
        print(json.dumps(verify_package(args.exe)))
        write_checksum(args.exe)
    else:
        print(VERSION)


if __name__ == "__main__":
    main()
