"""The motion event's clip: downloaded once from Ring, then sampled into frames for the door check.

The clip only ever lives in Lambda /tmp (or memory) and is never stored in S3.
"""

import os
import tempfile
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path

import httpx
from PIL import Image

from fridgesense.oauth import OAuthRejected, OAuthUnavailable
from fridgesense.ring import RingAuthError, RingClient

FRAME_INTERVAL_MS = 500
MAX_CLIP_BYTES = 300_000_000
CLIP_RETRY_DELAYS_S = (3, 6)
NOT_READY = {416, 425}  # RECORDING_NOT_READY / MEDIA_NOT_FOUND, from the request or the link
CHUNK_BYTES = 1 << 20


class ClipUnavailable(Exception):
    """The clip can't be used; `reason` says why (status_<code>, download_failed, too_large,
    decode_failed, no_frames)."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _save(http: httpx.Client, link: str, directory: Path | None, max_bytes: int) -> Path | int:
    """Stream the pre-signed link (no Ring token) to a temp file; the HTTP status if not 200."""
    with http.stream("GET", link, timeout=60.0) as resp:
        if resp.status_code != 200:
            return resp.status_code
        if int(resp.headers.get("content-length") or 0) > max_bytes:
            raise ClipUnavailable("too_large")
        fd, name = tempfile.mkstemp(suffix=".mp4", dir=directory)
        path = Path(name)
        try:
            size = 0
            with os.fdopen(fd, "wb") as f:
                for chunk in resp.iter_bytes(CHUNK_BYTES):
                    size += len(chunk)
                    if size > max_bytes:
                        raise ClipUnavailable("too_large")
                    f.write(chunk)
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        return path


def download_clip(
    ring: RingClient,
    http: httpx.Client,
    device_id: str,
    start_ms: int,
    duration_ms: int,
    sleep: Callable[[float], None],
    directory: Path | None = None,
    max_bytes: int = MAX_CLIP_BYTES,
    delays: tuple[int, ...] = CLIP_RETRY_DELAYS_S,
) -> Path:
    """The event clip as a temp MP4 file; the caller deletes it. Raises ClipUnavailable.

    Ring answers 303 at once; missing footage shows up as 416/425 from the request or the
    link, so both are retried together after each delay in `delays`.
    """
    body = {"timestamp": start_ms, "duration": duration_ms}
    for attempt in range(len(delays) + 1):
        try:
            resp = ring.post(f"/v1/devices/{device_id}/media/video/download", json=body)
            if resp.is_redirect and resp.headers.get("location"):
                saved = _save(http, resp.headers["location"], directory, max_bytes)
                if isinstance(saved, Path):
                    return saved
                status = saved
            else:
                status = resp.status_code
        except (httpx.HTTPError, RingAuthError, OAuthRejected, OAuthUnavailable):
            raise ClipUnavailable("download_failed") from None
        if status not in NOT_READY or attempt == len(delays):
            raise ClipUnavailable(f"status_{status}")
        sleep(delays[attempt])
    raise ClipUnavailable("download_failed")  # unreachable: the loop always returns or raises


def parse_frame_interval(setting: str | None) -> int:
    """DOOR_FRAME_INTERVAL_MS: whole milliseconds between checked frames, default 500."""
    if not setting or not setting.strip():
        return FRAME_INTERVAL_MS
    try:
        value = int(setting)
    except ValueError:
        value = 0
    if value <= 0:
        raise ValueError("DOOR_FRAME_INTERVAL_MS must be a whole number of milliseconds above 0")
    return value


def clip_duration_ms(path: Path) -> int:
    """The clip's length in ms (decoder imported here so other Lambdas never load FFmpeg)."""
    import av

    try:
        with av.open(str(path)) as container:
            if not container.streams.video or container.duration is None:
                raise ClipUnavailable("decode_failed")
            return container.duration * 1000 // av.time_base
    except av.FFmpegError:
        raise ClipUnavailable("decode_failed") from None


def frames_at(path: Path, offsets_ms: Iterable[int]) -> Iterator[tuple[int, Image.Image]]:
    """(offset, frame shown at that offset) in one forward decode, for offsets inside the clip.

    The frame shown at t is the latest frame that starts at or before t. Frames are yielded
    one at a time so a long clip never sits in memory decoded.
    """
    import av

    duration = clip_duration_ms(path)
    wanted = sorted({ms for ms in offsets_ms if 0 <= ms < duration})
    found = 0
    try:
        with av.open(str(path)) as container:
            stream = container.streams.video[0]
            stream.thread_type = "AUTO"
            shown = None
            for frame in container.decode(stream):
                start_ms = round(frame.time * 1000)
                while wanted and shown is not None and start_ms > wanted[0]:
                    found += 1
                    yield wanted.pop(0), shown.to_image()
                if not wanted:
                    return
                shown = frame
            while wanted and shown is not None:  # after the last frame starts: it is still shown
                found += 1
                yield wanted.pop(0), shown.to_image()
    except av.FFmpegError:
        raise ClipUnavailable("decode_failed") from None
    if not found:
        raise ClipUnavailable("no_frames")


def sample_frames(path: Path, interval_ms: int) -> Iterator[tuple[int, Image.Image]]:
    """The frame shown at 0, interval, 2 x interval, ... up to the clip's end."""
    return frames_at(path, range(0, clip_duration_ms(path), interval_ms))
