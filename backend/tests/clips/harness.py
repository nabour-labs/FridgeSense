"""Door check on local fridge recordings: labels, a clip-backed fake camera, and scoring.

Shared by the `clips` tests and `scripts/door_clip_report.py`, so both score the same way.
Clips are read from the local clips folder only and never leave the machine.
"""

import io
import json
import math
import os
import threading
from bisect import bisect_right
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Protocol
from unittest import mock

import httpx
import respx
from PIL import Image

from fridgesense.door_events import (
    DoorCheck,
    fetch_stills,
    parse_interval,
    still_count,
    still_times,
)
from fridgesense.oauth import OAuthClient
from fridgesense.ring import API_BASE, RingClient
from fridgesense.store import Tokens
from tests.conftest import BUCKET, TABLE, FakeBlurrer, MemoryTokenStore

REPO = Path(__file__).resolve().parents[3]
LABELS = Path(__file__).parent.parent / "fixtures" / "clips" / "door_labels.json"


def clips_dir() -> Path:
    """The local clips folder: FRIDGESENSE_CLIPS_DIR, or the repo's git-ignored tmp/."""
    return Path(os.environ.get("FRIDGESENSE_CLIPS_DIR") or REPO / "tmp")


class LabelError(ValueError):
    """The labels file is malformed; the message names the clip and the problem."""


@dataclass(frozen=True)
class Opening:
    """One door opening a person saw, in seconds from the clip start (None: still open at end)."""

    opened_s: float
    closed_s: float | None


def _time(clip: str, opening: dict, key: str, nullable: bool) -> float | None:
    value = opening.get(key)
    if value is None and nullable and key in opening:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise LabelError(f"{clip}: {key} must be a number of seconds")
    if value < 0:
        raise LabelError(f"{clip}: {key} must not be negative")
    return float(value)


def _openings(clip: str, entry: dict) -> list[Opening]:
    raw = entry.get("openings") if isinstance(entry, dict) else None
    if not isinstance(raw, list):
        raise LabelError(f"{clip}: openings must be a list")
    found = []
    for opening in raw:
        if not isinstance(opening, dict):
            raise LabelError(f"{clip}: each opening must be an object")
        opened = _time(clip, opening, "opened_s", nullable=False)
        closed = _time(clip, opening, "closed_s", nullable=True)
        if closed is not None and closed <= opened:
            raise LabelError(f"{clip}: closed_s must be after opened_s ({opened} -> {closed})")
        found.append(Opening(opened, closed))
    for before, after in zip(found, found[1:], strict=False):
        if before.closed_s is None:
            raise LabelError(f"{clip}: only the last opening may have closed_s = null")
        if after.opened_s < before.closed_s:
            raise LabelError(f"{clip}: openings overlap ({before} and {after})")
    return found


def load_labels(path: Path | str = LABELS) -> dict[str, list[Opening]]:
    """Clip file name -> its labelled openings (empty: the door never opened)."""
    data = json.loads(Path(path).read_text())
    clips = data.get("clips") if isinstance(data, dict) else None
    if not isinstance(clips, dict):
        raise LabelError(f"{path}: needs a top-level 'clips' object")
    return {clip: _openings(clip, entry) for clip, entry in clips.items()}


def expected_span(openings: list[Opening], duration_s: float) -> tuple[float, float] | None:
    """(open, close) the check should find: first open to last close; None close: clip end."""
    if not openings:
        return None
    close = openings[-1].closed_s
    return openings[0].opened_s, duration_s if close is None else close


EPOCH_MS = 1786715596000  # every clip's window starts here
NOW_S = EPOCH_MS / 1000
JPEG_QUALITY = 90
DOWNLOAD = rf"{API_BASE}/v1/devices/[^/]+/media/image/download"
MEDIA_HOST = "https://clip-camera.invalid"


