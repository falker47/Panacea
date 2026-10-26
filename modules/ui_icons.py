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
    """Return an independent RGBA icon.

    Resurrection reuses the original chalice silhouette as a uniform
    foreground-only sidebar glyph. The complete brand image is unchanged.
    """
    if name != 'resurrect' and name not in ICON_SOURCES:
        raise ValueError(f'Unknown Panacea icon: {name}')
    if not isinstance(size, int) or isinstance(size, bool) or size < 1:
        raise ValueError('Icon size must be a positive integer')
    if name == 'resurrect':
        # Extract the *actual* Panacea chalice from the supplied brand asset,
        # excluding the square logo border. Recolor the mark like the other
        # outline navigation icons; the full original logo remains unchanged.
        original = _load_image(resource_path('assets/panacea_icon.png'))
        mark = original.crop((140, 73, 394, 425)).convert('L')
        alpha = mark.point(lambda value: max(0, min(255, (value - 38) * 3)))
        alpha.thumbnail((max(1, round(size * 0.78)),
                         max(1, round(size * 0.88))), Image.Resampling.LANCZOS)
        if size >= 20:
            from PIL import ImageFilter
            alpha = alpha.filter(ImageFilter.MaxFilter(3))
        mask = Image.new('L', (size, size), 0)
        mask.paste(alpha, ((size - alpha.width) // 2, (size - alpha.height) // 2))
        icon = Image.new('RGBA', (size, size), color)
        icon.putalpha(mask)
        return icon

    source = _load_image(resource_path(
        f'assets/icons/lucide/png/{ICON_SOURCES[name]}.png'))
    alpha = source.getchannel('A').resize((size, size), Image.Resampling.LANCZOS)
    icon = Image.new('RGBA', (size, size), color)
    icon.putalpha(alpha)
    return icon
