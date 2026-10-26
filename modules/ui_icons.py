"""Local Lucide icons and the original Panacea chalice for CustomTkinter.

SVG sources, licenses and pre-rendered 96px PNGs live in assets/icons/lucide.
Pillow only resizes/tints their alpha masks at runtime; no SVG engine, icon
font or network access is required. A battery status icon is drawn locally
from the reported charge level, without any external imagery.
"""
from functools import lru_cache

from PIL import Image, ImageColor, ImageDraw

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


@lru_cache(maxsize=48)
def make_battery_icon(percent=None, *, plugged=False, charging=False,
                      color='#76b6e2', size=96):
    """Native battery pictogram. Only the confirmed percentage fills its body."""
    if not isinstance(size, int) or isinstance(size, bool) or size < 1:
        raise ValueError('Icon size must be a positive integer')
    if percent is not None and (isinstance(percent, bool) or not isinstance(percent, (int, float))
                                or not 0 <= percent <= 100):
        raise ValueError('Battery percent must be between 0 and 100 or None')
    tint = ImageColor.getrgb(color)
    canvas = Image.new('RGBA', (96, 96), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((11, 25, 81, 70), radius=9, outline=tint, width=5)
    draw.rounded_rectangle((83, 39, 91, 57), radius=2, fill=tint)
    if percent is not None and percent > 0:
        end = 19 + round(percent / 100 * 55)
        if end > 19:
            draw.rounded_rectangle((19, 33, end, 62), radius=3, fill=tint)
    if charging:
        gold = ImageColor.getrgb('#e4c579')
        draw.polygon([(51, 18), (39, 47), (52, 44), (45, 79),
                      (68, 45), (55, 47), (63, 18)], fill=gold)
    elif plugged:
        draw.ellipse((59, 15, 78, 34), fill=ImageColor.getrgb('#78c8a8'))
    if size != 96:
        canvas = canvas.resize((size, size), Image.Resampling.LANCZOS)
    return canvas


@lru_cache(maxsize=4)
def make_windows_icon(color='#76b6e2', size=96):
    """Compact four-pane Windows mark, rendered locally without an icon font."""
    if not isinstance(size, int) or isinstance(size, bool) or size < 1:
        raise ValueError('Icon size must be a positive integer')
    image = Image.new('RGBA', (96, 96), (0, 0, 0, 0))
    pen = ImageDraw.Draw(image)
    paint = ImageColor.getrgb(color)
    for left, top, right, bottom in (
        (10, 12, 43, 44), (51, 12, 86, 44),
        (10, 52, 43, 84), (51, 52, 86, 84),
    ):
        pen.rectangle((left, top, right, bottom), fill=paint)
    if size != 96:
        image = image.resize((size, size), Image.Resampling.LANCZOS)
    return image
