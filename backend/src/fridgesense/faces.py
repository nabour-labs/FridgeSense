"""Face blurring for fridge-camera stills: faces never reach S3 or Nova."""

import io
import logging
from collections.abc import Iterable

from botocore.exceptions import BotoCoreError, ClientError
from PIL import Image, ImageFilter

from fridgesense.logs import log_event

Box = tuple[float, float, float, float]

ENLARGE = 1.3
PIXEL_BLOCKS = 8  # the longer side of a face shrinks to this many pixels
JPEG_QUALITY = 95
DEFAULT_PRICE = 0.001  # USD per image (Rekognition DetectFaces)


def enlarge_box(box: Box, factor: float = ENLARGE) -> Box:
    """Grow a face box (fractions x, y, width, height) about its centre, clipped to the image."""
    x, y, w, h = box
    cx, cy = x + w / 2, y + h / 2
    half_w, half_h = w * factor / 2, h * factor / 2
    left, top = max(0.0, cx - half_w), max(0.0, cy - half_h)
    right, bottom = min(1.0, cx + half_w), min(1.0, cy + half_h)
    return left, top, right - left, bottom - top


def blur_regions(jpeg: bytes, boxes: Iterable[Box]) -> bytes:
    """Pixelate then blur each enlarged face box; returns a new JPEG."""
    img = Image.open(io.BytesIO(jpeg)).convert("RGB")
    W, H = img.size
    for box in boxes:
        x, y, w, h = enlarge_box(box)
        left, top = round(x * W), round(y * H)
        right, bottom = round((x + w) * W), round((y + h) * H)
        if right <= left or bottom <= top:
            continue
        region = img.crop((left, top, right, bottom))
        rw, rh = region.size
        scale = PIXEL_BLOCKS / max(rw, rh)
        small = region.resize(
            (max(1, round(rw * scale)), max(1, round(rh * scale))), Image.Resampling.BOX
        )
        region = small.resize((rw, rh), Image.Resampling.NEAREST)
        region = region.filter(ImageFilter.GaussianBlur(radius=max(4, max(rw, rh) / 6)))
        img.paste(region, (left, top))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY)
    return buf.getvalue()


def _box(face: dict) -> Box:
    b = face["BoundingBox"]
    return b["Left"], b["Top"], b["Width"], b["Height"]


class FaceBlurrer:
    """Finds faces with Rekognition and blurs every one it reports."""

    def __init__(self, client, price_usd: float = DEFAULT_PRICE):
        self.client = client
        self.price_usd = price_usd

    def blur(self, jpeg: bytes, context: dict) -> bytes | None:
        """The still with every face blurred, or None if detection failed (fail closed)."""
        try:
            resp = self.client.detect_faces(Image={"Bytes": jpeg}, Attributes=["DEFAULT"])
        except ClientError as e:
            log_event(
                "face_detect_failed", logging.WARNING, error=e.response["Error"]["Code"], **context
            )
            return None
        except BotoCoreError as e:
            log_event("face_detect_failed", logging.WARNING, error=type(e).__name__, **context)
            return None
        boxes = [_box(f) for f in resp.get("FaceDetails", [])]
        log_event("face_detect_cost", **context, faces=len(boxes), usd=self.price_usd)
        return blur_regions(jpeg, boxes) if boxes else jpeg


class NoBlur:
    """Stands in for FaceBlurrer while face blurring is off: no detection, bytes unchanged."""

    def blur(self, jpeg: bytes, context: dict) -> bytes:
        return jpeg
