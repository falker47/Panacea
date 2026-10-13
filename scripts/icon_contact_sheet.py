"""Render the actual CTkImage source/downsample pipeline without opening a GUI."""
import argparse
from pathlib import Path
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from modules.ui_icons import make_icon  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/validation/v2-icons-contact.png')
    args = parser.parse_args()
    sheet = Image.new('RGB', (1040, 710), '#0b1525')
    draw = ImageDraw.Draw(sheet)
    try:
        title = ImageFont.truetype('segoeuib.ttf', 23)
        body = ImageFont.truetype('segoeui.ttf', 16)
        small = ImageFont.truetype('segoeui.ttf', 13)
    except OSError:
        title = ImageFont.load_default(size=23)
        body = ImageFont.load_default(size=16)
        small = ImageFont.load_default(size=13)

    draw.text((26, 20), 'PANACEA / LOCAL ICON SYSTEM', fill='#e4c579', font=title)
    draw.text((26, 58), 'Lucide 2px strokes | Original Panacea gold chalice | Native pixel sizes', fill='#a5b5cd', font=body)
    rows = [('Dashboard', 'dashboard'), ('Cleanup', 'clean'), ('Disk', 'disk'),
            ('Tools', 'tools'), ('Apps', 'apps'), ('Turbo', 'turbo'), ('Resurrection', 'resurrect')]
    for column, size in enumerate((20, 24, 30, 36)):
        left = 240 + column * 195
        draw.text((left, 102), f'{size} px', fill='#f1f3f8', font=body)
        draw.text((left, 125), 'Idle         Selected', fill='#a5b5cd', font=small)
        for row, (label, name) in enumerate(rows):
            y = 153 + row * 58
            if column == 0:
                draw.text((26, y + 13), label, fill='#f1f3f8', font=body)
            for state, color in enumerate(('#a5b5cd', '#e4c579')):
                x = left + state * 78
                draw.rounded_rectangle((x - 8, y, x + 51, y + 48), radius=6,
                                       fill='#0e192b' if state == 0 else '#1b2b44')
                # Same 96px source and Pillow LANCZOS downsample used by CTkImage.
                art = make_icon(name, color, 96).resize((size, size), Image.Resampling.LANCZOS)
                sheet.paste(art, (x + (44-size)//2, y + (48-size)//2), art)

    draw.line((26, 576, 1010, 576), fill='#2e415c')
    draw.text((26, 594), 'Dashboard actions / 22 px', fill='#f1f3f8', font=body)
    for column, name in enumerate(('cpu', 'memory', 'drive', 'scan', 'restore', 'updates')):
        x = 310 + column * 118
        color = '#e4c579' if name in ('drive', 'restore') else '#76b6e2'
        art = make_icon(name, color, 96).resize((22, 22), Image.Resampling.LANCZOS)
        sheet.paste(art, (x, 595), art)
        draw.text((x - 8, 625), name, fill='#a5b5cd', font=small)
    draw.text((26, 669), 'Offline asset contact sheet; full Windows layout and DPI evidence is recorded separately.',
              fill='#a5b5cd', font=small)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.output)
    print(args.output)


if __name__ == '__main__':
    main()
