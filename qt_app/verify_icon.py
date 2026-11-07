"""Verify PE RT_ICON bytes against the original ICO, not merely resource IDs."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct


def verify_payloads(resources, ico: bytes) -> int:
    if len(ico) < 6:
        raise ValueError("Truncated ICO header")
    reserved, kind, count = struct.unpack_from("<HHH", ico)
    if reserved or kind != 1 or count < 1 or len(ico) < 6 + 16 * count:
        raise ValueError("Invalid ICO directory")
    available = set(resources)
    for index in range(count):
        size, offset = struct.unpack_from("<II", ico, 6 + 16 * index + 8)
        if not size or offset < 6 + 16 * count or offset + size > len(ico):
            raise ValueError("Invalid ICO image offset")
        if ico[offset:offset + size] not in available:
            raise ValueError(f"PE does not contain original Panacea icon image {index}")
    return count


def group_payloads(group: bytes, by_id: dict) -> list[bytes]:
    if len(group) < 6:
        raise ValueError("Truncated group icon")
    reserved, kind, count = struct.unpack_from("<HHH", group)
    if reserved or kind != 1 or count < 1 or len(group) < 6 + 14 * count:
        raise ValueError("Invalid group icon")
    images = []
    for index in range(count):
        identifier = struct.unpack_from("<H", group, 6 + 14 * index + 12)[0]
        if identifier not in by_id:
            raise ValueError("Group icon references a missing image")
        images.extend(by_id[identifier])
    return images


def verify(executable: Path, original: Path) -> dict:
    import pefile
    with pefile.PE(str(executable)) as pe:
        entries = pe.DIRECTORY_ENTRY_RESOURCE.entries
        types = {entry.id for entry in entries}
        if not {3, 14}.issubset(types):
            raise ValueError("PE has no RT_ICON / RT_GROUP_ICON")
        by_id = {}
        groups = []
        for entry in entries:
            if entry.id == 3:
                for icon in entry.directory.entries:
                    by_id[icon.id] = []
                    for language in icon.directory.entries:
                        data = language.data.struct
                        by_id[icon.id].append(pe.get_data(data.OffsetToData, data.Size))
            if entry.id == 14:
                for group in entry.directory.entries:
                    for language in group.directory.entries:
                        data = language.data.struct
                        groups.append(pe.get_data(data.OffsetToData, data.Size))
        if not groups:
            raise ValueError("No default icon group")
        count = verify_payloads(group_payloads(groups[0], by_id), original.read_bytes())
    return {"original_icon_images_verified": count,
            "default_icon_group_verified": True,
            "ico_sha256": hashlib.sha256(original.read_bytes()).hexdigest(),
            "exe_sha256": hashlib.sha256(executable.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("--icon", type=Path, default=Path(__file__).resolve().parents[1] / "assets/panacea_icon.ico")
    args = parser.parse_args()
    print(json.dumps(verify(args.executable, args.icon)))


if __name__ == "__main__":
    main()
