import pytest


def test_tag_must_match_authoritative_version():
    from scripts.release_tools import validate_tag
    assert validate_tag("v1.49.0", "1.49.0") == "1.49.0"
    with pytest.raises(ValueError):
        validate_tag("v1.48", "1.49.0")
    with pytest.raises(ValueError):
        validate_tag("v1.49.0rc1", "1.49.0")


def test_package_rejects_non_pe_before_creating_checksum(tmp_path):
    from scripts.release_tools import verify_package
    exe = tmp_path / "Panacea.exe"
    exe.write_bytes(b"not a Windows executable")
    with pytest.raises(ValueError):
        verify_package(exe)
    assert not (tmp_path / "Panacea.exe.sha256").exists()


def test_checksum_is_exact_binary_digest(tmp_path):
    from scripts.release_tools import write_checksum
    exe = tmp_path / "Panacea.exe"
    exe.write_bytes(b"fixture executable bytes")
    checksum = write_checksum(exe)
    assert checksum.read_text().strip() == (
        "f67bea1e29bf7fa00d04549495d9d5d3bf5fc92aa36a59fc471f792d6c8b153c  Panacea.exe"
    )


def test_package_requires_exact_asset_name(tmp_path):
    from scripts.release_tools import write_checksum
    exe = tmp_path / "Other.exe"
    exe.write_bytes(b"bytes")
    with pytest.raises(ValueError):
        write_checksum(exe)


def test_resource_encodes_numeric_version_and_filename():
    from scripts.release_tools import version_resource
    resource = version_resource("1.49.0")
    assert "filevers=(1, 49, 0, 0)" in resource
    assert "Panacea.exe" in resource


@pytest.mark.parametrize('tool_version', ['6.19.0', '6.22.0', '6.22.2'])
def test_build_rejects_old_or_incompatible_privileged_bootloader(tool_version):
    from scripts.release_tools import validate_build_toolchain
    with pytest.raises(ValueError):
        validate_build_toolchain(tool_version)


def test_build_accepts_patched_compatible_bootloader():
    from scripts.release_tools import validate_build_toolchain
    assert validate_build_toolchain('6.22.3') == '6.22.3'
