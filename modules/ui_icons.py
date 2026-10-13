"""Small consistent, transparent line icons rendered by Pillow at UI startup.

No icon font, network fetch, or third-party icon bundle is required.
The Panacea chalice remains the product logo (assets/panacea_icon.png).
"""
from PIL import Image, ImageDraw


def make_icon(name, color='#C0CEE0', size=24):
    """Return a high-quality RGBA icon for CTkImage, with shared stroke weight."""
    image = Image.new('RGBA', (96, 96), (0, 0, 0, 0))
    pen = ImageDraw.Draw(image)
    c = color
    def stroke(points, width=7):
        pen.line(points, fill=c, width=width, joint='curve')
        radius = width // 2
        for x, y in (points[0], points[-1]):
            pen.ellipse((x-radius, y-radius, x+radius, y+radius), fill=c)
    def frame(box, radius=10, width=6):
        pen.rounded_rectangle(box, radius=radius, outline=c, width=width)
    def circle(box, width=6):
        pen.ellipse(box, outline=c, width=width)

    if name == 'dashboard':
        frame((13, 13, 45, 45), 6)
        frame((53, 13, 83, 45), 6)
        frame((13, 53, 45, 83), 6)
        frame((53, 53, 83, 83), 6)
    elif name == 'clean':
        stroke([(30, 17), (62, 50)], 8)
        pen.polygon([(58, 53), (78, 64), (85, 82), (68, 78), (51, 60)], outline=c)
        stroke([(54, 67), (70, 83)], 5)
        stroke([(65, 58), (81, 74)], 5)
    elif name == 'disk':
        pen.ellipse((16, 16, 80, 36), outline=c, width=6)
        stroke([(16, 26), (16, 70)], 6)
        stroke([(80, 26), (80, 70)], 6)
        pen.arc((16, 38, 80, 63), 0, 180, fill=c, width=6)
        pen.arc((16, 56, 80, 84), 0, 180, fill=c, width=6)
    elif name == 'tools':
        stroke([(23, 74), (72, 25)], 8)
        circle((13, 66, 31, 84), 5)
        pen.arc((48, 8, 88, 48), 55, 310, fill=c, width=7)
        stroke([(26, 21), (46, 42)], 6)
        pen.ellipse((18, 12, 29, 23), outline=c, width=4)
    elif name == 'apps':
        for x in (15, 55):
            for y in (15, 55):
                frame((x, y, x + 26, y + 26), 5)
    elif name == 'turbo':
        pen.polygon([(53, 10), (22, 57), (46, 57), (39, 86), (78, 40), (54, 40)], outline=c)
        stroke([(53, 10), (22, 57), (46, 57), (39, 86), (78, 40), (54, 40), (53, 10)], 5)
    elif name == 'resurrect':
        pen.arc((16, 18, 80, 82), 50, 334, fill=c, width=7)
        stroke([(16, 30), (17, 12), (35, 18)], 6)
        stroke([(48, 31), (48, 51), (63, 60)], 6)
    elif name == 'cpu':
        frame((24, 24, 72, 72), 8)
        frame((38, 38, 58, 58), 3, 5)
        for n in (35, 49, 63):
            stroke([(n, 12), (n, 21)], 5)
            stroke([(n, 75), (n, 84)], 5)
            stroke([(12, n), (21, n)], 5)
            stroke([(75, n), (84, n)], 5)
    elif name == 'memory':
        frame((12, 29, 84, 66), 8)
        for x in (25, 39, 53, 67):
            frame((x, 40, x+8, 53), 2, 3)
        for x in (25, 40, 55, 70):
            stroke([(x, 66), (x, 73)], 4)
    elif name == 'drive':
        frame((14, 31, 82, 69), 8)
        stroke([(20, 47), (76, 47)], 4)
        pen.ellipse((65, 55, 72, 62), fill=c)
    elif name == 'scan':
        frame((19, 11, 59, 77), 7)
        stroke([(30, 29), (48, 29)], 5)
        stroke([(30, 42), (44, 42)], 5)
        circle((43, 45, 75, 77), 6)
        stroke([(69, 72), (84, 88)], 7)
    elif name == 'restore':
        pen.arc((17, 17, 78, 78), 35, 330, fill=c, width=6)
        stroke([(18, 29), (18, 13), (35, 18)], 6)
        stroke([(48, 33), (48, 63)], 6)
        stroke([(33, 48), (63, 48)], 6)
    elif name == 'updates':
        pen.arc((17, 17, 79, 79), 35, 190, fill=c, width=7)
        pen.arc((17, 17, 79, 79), 215, 370, fill=c, width=7)
        stroke([(80, 53), (79, 79), (58, 73)], 6)
        stroke([(16, 43), (17, 17), (38, 22)], 6)
    else:
        raise ValueError(f'Unknown Panacea icon: {name}')
    return image.resize((size, size), Image.Resampling.LANCZOS)
