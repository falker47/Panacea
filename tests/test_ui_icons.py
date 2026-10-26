"""Local licensed assets, color handling and original-brand regressions."""
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageColor
import pytest

from modules.ui_icons import ICON_SOURCES, make_icon, make_battery_icon, make_windows_icon


ROOT = Path(__file__).resolve().parents[1]
LUCIDE = ROOT / 'assets' / 'icons' / 'lucide'


@pytest.mark.parametrize('name', [
    'dashboard', 'clean', 'disk', 'tools', 'apps', 'turbo',
    'cpu', 'memory', 'drive', 'scan', 'restore', 'updates',
])
@pytest.mark.parametrize('size', [20, 24, 30, 36, 96])
def test_each_ui_icon_has_visible_transparent_art_and_consistent_size(name, size):
    icon = make_icon(name, '#e4c579', size)
    assert icon.mode == 'RGBA'
    assert icon.size == (size, size)
    assert icon.getbbox() is not None
    assert icon.getpixel((0, 0))[3] == 0


def test_unknown_icon_is_a_configuration_error():
    with pytest.raises(ValueError, match='Unknown Panacea icon'):
        make_icon('unknown-icon')


@pytest.mark.parametrize('size', [20, 24, 30, 36, 96])
def test_resurrection_keeps_original_chalice_mark_without_the_square_border(size):
    inactive = make_icon('resurrect', '#a5b5cd', size)
    active = make_icon('resurrect', '#e4c579', size)
    assert inactive.mode == active.mode == 'RGBA'
    assert inactive.size == active.size == (size, size)
    assert inactive.getchannel('A').tobytes() == active.getchannel('A').tobytes()
    assert inactive.convert('RGB').getextrema() == tuple(
        (value, value) for value in ImageColor.getrgb('#a5b5cd'))
    assert active.getbbox() is not None
    # The original boxed icon's continuous outer border must not be present.
    assert all(active.getpixel((0, i))[3] == 0 for i in range(size))
    assert all(active.getpixel((size - 1, i))[3] == 0 for i in range(size))
    assert all(active.getpixel((i, 0))[3] == 0 for i in range(size))
    assert all(active.getpixel((i, size - 1))[3] == 0 for i in range(size))


def test_full_brand_image_remains_distinct_from_the_navigation_glyph():
    with Image.open(ROOT / 'assets' / 'panacea_icon.png') as image:
        full = image.convert('RGBA').resize((96, 96), Image.Resampling.LANCZOS)
    assert full.tobytes() != make_icon('resurrect', '#e4c579', 96).tobytes()


@pytest.mark.parametrize('color', ['#a5b5cd', '#e4c579', '#76b6e2'])
def test_lucide_tint_changes_rgb_without_changing_art(color):
    colored = make_icon('clean', color)
    reference = make_icon('clean', 'white')
    assert colored.getchannel('A').tobytes() == reference.getchannel('A').tobytes()
    assert colored.convert('RGB').getextrema() == tuple((value, value) for value in ImageColor.getrgb(color))


def test_mutating_one_icon_does_not_corrupt_cached_art():
    first = make_icon('dashboard', size=96)
    expected = first.tobytes()
    first.paste((255, 0, 0, 255), (0, 0, 96, 96))
    assert make_icon('dashboard', size=96).tobytes() == expected


def test_asset_resolution_supports_frozen_extraction(monkeypatch, tmp_path):
    import sys
    import shutil

    bundled = tmp_path / 'assets' / 'icons' / 'lucide' / 'png'
    bundled.mkdir(parents=True)
    shutil.copy(LUCIDE / 'png' / 'wrench.png', bundled / 'wrench.png')
    expected = make_icon('tools').tobytes()
    monkeypatch.setattr(sys, '_MEIPASS', str(tmp_path), raising=False)
    assert make_icon('tools').tobytes() == expected


def test_vendored_assets_match_pinned_upstream_and_render_manifests():
    manifest = json.loads((LUCIDE / 'manifest.json').read_text(encoding='utf-8'))
    rendered = json.loads((LUCIDE / 'rendered.json').read_text(encoding='utf-8'))
    base = f"https://raw.githubusercontent.com/lucide-icons/lucide/{manifest['revision']}/"
    assert len(manifest['revision']) == 40
    assert set(manifest['files']) == {f'svg/{name}.svg' for name in ICON_SOURCES.values()} | {'LICENSE'}
    for path, metadata in manifest['files'].items():
        assert metadata['source'].startswith(base)
        assert hashlib.sha256((LUCIDE / path).read_bytes()).hexdigest() == metadata['sha256']
    assert set(rendered['files']) == {f'png/{name}.png' for name in ICON_SOURCES.values()}
    for path, expected_hash in rendered['files'].items():
        assert hashlib.sha256((LUCIDE / path).read_bytes()).hexdigest() == expected_hash
        with Image.open(LUCIDE / path) as icon:
            assert icon.size == (96, 96)
            assert 'A' in icon.getbands()
    license_text = (LUCIDE / 'LICENSE').read_text(encoding='utf-8')
    assert 'ISC License' in license_text
    assert 'Copyright (c) 2026 Lucide Icons and Contributors' in license_text
    assert 'The MIT License (MIT)' in license_text


def test_vendored_assets_survive_git_checkout_with_autocrlf(tmp_path):
    """A Windows checkout must preserve the upstream and renderer byte hashes."""
    import os
    import shutil
    import subprocess

    repository = tmp_path / 'repository'
    repository.mkdir()
    shutil.copytree(LUCIDE, repository / 'assets' / 'icons' / 'lucide')
    attributes = ROOT / '.gitattributes'
    if attributes.exists():
        shutil.copyfile(attributes, repository / '.gitattributes')
    environment = {**os.environ, 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull}

    def git(*args):
        subprocess.run(['git', '-C', str(repository), '-c', 'core.autocrlf=true',
                        '-c', 'core.safecrlf=false', *args],
                       stdin=subprocess.DEVNULL, capture_output=True, text=True,
                       check=True, timeout=30, env=environment,
                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))

    git('init', '--quiet')
    git('add', '--all')
    checkout = tmp_path / 'fresh-checkout'
    git('checkout-index', '--all', '--prefix=' + checkout.as_posix() + '/')
    checked_assets = checkout / 'assets' / 'icons' / 'lucide'
    manifest = json.loads((checked_assets / 'manifest.json').read_text(encoding='utf-8'))
    for path, metadata in manifest['files'].items():
        assert hashlib.sha256((checked_assets / path).read_bytes()).hexdigest() == metadata['sha256']
    # The reproducible renderer also compares this generated manifest byte-for-byte.
    assert (checked_assets / 'rendered.json').read_bytes() == (LUCIDE / 'rendered.json').read_bytes()


@pytest.mark.parametrize('size', [0, -1, 1.5, True])
def test_invalid_sizes_fail_with_clear_configuration_error(size):
    with pytest.raises(ValueError, match='positive integer'):
        make_icon('dashboard', size=size)



def test_battery_fill_tracks_percent_and_charging_marker_is_distinct():
    from PIL import ImageChops
    empty = make_battery_icon(0, color='#76b6e2')
    full = make_battery_icon(100, color='#76b6e2')
    charging = make_battery_icon(50, charging=True, color='#76b6e2')
    assert empty.size == full.size == charging.size == (96, 96)
    assert ImageChops.difference(empty, full).getbbox() is not None
    assert ImageChops.difference(charging, full).getbbox() is not None
    assert make_windows_icon(size=40).size == (40, 40)
