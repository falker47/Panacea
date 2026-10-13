"""Local Lucide icons and the original Panacea chalice for CustomTkinter.

SVG sources, licenses and pre-rendered 96px PNGs live in assets/icons/lucide.
Pillow only resizes/tints their alpha masks at runtime; no SVG engine, icon
font, network access or hand-drawn substitute is involved.
"""
from functools import lru_cache

from PIL import Image

from modules.utils import resource_path


ICON_SOURCES = {
    'dashboard': 'layout-dashboard',
    'clean': 'brush-cleaning',
    'disk': 'hard-drive',
    'tools': 'wrench',
    'apps': 'layout-grid',
    'turbo': 'zap',
    'cpu': 'cpu',
    'memory': 'memory-stick',
    'drive': 'hard-drive',
    'scan': 'file-search',
    'restore': 'shield-plus',
    'updates': 'refresh-cw',
}


@lru_cache(maxsize=16)
def _load_image(path):
    """Decode each bundled asset once and immediately close its file handle."""
    with Image.open(path) as source:
        return source.convert('RGBA')


def make_icon(name, color='#C0CEE0', size=24):
    """Return an independent RGBA icon; Resurrection keeps the brand's gold.

    The public name/color/size API is retained. ``color`` tints Lucide icons only:
    the proprietary chalice must never be replaced with a generic recovery glyph
    or recolored to match an inactive navigation item.
    """
    if name != 'resurrect' and name not in ICON_SOURCES:
        raise ValueError(f'Unknown Panacea icon: {name}')
    if not isinstance(size, int) or isinstance(size, bool) or size < 1:
        raise ValueError('Icon size must be a positive integer')
    if name == 'resurrect':
        original = _load_image(resource_path('assets/panacea_icon.png'))
        return original.resize((size, size), Image.Resampling.LANCZOS)

    source = _load_image(resource_path(
        f'assets/icons/lucide/png/{ICON_SOURCES[name]}.png'))
    alpha = source.getchannel('A').resize((size, size), Image.Resampling.LANCZOS)
    icon = Image.new('RGBA', (size, size), color)
    icon.putalpha(alpha)
    return icon
