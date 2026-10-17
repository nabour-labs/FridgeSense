"""pipeline-debug-traces: raw debug stills are small blurred thumbnails while blurring is on."""

import io

from PIL import Image, ImageChops, ImageStat

from fridgesense.traces import trace_thumbnail
from tests.conftest import checkerboard_jpeg


def size(data: bytes) -> tuple[int, int]:
    return Image.open(io.BytesIO(data)).size


def plain_downscale(data: bytes, to: tuple[int, int]) -> Image.Image:
    return Image.open(io.BytesIO(data)).convert("L").resize(to, Image.Resampling.LANCZOS)


# Raw stills are small blurred thumbnails
def test_landscape_still_becomes_160_by_90_and_blurred():
    still = checkerboard_jpeg(size=(1920, 1080), square=40)
    thumb = trace_thumbnail(still)
    assert Image.open(io.BytesIO(thumb)).format == "JPEG"
    assert size(thumb) == (160, 90)
    diff = ImageChops.difference(
        Image.open(io.BytesIO(thumb)).convert("L"), plain_downscale(still, (160, 90))
    )
    assert ImageStat.Stat(diff).mean[0] > 5  # blurred, not just shrunk


# Portrait still
def test_portrait_still_becomes_90_by_160():
    assert size(trace_thumbnail(checkerboard_jpeg(size=(1080, 1920), square=40))) == (90, 160)


# Small still not upscaled
def test_small_still_not_upscaled_but_blurred():
    still = checkerboard_jpeg(size=(100, 50), square=4)
    thumb = trace_thumbnail(still)
    assert size(thumb) == (100, 50)
    assert ImageStat.Stat(Image.open(io.BytesIO(thumb)).convert("L")).stddev[0] < 30


# Still that cannot be decoded
def test_garbage_gives_none():
    assert trace_thumbnail(b"not an image") is None
