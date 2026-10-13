"""Render-time smoke coverage for the first-party, consistent sidebar icons."""
import pytest

from modules.ui_icons import make_icon


@pytest.mark.parametrize('name', [
    'dashboard', 'clean', 'disk', 'tools', 'apps', 'turbo', 'resurrect',
    'cpu', 'memory', 'drive', 'scan', 'restore', 'updates',
])
def test_each_ui_icon_has_visible_transparent_art_and_consistent_size(name):
    icon = make_icon(name, '#e4c579', 24)
    assert icon.mode == 'RGBA'
    assert icon.size == (24, 24)
    assert icon.getbbox() is not None
    assert icon.getpixel((0, 0))[3] == 0


def test_unknown_icon_is_a_configuration_error():
    with pytest.raises(ValueError, match='Unknown Panacea icon'):
        make_icon('unknown-icon')
