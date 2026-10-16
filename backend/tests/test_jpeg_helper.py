import io

from PIL import Image, ImageStat

from tests.conftest import checkerboard_jpeg, color_jpeg, jpeg


def test_jpeg_helper_makes_valid_images():
    for data in (jpeg(0.8), jpeg(bright_box=(0.6, 0.0, 0.4, 1.0))):
        img = Image.open(io.BytesIO(data))
        assert img.format == "JPEG" and img.size == (320, 180)


def test_checkerboard_helper_is_high_contrast():
    img = Image.open(io.BytesIO(checkerboard_jpeg())).convert("L")
    assert img.size == (320, 180)
    assert ImageStat.Stat(img).stddev[0] > 100


def test_color_jpeg_helper_fills_and_draws_blocks():
    data = color_jpeg(fill=(128, 128, 128), blocks=[((0.5, 0.0, 0.5, 0.5), (40, 90, 200))])
    img = Image.open(io.BytesIO(data)).convert("RGB")
    assert img.size == (320, 180)
    inside = img.getpixel((240, 45))
    outside = img.getpixel((80, 135))
    assert all(abs(a - b) <= 6 for a, b in zip(inside, (40, 90, 200), strict=True))
    assert all(abs(a - 128) <= 6 for a in outside)
