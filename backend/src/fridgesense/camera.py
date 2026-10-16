"""Camera snapshots for setup: one still from the fridge camera, faces blurred, never stored."""

import io
import logging
import time
from collections.abc import Callable

import httpx
from botocore.exceptions import BotoCoreError, ClientError
from PIL import Image

from fridgesense.door_events import NOT_READY, fetch_still
from fridgesense.faces import FaceBlurrer
from fridgesense.logs import log_event
from fridgesense.ring import RingClient

SNAPSHOT_LAG_MS = 3000  # the newest seconds of footage are often not indexed yet
SNAPSHOT_RETRY_DELAYS_S = (2,)
MAX_WIDTH = 960
MAX_BYTES = 300_000
QUALITY, SMALLER_QUALITY, SMALLER_ABOVE = 85, 70, 250_000


class NoFootage(Exception):
    """Ring has no footage near now: nothing moved in front of the camera recently."""


class SnapshotFailed(Exception):
    """Ring, the Ring token or face detection failed; no image may be returned."""


def _encode(img: Image.Image, quality: int) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def shrink(jpeg: bytes, max_width: int = MAX_WIDTH) -> bytes:
    """At most `max_width` px wide (aspect kept), JPEG of at most MAX_BYTES."""
    img = Image.open(io.BytesIO(jpeg)).convert("RGB")
    if img.width > max_width:
        img = img.resize((max_width, round(img.height * max_width / img.width)), Image.LANCZOS)
    data = _encode(img, QUALITY)
    if len(data) > SMALLER_ABOVE:
        data = _encode(img, SMALLER_QUALITY)
    quality = SMALLER_QUALITY
    while len(data) > MAX_BYTES and quality > 30:
        quality -= 10
        data = _encode(img, quality)
    return data


def snapshot(
    ring: RingClient,
    http: httpx.Client,
    blurrer: FaceBlurrer,
    device_id: str,
    now_ms: int,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[bytes, int]:
    """(blurred JPEG, its timestamp ms) for the camera at now − 3 s."""
    ts = now_ms - SNAPSHOT_LAG_MS
    try:
        data, status = fetch_still(ring, http, device_id, ts, sleep, SNAPSHOT_RETRY_DELAYS_S)
    except (ClientError, BotoCoreError) as e:  # e.g. a refreshed token the API may not save
        log_event("snapshot_failed", logging.WARNING, device_id=device_id, error=type(e).__name__)
        raise SnapshotFailed() from e
    if data is None:
        raise NoFootage() if status in NOT_READY else SnapshotFailed()
    blurred = blurrer.blur(shrink(data), {"device_id": device_id, "still": "snapshot"})
    if blurred is None:
        raise SnapshotFailed()
    return shrink(blurred), ts
