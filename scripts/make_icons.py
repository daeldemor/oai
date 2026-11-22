#!/usr/bin/env python3
"""Иконки для ярлыков Inkling: капля чернил на градиенте и подпись с размером контекста.

    .venv/Scripts/python.exe scripts/make_icons.py

Пишет assets/icons/inkling-320k.ico и inkling-128k.ico (16–256 px). На размерах до 32 px
подпись не читается, там рисуется одна капля.
"""
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "icons"
S = 1024  # рисуем крупно, потом уменьшаем
FONT = "C:/Windows/Fonts/bahnschrift.ttf"
SIZES = [16, 20, 24, 32, 40, 48, 64, 96, 128, 256]

VARIANTS = {
    "inkling-320k": ("320K", (76, 29, 149), (192, 38, 211)),   # индиго -> фуксия
    "inkling-128k": ("128K", (12, 74, 110), (20, 184, 166)),   # глубокий синий -> бирюза
}


def gradient(c1, c2):
    g = Image.new("RGB", (S, S))
    px = g.load()
    for y in range(S):
        for x in range(S):
            t = (x + y) / (2 * (S - 1))  # диагональ сверху-слева вниз-вправо
            px[x, y] = tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))
    return g


def drop_mask(cx, cy, r):
    """Капля: круг снизу и треугольник-хвост вверх, сглаженные."""
    m = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(m)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
    tip = cy - 2.15 * r
    d.polygon([(cx, tip), (cx - 0.86 * r, cy - 0.5 * r), (cx + 0.86 * r, cy - 0.5 * r)], fill=255)
    return m.filter(ImageFilter.GaussianBlur(S / 400))


def render(label, c1, c2, with_text):
    base = gradient(c1, c2).convert("RGBA")
    # скруглённый квадрат
    shape = Image.new("L", (S, S), 0)
    ImageDraw.Draw(shape).rounded_rectangle([0, 0, S - 1, S - 1], radius=int(S * 0.22), fill=255)
    base.putalpha(shape)

    # мягкий блик сверху
    gloss = Image.new("L", (S, S), 0)
    ImageDraw.Draw(gloss).ellipse([-S * 0.3, -S * 0.75, S * 1.3, S * 0.42], fill=60)
    gloss = ImageChops.multiply(gloss.filter(ImageFilter.GaussianBlur(S / 7)), shape)
    base = Image.composite(Image.new("RGBA", (S, S), (255, 255, 255, 255)), base, gloss)
    base.putalpha(shape)

    if with_text:
        cx, cy, r = S / 2, S * 0.43, S * 0.17
    else:
        cx, cy, r = S / 2, S * 0.62, S * 0.25
    drop = drop_mask(cx, cy, r)

    # тень под каплей
    shadow = ImageChops.offset(drop, 0, int(S * 0.018)).filter(ImageFilter.GaussianBlur(S / 60))
    base = Image.composite(Image.new("RGBA", (S, S), (0, 0, 0, 255)),
                           base, shadow.point(lambda v: v * 0.35))
    base = Image.composite(Image.new("RGBA", (S, S), (255, 255, 255, 255)), base, drop)

    if with_text:
        d = ImageDraw.Draw(base)
        font = ImageFont.truetype(FONT, int(S * 0.24))
        font.set_variation_by_name("Bold")
        w = d.textlength(label, font=font)
        d.text(((S - w) / 2, S * 0.66), label, font=font, fill=(255, 255, 255, 255))

    base.putalpha(ImageChops.multiply(base.getchannel("A"), shape))
    return base


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, (label, c1, c2) in VARIANTS.items():
        big, small = render(label, c1, c2, True), render(label, c1, c2, False)
        frames = [(small if s <= 32 else big).resize((s, s), Image.LANCZOS) for s in SIZES]
        frames[-1].save(OUT / f"{name}.ico", format="ICO", sizes=[(s, s) for s in SIZES],
                        append_images=frames[:-1])
        big.resize((256, 256), Image.LANCZOS).save(OUT / f"{name}.png")
        print(OUT / f"{name}.ico")


if __name__ == "__main__":
    main()
