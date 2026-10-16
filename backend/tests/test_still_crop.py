"""door-event-detection: Stills cropped to the visible area."""

import io

import pytest
from PIL import Image

from fridgesense.door_events import crop_still, parse_crop
from tests.conftest import color_jpeg, jpeg

RED = (220, 30, 30)
# Red marker column at x = 768..777 of a 2560x1440 still (0.30 = 768 / 2560)
MARKED = color_jpeg((128, 128, 128), [((0.30, 0.0, 10 / 2560, 1.0), RED)], size=(2560, 1440))


def image(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data)).convert("RGB")


# Crop to the visible strip
def test_crop_to_the_visible_strip():
    cropped = image(crop_still(MARKED, parse_crop("0.30,0.0,0.34,1.0")))
    assert abs(cropped.width - 870) <= 1 and cropped.height == 1440
    # The marker that started at x = 768 is now the left edge
    assert all(abs(a - b) <= 8 for a, b in zip(cropped.getpixel((4, 720)), RED, strict=True))
    assert all(abs(a - 128) <= 8 for a in cropped.getpixel((40, 720)))


# No crop configured
@pytest.mark.parametrize("setting", [None, "", "  "])
def test_no_crop_configured(setting):
    downloaded = jpeg(0.5)
    assert parse_crop(setting) is None
    assert crop_still(downloaded, parse_crop(setting)) == downloaded


# Invalid crop config
@pytest.mark.parametrize("setting", ["0.8,0,0.5,1", "0,0,1"])
def test_invalid_crop_config(setting):
    with pytest.raises(ValueError, match="STILL_CROP"):
        parse_crop(setting)
