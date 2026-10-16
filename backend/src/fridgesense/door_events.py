"""Door-event workflow steps: event window, stills and the door-open check."""

import io
import logging
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from PIL import Image, ImageChops, ImageStat

from fridgesense.faces import FaceBlurrer
from fridgesense.logs import log_event
from fridgesense.oauth import OAuthRejected, OAuthUnavailable
from fridgesense.ring import RingAuthError, RingClient
from fridgesense.table import FridgeTable, TransactionConflict, account_pk

MATCH_TOLERANCE_MS = 10_000
MAX_WINDOW_CHECKS = 6
FALLBACK_DURATION_MS = 30_000


def _ms(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def find_window(ring: RingClient, state: dict) -> dict:
    """Find the motion event's start and end in Ring's history.

    Returns the run state with `window` set to ready or pending; after
    MAX_WINDOW_CHECKS pending checks it falls back to timestamp + 30 s.
    """
    attempt = int(state.get("attempt", 1))
    ts = int(state["timestamp_ms"])
    match = _matching_event(ring, state["device_id"], ts)
    if match is not None:
        window = {"status": "ready", **match}
    elif attempt >= MAX_WINDOW_CHECKS:
        log_event("window_fallback", logging.WARNING, device_id=state["device_id"], timestamp_ms=ts)
        window = {
            "status": "ready",
            "start_ms": ts,
            "end_ms": ts + FALLBACK_DURATION_MS,
            "ring_event_id": None,
        }
    else:
        window = {"status": "pending"}
    return {**state, "window": window, "attempt": attempt + 1}


def _matching_event(ring: RingClient, device_id: str, ts: int) -> dict | None:
    try:
        resp = ring.get(f"/v1/history/devices/{device_id}/events", params={"event_types": "motion"})
    except (httpx.HTTPError, RingAuthError, OAuthRejected, OAuthUnavailable) as e:
        log_event("history_unavailable", logging.WARNING, error=type(e).__name__)
        return None
    if resp.status_code != 200:
        log_event("history_unavailable", logging.WARNING, status=resp.status_code)
        return None
    best = None
    for event in resp.json().get("data", []):
        attrs = event.get("attributes", {})
        start = _ms(attrs.get("start"))
        if start is None or abs(start - ts) > MATCH_TOLERANCE_MS:
            continue
        if best is None or abs(start - ts) < abs(best[0] - ts):
            best = (start, _ms(attrs.get("end")), event.get("id"))
    if best is None or best[1] is None:
        return None
    return {"start_ms": best[0], "end_ms": best[1], "ring_event_id": best[2]}


STILL_COUNT = 4  # fewest stills per window
MAX_STILLS = 30
STILL_INTERVAL_MS = 1000
DOWNLOAD_WORKERS = 8

Box = tuple[float, float, float, float]

# Measured on the fridge camera (2026-10-15 clip): French doors, then the two drawers.
DEFAULT_ZONES: tuple[Box, ...] = ((0.38, 0.32, 0.21, 0.30), (0.455, 0.60, 0.12, 0.18))
DEFAULT_THRESHOLD = 0.02
MIN_CHROMA = 60  # max(R,G,B) - min(R,G,B): grey steel, white and wood stay below this
MIN_PEAK = 100  # brightest channel: keeps dark saturated clothing (navy) out


def still_times(start_ms: int, end_ms: int, count: int = STILL_COUNT) -> list[int]:
    """Evenly spaced times inside the window: 1/5, 2/5, 3/5, 4/5 for four stills."""
    span = end_ms - start_ms
    return [start_ms + span * k // (count + 1) for k in range(1, count + 1)]


def still_count(span_ms: int, interval_ms: int = STILL_INTERVAL_MS) -> int:
    """About one still per interval across the window, 4 to 30 of them."""
    return max(STILL_COUNT, min(MAX_STILLS, span_ms // interval_ms))


def parse_interval(setting: str | None) -> int:
    """STILL_INTERVAL_MS: whole milliseconds between stills, default 1000."""
    if not setting or not setting.strip():
        return STILL_INTERVAL_MS
    try:
        value = int(setting)
    except ValueError:
        value = 0
    if value <= 0:
        raise ValueError("STILL_INTERVAL_MS must be a whole number of milliseconds above 0")
    return value


def open_span(scores: list[float], threshold: float) -> list[int] | None:
    """Indices from the first open still through the first still after the last open one."""
    opened = [i for i, score in enumerate(scores) if score >= threshold]
    if not opened:
        return None
    end = min(opened[-1] + 1, len(scores) - 1)
    return list(range(opened[0], end + 1))


def pick(span: list[int], count: int = STILL_COUNT) -> list[int]:
    """Up to `count` evenly spaced items of `span`, always including its first and last."""
    if len(span) <= count:
        return list(span)
    n = len(span)
    return [span[round(i * (n - 1) / (count - 1))] for i in range(count)]


def parse_box(text: str, setting: str) -> Box:
    """`x,y,width,height` fractions that must lie inside the image; errors name the setting."""
    parts = tuple(float(v) for v in text.split(","))
    if len(parts) != 4:
        raise ValueError(f"{setting} needs four numbers per box: x,y,width,height")
    x, y, bw, bh = parts
    if min(parts) < 0 or bw <= 0 or bh <= 0 or x + bw > 1 or y + bh > 1:
        raise ValueError(f"{setting} boxes must lie inside the image (fractions 0-1)")
    return parts


def _crop_box(img: Image.Image, box: Box) -> Image.Image:
    w, h = img.size
    x, y, bw, bh = box
    return img.crop((round(x * w), round(y * h), round((x + bw) * w), round((y + bh) * h)))


def _colorful(zone: Image.Image) -> float:
    r, g, b = zone.split()
    peak = ImageChops.lighter(ImageChops.lighter(r, g), b)
    low = ImageChops.darker(ImageChops.darker(r, g), b)
    chroma = ImageChops.subtract(peak, low)
    colourful = ImageChops.multiply(
        chroma.point(lambda v: 255 if v > MIN_CHROMA else 0),
        peak.point(lambda v: 255 if v > MIN_PEAK else 0),
    )
    return ImageStat.Stat(colourful).mean[0] / 255


def _open_rgb(still: bytes | Image.Image) -> Image.Image:
    if isinstance(still, Image.Image):
        return still
    return Image.open(io.BytesIO(still)).convert("RGB")


def colorful_fraction(jpeg_bytes: bytes, box: Box) -> float:
    """Share (0-1) of colourful pixels in a box given as fractions (x, y, width, height).

    The lit fridge interior and its food are colourful; closed steel doors are grey
    at any ambient light level.
    """
    return _colorful(_crop_box(_open_rgb(jpeg_bytes), box))


FEATURES = ("color", "change", "brightness")  # also the tie order when setup picks one
BASELINE_SIZE = (32, 32)


def _thumb(zone: Image.Image) -> bytes:
    return zone.resize(BASELINE_SIZE, Image.Resampling.BOX).tobytes()


def baseline_of(stills: list[bytes], box: Box) -> bytes:
    """The per-pixel mean of the stills' zone at 32x32 RGB: what "closed" looks like."""
    thumbs = [_thumb(_crop_box(_open_rgb(s), box)) for s in stills]
    return bytes(round(sum(px) / len(thumbs)) for px in zip(*thumbs, strict=True))


def measure(
    still: bytes | Image.Image, box: Box, feature: str, baseline: bytes | None = None
) -> float:
    """One feature (0-1) of a zone: colorful fraction, mean luminance, or change from a baseline."""
    zone = _crop_box(_open_rgb(still), box)
    if feature == "color":
        return _colorful(zone)
    if feature == "brightness":
        return ImageStat.Stat(zone.convert("L")).mean[0] / 255
    if feature == "change":
        if baseline is None:
            raise ValueError("the change feature needs a baseline")
        thumb = _thumb(zone)
        return sum(abs(a - b) for a, b in zip(thumb, baseline, strict=True)) / len(thumb) / 255
    raise ValueError(f"unknown feature: {feature!r}")


@dataclass(frozen=True)
class ZoneRule:
    """A zone is open when its feature is at or past the threshold in the rule's direction."""

    box: Box
    feature: str = "color"
    direction: str = "above"
    threshold: float = DEFAULT_THRESHOLD
    baseline: bytes | None = None

    def value(self, still: bytes | Image.Image) -> float:
        return measure(still, self.box, self.feature, self.baseline)

    def excess(self, value: float) -> float:
        """How far past the threshold (negative: short of it)."""
        return value - self.threshold if self.direction == "above" else self.threshold - value

    def is_open(self, value: float) -> bool:
        return self.excess(value) >= 0


@dataclass(frozen=True)
class StillResult:
    is_open: bool
    value: float  # the best zone's feature value
    zone: int  # 1-based
    feature: str
    threshold: float


CROP_JPEG_QUALITY = 95


def parse_crop(setting: str | None) -> Box | None:
    """The STILL_CROP box, or None when unset (stills are stored as downloaded)."""
    if not setting or not setting.strip():
        return None
    return parse_box(setting, "STILL_CROP")


def crop_still(jpeg_bytes: bytes, box: Box | None) -> bytes:
    """Cut a still down to `box` (e.g. the strip the camera's privacy mask leaves visible)."""
    if box is None:
        return jpeg_bytes
    buf = io.BytesIO()
    _crop_box(Image.open(io.BytesIO(jpeg_bytes)).convert("RGB"), box).save(
        buf, format="JPEG", quality=CROP_JPEG_QUALITY
    )
    return buf.getvalue()


@dataclass(frozen=True)
class DoorCheck:
    zones: tuple[Box, ...] = DEFAULT_ZONES
    threshold: float = DEFAULT_THRESHOLD
    rules: tuple[ZoneRule, ...] = ()  # from setup; without them, colour rules from zones/threshold
    source: str = "default"

    def __post_init__(self):
        if not self.rules:
            rules = tuple(ZoneRule(z, "color", "above", self.threshold) for z in self.zones)
            object.__setattr__(self, "rules", rules)

    @classmethod
    def from_config(cls, zones: str | None, threshold: str | None) -> "DoorCheck":
        """Zones as `x,y,w,h;x,y,w,h` (fractions of the uncropped still)."""
        parsed = DEFAULT_ZONES
        if zones:
            parsed = tuple(parse_box(z, "DOOR_ZONES") for z in zones.split(";") if z.strip())
            if not parsed:
                raise ValueError("DOOR_ZONES needs at least one zone: x,y,width,height")
        return cls(zones=parsed, threshold=float(threshold) if threshold else DEFAULT_THRESHOLD)

    def result(self, still: bytes) -> StillResult:
        """The still's best zone: the one furthest past (or closest to) its threshold."""
        img = _open_rgb(still)
        best = max(
            (
                (rule.excess(v := rule.value(img)), v, n, rule)
                for n, rule in enumerate(self.rules, 1)
            ),
            key=lambda t: t[0],
        )
        excess, value, zone, rule = best
        return StillResult(excess >= 0, value, zone, rule.feature, rule.threshold)

    def results(self, stills: list[bytes]) -> list[StillResult]:
        return [self.result(s) for s in stills]

    def best(self, results: list[StillResult]) -> StillResult:
        """The still furthest past (or closest to) its zone's threshold."""
        return max(results, key=lambda r: self.rules[r.zone - 1].excess(r.value))

    def evaluate(self, stills: list[bytes]) -> tuple[bool, float, int]:
        """(door open?, best still's value, its 1-based zone) over all stills."""
        best = self.best(self.results(stills))
        return best.is_open, best.value, best.zone


STILL_ATTEMPTS = 3
STILL_RETRY_DELAYS_S = (3, 6)
DENSE_RETRY_DELAYS_S = (1, 2)  # many stills per window: shorter waits keep the task under 90 s
NOT_READY = {416, 425}


def stills_prefix(account_id: str, device_id: str, start_ms: int) -> str:
    return f"accounts/{account_id}/devices/{device_id}/events/{start_ms}/"


def download_stills(
    ring: RingClient,
    http: httpx.Client,
    state: dict,
    sleep: Callable[[float], None] = time.sleep,
    interval_ms: int = STILL_INTERVAL_MS,
) -> list[tuple[int, bytes]]:
    """Download the stills for the window into memory: (still number, raw bytes) pairs.

    Nothing is stored here; raw stills only feed the door check and face detection.
    """
    window = state["window"]
    count = still_count(window["end_ms"] - window["start_ms"], interval_ms)
    times = still_times(window["start_ms"], window["end_ms"], count)
    delays = STILL_RETRY_DELAYS_S if count <= STILL_COUNT else DENSE_RETRY_DELAYS_S

    def fetch(ts: int) -> bytes | None:
        return _download_still(ring, http, state["device_id"], ts, sleep, delays)

    if count <= STILL_COUNT:
        results = [fetch(ts) for ts in times]
    else:  # many stills: download in parallel to stay well inside the task timeout
        with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as pool:
            results = list(pool.map(fetch, times))
    return [(n, data) for n, data in enumerate(results, start=1) if data is not None]


def store_blurred_stills(
    s3, bucket: str, blurrer: FaceBlurrer, state: dict, raw: list[tuple[int, bytes]]
) -> list[tuple[str, bytes]]:
    """Blur faces in each still and store it in S3.

    Returns (key, blurred bytes) pairs. Only blurred stills are ever stored.
    """
    prefix = stills_prefix(state["account_id"], state["device_id"], state["window"]["start_ms"])
    saved = []
    for n, data in raw:
        blurred = blurrer.blur(
            data, {"account_id": state["account_id"], "device_id": state["device_id"], "still": n}
        )
        if blurred is None:
            continue  # face detection failed: never store an unblurred still
        key = f"{prefix}still-{n}.jpg"
        s3.put_object(Bucket=bucket, Key=key, Body=blurred, ContentType="image/jpeg")
        saved.append((key, blurred))
    return saved


def _download_still(
    ring: RingClient,
    http: httpx.Client,
    device_id: str,
    ts: int,
    sleep: Callable[[float], None],
    delays: tuple[int, ...] = STILL_RETRY_DELAYS_S,
) -> bytes | None:
    body = {"type": "at_timestamp", "timestamp": ts, "image_options": {"format": "jpeg"}}
    for attempt in range(STILL_ATTEMPTS):
        try:
            resp = ring.post(f"/v1/devices/{device_id}/media/image/download", json=body)
            if resp.is_redirect and resp.headers.get("location"):
                # Pre-signed link: fetched without the Ring token.
                media = http.get(resp.headers["location"], timeout=10.0)
                if media.status_code == 200:
                    return media.content
                status = media.status_code
            else:
                status = resp.status_code
        except (httpx.HTTPError, RingAuthError, OAuthRejected, OAuthUnavailable) as e:
            log_event("still_failed", logging.WARNING, timestamp=ts, error=type(e).__name__)
            return None
        if status not in NOT_READY or attempt == len(delays):
            log_event("still_missing", logging.WARNING, timestamp=ts, status=status)
            return None
        sleep(delays[attempt])
    return None


MIN_STILLS = 2


def iso_utc(ms: int) -> str:
    dt = datetime.fromtimestamp(ms // 1000, UTC)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ms % 1000:03d}Z"


def fetch_stills(
    ring: RingClient,
    http: httpx.Client,
    s3,
    table: FridgeTable,
    bucket: str,
    check: DoorCheck,
    blurrer: FaceBlurrer,
    state: dict,
    sleep: Callable[[float], None] = time.sleep,
    crop: Box | None = None,
    interval_ms: int = STILL_INTERVAL_MS,
) -> dict:
    """Download stills, run the door check, and claim + record the door event.

    The door check runs on the raw, uncropped stills in memory. For a door opening, up to
    4 stills from the open span are cropped to `crop`, pay for face detection, and have
    their blurred stills stored; the span also gives the event's open and close times.
    Outcomes: door_open (go on to analysis), not_door, no_media, duplicate.
    """
    account_id, device_id, window = state["account_id"], state["device_id"], state["window"]
    raw = download_stills(ring, http, state, sleep, interval_ms)
    count = still_count(window["end_ms"] - window["start_ms"], interval_ms)
    times = still_times(window["start_ms"], window["end_ms"], count)
    opened_ms, closed_ms = window["start_ms"], window["end_ms"]
    still_keys: list[str] = []
    status = "no_media"

    if len(raw) >= MIN_STILLS:
        results = check.results([data for _, data in raw])
        span = open_span([1.0 if r.is_open else 0.0 for r in results], 1.0)
        if span is None:
            best = check.best(results)
            log_event(
                "motion_not_door",
                account_id=account_id,
                device_id=device_id,
                score=round(best.value, 3),
                zone=best.zone,
                threshold=best.threshold,
            )
            return {**state, "outcome": "not_door", "score": round(best.value, 3)}
        opened_ms = times[raw[span[0]][0] - 1]
        if not results[span[-1]].is_open:  # the first closed still after the opening
            closed_ms = times[raw[span[-1]][0] - 1]
        picked = [(k, crop_still(raw[i][1], crop)) for k, i in enumerate(pick(span), start=1)]
        stills = store_blurred_stills(s3, bucket, blurrer, state, picked)
        still_keys = [k for k, _ in stills]
        if len(stills) >= MIN_STILLS:
            status = "analyzing"

    door_sk = f"DOOR#{iso_utc(window['start_ms'])}#{device_id}"
    claim = window["ring_event_id"] or f"ts-{state['timestamp_ms']}"
    pk = account_pk(account_id)
    event = {
        "pk": pk,
        "sk": door_sk,
        "device_id": device_id,
        "ring_event_id": window["ring_event_id"],
        "opened_at": iso_utc(opened_ms),
        "closed_at": iso_utc(closed_ms),
        "duration_s": round((closed_ms - opened_ms) / 1000),
        "still_keys": still_keys,
        "status": status,
    }
    try:
        table.transact(
            [
                {
                    "Put": {
                        "Item": {
                            "pk": pk,
                            "sk": f"RINGEVENT#{device_id}#{claim}",
                            "door_sk": door_sk,
                        },
                        "ConditionExpression": "attribute_not_exists(sk)",
                    }
                },
                {"Put": {"Item": event}},
            ]
        )
    except TransactionConflict as e:
        if e.reasons and e.reasons[0] == "ConditionalCheckFailed":
            log_event("door_event_duplicate", account_id=account_id, ring_event=claim)
            return {**state, "outcome": "duplicate"}
        raise
    outcome = "door_open" if status == "analyzing" else "no_media"
    log_event("door_event_recorded", account_id=account_id, door_sk=door_sk, outcome=outcome)
    return {**state, "outcome": outcome, "door_sk": door_sk, "still_keys": still_keys}