class FrameSource(Protocol):
    """A clip's frames: `jpeg_at(t)` is the frame shown t seconds in, or None outside the clip."""

    duration_s: float

    def prepare(self, offsets_s: list[float]) -> None: ...

    def jpeg_at(self, offset_s: float) -> bytes | None: ...


def to_jpeg(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=JPEG_QUALITY)
    return buf.getvalue()


class ColourSource:
    """A stand-in clip of solid-colour frames: (start second, RGB) pairs, sorted by time."""

    def __init__(self, frames, duration_s: float, size: tuple[int, int] = (320, 180)):
        self.frames = list(frames)
        self.duration_s = duration_s
        self.size = size

    def prepare(self, offsets_s: list[float]) -> None:
        pass

    def jpeg_at(self, offset_s: float) -> bytes | None:
        if not 0 <= offset_s <= self.duration_s:
            return None
        i = bisect_right([t for t, _ in self.frames], offset_s) - 1
        return to_jpeg(Image.new("RGB", self.size, self.frames[max(i, 0)][1]))


def ring_client(http: httpx.Client) -> RingClient:
    """A Ring client with a fresh token, so it never refreshes."""
    tokens = Tokens(
        account_id="clip.account",
        access_token="clip",
        refresh_token="clip",
        expires_at=int(NOW_S) + 3600,
        link_status="linked",
    )
    return RingClient(http, MemoryTokenStore(tokens), OAuthClient(http, "c", "s"), lambda: NOW_S)


def clip_camera(router: respx.Router, source: FrameSource, start_ms: int) -> None:
    """Answer Ring's still download like the camera would, from the clip frame at t - start."""
    lock = threading.Lock()  # stills download in parallel; decoders are not thread-safe

    def download(request: httpx.Request) -> httpx.Response:
        ts = json.loads(request.content)["timestamp"]
        return httpx.Response(303, headers={"Location": f"{MEDIA_HOST}/{ts}"})

    def media(request: httpx.Request) -> httpx.Response:
        offset_s = (int(request.url.path.strip("/")) - start_ms) / 1000
        with lock:
            data = source.jpeg_at(offset_s)
        if data is None:
            return httpx.Response(404)
        return httpx.Response(200, content=data, headers={"Content-Type": "image/jpeg"})

    router.post(url__regex=DOWNLOAD).mock(side_effect=download)
    router.get(url__regex=rf"{MEDIA_HOST}/\d+").mock(side_effect=media)


class ClipUnreadable(Exception):
    """The clip file is not a video the decoder can read; the message names the file."""


class AvSource:
    """A clip decoded with PyAV. `prepare` decodes the given times in one pass and keeps JPEGs."""

    def __init__(self, path: Path):
        import av

        self.path = Path(path)
        self.jpegs: dict[int, bytes] = {}  # by offset in ms
        try:
            with av.open(str(self.path)) as container:
                stream = container.streams.video[0]
                self.size = (stream.width, stream.height)
                self.duration_s = container.duration / 1_000_000
        except (av.FFmpegError, IndexError, TypeError) as e:
            raise ClipUnreadable(f"{self.path.name}: not a readable video ({e})") from e

    def prepare(self, offsets_s: list[float]) -> None:
        """Decode the frame shown at each offset (the latest frame at or before it)."""
        import av

        wanted = sorted(
            {round(t * 1000) for t in offsets_s if 0 <= t <= self.duration_s} - self.jpegs.keys()
        )
        if not wanted:
            return
        try:
            with av.open(str(self.path)) as container:
                stream = container.streams.video[0]
                stream.thread_type = "AUTO"
                shown = None
                for frame in container.decode(stream):
                    while wanted and shown is not None and frame.time * 1000 > wanted[0]:
                        self.jpegs[wanted.pop(0)] = to_jpeg(shown.to_image())
                    if not wanted:
                        return
                    shown = frame
                for ms in wanted:  # past the last frame's start: it is still showing
                    self.jpegs[ms] = to_jpeg(shown.to_image())
        except av.FFmpegError as e:
            raise ClipUnreadable(f"{self.path.name}: not a readable video ({e})") from e

    def jpeg_at(self, offset_s: float) -> bytes | None:
        if not 0 <= offset_s <= self.duration_s:
            return None
        ms = round(offset_s * 1000)
        if ms not in self.jpegs:
            self.prepare([offset_s])
        return self.jpegs[ms]


