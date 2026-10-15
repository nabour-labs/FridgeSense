"""Draws the FridgeSense app icons and iOS splash images (same design as public/icon.svg).

Run from pwa/: uv run --project ../backend python scripts/make_icons.py
"""

from PIL import Image, ImageDraw

# Brand colours (index.css): brand-400, brand-700, brand-50, brand-950.
TOP, BOTTOM, ICE, DEEP = (37, 207, 191), (0, 116, 111), (234, 253, 252), (0, 43, 43)
WARM = (245, 158, 11)  # warm-500

# iPhone portrait splash sizes: (width, height, device width, device height, pixel ratio).
SPLASHES = [
    (750, 1334, 375, 667, 2),  # iPhone SE
    (1179, 2556, 393, 852, 3),  # iPhone 15 / 16 Pro
    (1290, 2796, 430, 932, 3),  # iPhone 15 / 16 Pro Max
]


def gradient(size: int) -> Image.Image:
    img = Image.new("RGB", (size, size))
    d = ImageDraw.Draw(img)
    for y in range(size):
        t = y / max(1, size - 1)
        d.line([(0, y), (size, y)], fill=tuple(round(a + (b - a) * t) for a, b in zip(TOP, BOTTOM)))
    return img


def icon(size: int, maskable: bool = False) -> Image.Image:
    s = size / 512
    img = gradient(size).convert("RGBA")
    if not maskable:
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=112 * s, fill=255)
        img.putalpha(mask)
    d = ImageDraw.Draw(img)
    # Maskable icons keep the art inside the central 80% safe zone.
    k = 0.8 if maskable else 1.0
    off = (1 - k) * size / 2

    def box(x0, y0, x1, y1):
        return [off + x0 * s * k, off + y0 * s * k, off + x1 * s * k, off + y1 * s * k]

    d.rounded_rectangle(box(156, 88, 356, 424), radius=36 * s * k, fill=ICE)
    d.rectangle(box(156, 201, 356, 215), fill=DEEP)
    d.rounded_rectangle(box(186, 128, 200, 176), radius=7 * s * k, fill=DEEP)
    d.rounded_rectangle(box(186, 236, 200, 308), radius=7 * s * k, fill=DEEP)
    d.ellipse(box(266, 302, 334, 370), fill=WARM)
    return img if not maskable else img.convert("RGB")


def splash(width: int, height: int) -> Image.Image:
    img = Image.new("RGB", (width, height), ICE)
    size = round(min(width, height) * 0.32)
    art = icon(size)
    img.paste(art, ((width - size) // 2, (height - size) // 2), art)
    return img


for size in (192, 512):
    icon(size).save(f"public/icon-{size}.png")
icon(512, maskable=True).save("public/icon-maskable-512.png")
icon(180, maskable=True).save("public/apple-touch-icon.png")
for w, h, *_ in SPLASHES:
    splash(w, h).save(f"public/splash-{w}x{h}.png", optimize=True)
