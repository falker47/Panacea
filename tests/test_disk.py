import ctypes
import shutil
from types import SimpleNamespace

import pytest

import modules.disk as disk


@pytest.fixture
def subject(monkeypatch):
    monkeypatch.setattr(disk, 'Logger', lambda: SimpleNamespace(log=lambda *args: None))
    return disk.DiskOptimizer()


def test_drive_inventory_excludes_network_optical_and_removable_devices(subject, monkeypatch):
    # A logical-drive bitmask advertises C:, D:, E:, Z:. Only C: is fixed.
    kernel = SimpleNamespace(GetLogicalDrives=lambda: (1 << 2) | (1 << 3) | (1 << 4) | (1 << 25),
                             GetDriveTypeW=lambda root: {'C:\\': 3, 'D:\\': 5, 'E:\\': 2, 'Z:\\': 4}[root])
    monkeypatch.setattr(ctypes, 'windll', SimpleNamespace(kernel32=kernel))
    monkeypatch.setattr(disk.os.path, 'exists', lambda root: root in ('C:\\', 'D:\\', 'E:\\', 'Z:\\'))
    assert subject.get_drives() == ['C:']


def test_drive_inventory_failure_is_not_an_empty_success(subject, monkeypatch):
    monkeypatch.setattr(ctypes, 'windll', SimpleNamespace(kernel32=SimpleNamespace(GetLogicalDrives=lambda: 0)))
    with pytest.raises(OSError):
        subject.get_drive_info()


def test_drive_metadata_reports_capacity_without_inventing_media_type(subject, monkeypatch):
    monkeypatch.setattr(subject, 'get_drives', lambda: ['C:', 'D:'])
    def usage(root):
        if root == 'D:\\':
            raise OSError('Volume is locked')
        assert root == 'C:\\'
        return SimpleNamespace(total=1000, free=300, used=700)
    monkeypatch.setattr(shutil, 'disk_usage', usage)
    assert subject.get_drive_info() == [
        {'letter': 'C:', 'type': 'Fixed', 'total_bytes': 1000, 'free_bytes': 300,
         'used_percent': 70.0, 'available': True, 'error': ''},
        {'letter': 'D:', 'type': 'Fixed', 'total_bytes': None, 'free_bytes': None,
         'used_percent': None, 'available': False, 'error': 'Volume is locked'},
    ]
