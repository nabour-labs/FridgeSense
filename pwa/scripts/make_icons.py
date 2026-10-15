"""Draws the FridgeSense app icons (same design as public/icon.svg).

Run from pwa/: uv run --project ../backend python scripts/make_icons.py
"""

from PIL import Image, ImageDraw

NAVY, ICE, SKY = (15, 23, 42), (224, 242, 254), (56, 189, 248)


def icon(size: int, maskable: bool = False) -> Image.Image:
    s = size / 512
    img = Image.new("RGB" if maskable else "RGBA", (size, size), NAVY if maskable else (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if not maskable:
        d.rounded_rectangle([0, 0, size - 1, size - 1], radius=112 * s, fill=NAVY)
    # Maskable icons keep the art inside the central 80% safe zone.
    k = 0.8 if maskable else 1.0
    off = (1 - k) * size / 2

    def box(x0, y0, x1, y1):
        return [off + x0 * s * k, off + y0 * s * k, off + x1 * s * k, off + y1 * s * k]

    d.rounded_rectangle(box(156, 88, 356, 424), radius=36 * s * k, fill=ICE)
    d.rectangle(box(156, 201, 356, 215), fill=NAVY)
    d.rounded_rectangle(box(186, 128, 200, 176), radius=7 * s * k, fill=NAVY)
    d.rounded_rectangle(box(186, 236, 200, 308), radius=7 * s * k, fill=NAVY)
    d.ellipse(box(266, 302, 334, 370), fill=SKY)
    return img


for size in (192, 512):
    icon(size).save(f"public/icon-{size}.png")
icon(512, maskable=True).save("public/icon-maskable-512.png")
icon(180, maskable=True).save("public/apple-touch-icon.png")