ACCOUNT = "clip.account"
DEVICE = "clip.device"
TOLERANCE_STILLS = 1.5


def tolerance_s(duration_ms: int, interval_ms: int) -> float:
    """1.5 x the spacing of the stills the pipeline asks for (wider than the interval when
    a long window hits the still cap)."""
    spacing_ms = duration_ms / (still_count(duration_ms, interval_ms) + 1)
    return TOLERANCE_STILLS * max(interval_ms, spacing_ms) / 1000


def _secs(s: float) -> str:
    return f"{round(s, 2):g} s"


@dataclass
class ClipResult:
    """How the door check did on one clip. Times are seconds from the clip start."""

    clip: str
    expected: tuple[float, float] | None  # labelled open span
    detected: tuple[float, float] | None
    tolerance_s: float
    best_value: float
    threshold: float
    merged: bool = False  # several labelled openings, scored as one span
    still_offsets_s: list[float] = field(default_factory=list)
    trace: object = None  # the pipeline's DoorTrace, for dumping stills

    @property
    def verdict(self) -> str:
        if self.expected:
            return "TP" if self.detected else "FN"
        return "FP" if self.detected else "TN"

    @property
    def open_error_s(self) -> float | None:
        return self.detected[0] - self.expected[0] if self.verdict == "TP" else None

    @property
    def close_error_s(self) -> float | None:
        return self.detected[1] - self.expected[1] if self.verdict == "TP" else None

    @property
    def failures(self) -> list[str]:
        if self.verdict == "FN":
            return [
                f"{self.clip}: missed opening (best zone value {self.best_value:.3f}, "
                f"threshold {self.threshold:g})"
            ]
        if self.verdict == "FP":
            opened, closed = self.detected
            return [f"{self.clip}: false opening detected {opened:.1f} s to {closed:.1f} s"]
        found = []
        for what, i, error in (("open", 0, self.open_error_s), ("close", 1, self.close_error_s)):
            if error is not None and abs(error) > self.tolerance_s:
                found.append(
                    f"{self.clip}: {what} time labelled {self.expected[i]:.1f} s, "
                    f"detected {self.detected[i]:.1f} s ({error:+.1f} s, "
                    f"tolerance {_secs(self.tolerance_s)})"
                )
        return found

    @property
    def passed(self) -> bool:
        return not self.failures


def score(
    clip: str,
    openings: list[Opening],
    duration_s: float,
    detected: tuple[float, float] | None,
    tolerance: float,
    best_value: float,
    threshold: float,
) -> ClipResult:
    return ClipResult(
        clip=clip,
        expected=expected_span(openings, duration_s),
        detected=detected,
        tolerance_s=tolerance,
        best_value=best_value,
        threshold=threshold,
        merged=len(openings) > 1,
    )


