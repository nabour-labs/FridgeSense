import io

from PIL import Image

from tests.conftest import jpeg


def test_jpeg_helper_makes_valid_images():
    for data in (jpeg(0.8), jpeg(bright_box=(0.6, 0.0, 0.4, 1.0))):
        img = Image.open(io.BytesIO(data))
        assert img.format == "JPEG" and img.size == (320, 180)