@contextmanager
def offline_camera(source: FrameSource, start_ms: int) -> Iterator[tuple[RingClient, httpx.Client]]:
    """Ring is the clip camera, S3 and DynamoDB are moto, and any other request raises."""
    import boto3
    from moto import mock_aws

    env = {
        "AWS_DEFAULT_REGION": "us-east-1",
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "TABLE_NAME": TABLE,
        "STILLS_BUCKET": BUCKET,
    }
    with mock.patch.dict(os.environ, env), mock_aws():
        os.environ.pop("AWS_PROFILE", None)
        boto3.client("s3").create_bucket(Bucket=BUCKET)
        boto3.client("dynamodb").create_table(
            TableName=TABLE,
            KeySchema=[
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "pk", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        with (
            respx.mock(assert_all_mocked=True, assert_all_called=False) as router,
            httpx.Client() as http,
        ):
            clip_camera(router, source, start_ms)
            yield ring_client(http), http


class _Capture:
    """A trace writer that keeps the door check's trace in memory."""

    trace = None

    def door(self, state, trace) -> None:
        self.trace = trace


def _offset_s(iso: str) -> float:
    return datetime.fromisoformat(iso).timestamp() - EPOCH_MS / 1000


def evaluate_clip(
    clip: str,
    source: FrameSource,
    openings: list[Opening],
    check: DoorCheck | None = None,
    interval_ms: int | None = None,
) -> ClipResult:
    """Run the unchanged fetch-stills task on a clip and score it against its labels.

    The check and interval default to DOOR_ZONES, DOOR_THRESHOLD and STILL_INTERVAL_MS.
    """
    import boto3

    from fridgesense.table import FridgeTable

    if check is None:
        check = DoorCheck.from_config(
            os.environ.get("DOOR_ZONES"), os.environ.get("DOOR_THRESHOLD")
        )
    if interval_ms is None:
        interval_ms = parse_interval(os.environ.get("STILL_INTERVAL_MS"))
    duration_ms = round(source.duration_s * 1000)
    start, end = EPOCH_MS, EPOCH_MS + duration_ms
    times = still_times(start, end, still_count(duration_ms, interval_ms))
    offsets = [(t - start) / 1000 for t in times]
    source.prepare(offsets)
    state = {
        "account_id": ACCOUNT,
        "device_id": DEVICE,
        "timestamp_ms": start,
        "request_id": f"clip-{clip}",
        "window": {
            "status": "ready",
            "start_ms": start,
            "end_ms": end,
            "ring_event_id": f"clip-{clip}",
        },
    }
    capture = _Capture()
    with offline_camera(source, start) as (ring, http):
        fetch_stills(
            ring,
            http,
            boto3.client("s3"),
            FridgeTable(),
            BUCKET,
            check,
            FakeBlurrer(),
            state,
            sleep=lambda s: None,
            interval_ms=interval_ms,
            writer=capture,
        )
    trace = capture.trace
    results = list(trace.results().values())
    best = check.best(results) if results else None
    detected = None
    if trace.open_span and trace.opened_at:
        detected = (_offset_s(trace.opened_at), _offset_s(trace.closed_at))
    result = score(
        clip,
        openings,
        source.duration_s,
        detected,
        tolerance_s(duration_ms, interval_ms),
        best.value if best else 0.0,
        best.threshold if best else check.threshold,
    )
    result.still_offsets_s = offsets
    result.trace = trace
    return result


NO_DECODER = "video decoder not installed: run `uv sync --group clips`"


def decoder_available() -> bool:
    import importlib.util

    return importlib.util.find_spec("av") is not None


def clip_cases(labels: Path = LABELS, folder: Path | None = None, have_decoder: bool | None = None):
    """One pytest param per labelled clip, skipped (with the reason) when it cannot run."""
    import pytest

    if not Path(labels).exists():
        return [
            pytest.param(
                None,
                None,
                id="no-labels",
                marks=pytest.mark.skip(reason=f"no labels file at {labels}"),
            )
        ]
    folder = clips_dir() if folder is None else Path(folder)
    have_decoder = decoder_available() if have_decoder is None else have_decoder
    cases = []
    for clip, openings in load_labels(labels).items():
        if not have_decoder:
            reason = NO_DECODER
        elif not folder.is_dir():
            reason = f"clips folder {folder} not found"
        elif not (folder / clip).is_file():
            reason = f"{clip} not in {folder}"
        else:
            reason = None
        marks = [pytest.mark.skip(reason=reason)] if reason else []
        cases.append(pytest.param(clip, openings, id=clip, marks=marks))
    return cases
