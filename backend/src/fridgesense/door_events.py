"""Door-event workflow steps: event window, stills and the door-open check."""

import io
import logging
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
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
DEFAULT_THRESHOLD = 0.01
MIN_CHROMA = 60  # max(R,G,B) - min(R,G,B): grey steel, white and wood stay below this
MIN_PEAK = 100  # brightest channel: keeps dark saturated clothing (navy) out
# Fridge light: stricter than "colourful". Daylight tints the steel doors a pale blue
# (e.g. 110,150,200) that passes the colour test; the LED-lit interior is a deep blue.
BLUE_MIN_CHROMA = 100
BLUE_MIN_PEAK = 120
BLUE_MIN_LEAD = 60  # B - max(R,G): the LED-lit interior is blue, food held in front is warm


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


SUSPECT_MIN_FRAMES = 10
SUSPECT_OPEN_SHARE = 0.9


def is_suspect(opened: list[bool], zones_source: str) -> bool:
    """A clip checked with setup rules that reads open at both bookends, or nearly
    throughout: a recording starts and ends with the door closed, so the rules are off."""
    if zones_source not in ("setup", "tuned") or len(opened) < SUSPECT_MIN_FRAMES:
        return False
    return (opened[0] and opened[-1]) or sum(opened) / len(opened) >= SUSPECT_OPEN_SHARE


def pick(span: list[int], count: int = STILL_COUNT) -> list[int]:
    """Up to `count` evenly spaced items of `span`, always including its first and last."""
    if len(span) <= count:
        return list(span)
    n = len(span)
    return [span[round(i * (n - 1) / (count - 1))] for i in range(count)]


MAX_VIDEO_FRAMES = 40  # ~288 tokens each at Nova 2 Lite's 672x672 video frames


def video_frame_indexes(span: list[int]) -> tuple[list[int], int]:
    """Frames for the analysis video: the one before the open span (if any) through the span,
    every `step`-th one so that at most MAX_VIDEO_FRAMES remain. Returns (indexes, step)."""
    frames = list(range(max(span[0] - 1, 0), span[-1] + 1))
    step = -(-len(frames) // MAX_VIDEO_FRAMES)  # ceil
    return frames[::step], step


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


def _colorful_mask(
    zone: Image.Image, min_chroma: int = MIN_CHROMA, min_peak: int = MIN_PEAK
) -> Image.Image:
    r, g, b = zone.split()
    peak = ImageChops.lighter(ImageChops.lighter(r, g), b)
    low = ImageChops.darker(ImageChops.darker(r, g), b)
    chroma = ImageChops.subtract(peak, low)
    return ImageChops.multiply(
        chroma.point(lambda v: 255 if v > min_chroma else 0),
        peak.point(lambda v: 255 if v > min_peak else 0),
    )


def _colorful(zone: Image.Image) -> float:
    return ImageStat.Stat(_colorful_mask(zone)).mean[0] / 255


def _blue_lit(zone: Image.Image) -> float:
    """Share of strongly colourful pixels whose blue clearly leads red and green: the lit
    fridge interior."""
    r, g, b = zone.split()
    lead = ImageChops.subtract(b, ImageChops.lighter(r, g))
    blue = lead.point(lambda v: 255 if v > BLUE_MIN_LEAD else 0)
    mask = _colorful_mask(zone, BLUE_MIN_CHROMA, BLUE_MIN_PEAK)
    return ImageStat.Stat(ImageChops.multiply(mask, blue)).mean[0] / 255


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


FEATURES = ("blue", "color", "change", "brightness")  # also the tie order when setup picks one
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
    """One feature (0-1) of a zone: colorful or blue-lit fraction, mean luminance, or change
    from a baseline."""
    zone = _crop_box(_open_rgb(still), box)
    if feature == "color":
        return _colorful(zone)
    if feature == "blue":
        return _blue_lit(zone)
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
    margin: float | None = None  # from setup: how far apart open and closed references were

    def value(self, still: bytes | Image.Image) -> float:
        return measure(still, self.box, self.feature, self.baseline)

    def excess(self, value: float) -> float:
        """How far past the threshold (negative: short of it)."""
        return value - self.threshold if self.direction == "above" else self.threshold - value

    def is_open(self, value: float) -> bool:
        return self.excess(value) >= 0


@dataclass(frozen=True)
class ZoneValue:
    """One zone's feature value in one still, against that zone's threshold."""

    zone: int  # 1-based
    value: float
    threshold: float
    open: bool
    excess: float


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
    rules: tuple[ZoneRule, ...] = ()  # from setup; without them, blue rules from zones/threshold
    source: str = "default"
    ran_at: str | None = None  # when setup ran

    def __post_init__(self):
        if not self.rules:
            rules = tuple(ZoneRule(z, "blue", "above", self.threshold) for z in self.zones)
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

    def zone_values(self, still: bytes | Image.Image) -> list[ZoneValue]:
        """Every zone's value in the still, with that zone's verdict."""
        img = _open_rgb(still)
        values = []
        for n, rule in enumerate(self.rules, 1):
            value = rule.value(img)
            excess = rule.excess(value)
            values.append(ZoneValue(n, value, rule.threshold, excess >= 0, excess))
        return values

    def result_of(self, values: list[ZoneValue]) -> StillResult:
        """The best zone: the one furthest past (or closest to) its threshold."""
        best = max(values, key=lambda v: v.excess)
        rule = self.rules[best.zone - 1]
        return StillResult(best.open, best.value, best.zone, rule.feature, rule.threshold)

    def result(self, still: bytes) -> StillResult:
        """The still's best zone: the one furthest past (or closest to) its threshold."""
        return self.result_of(self.zone_values(still))

    def results(self, stills: list[bytes]) -> list[StillResult]:
        return [self.result(s) for s in stills]

    def best(self, results: list[StillResult]) -> StillResult:
        """The still furthest past (or closest to) its zone's threshold."""
        return max(results, key=lambda r: self.rules[r.zone - 1].excess(r.value))

    def shifted(self, dx: float, dy: float) -> "DoorCheck":
        """The same rules with every zone moved by (dx, dy), kept inside the image."""
        if not dx and not dy:
            return self
        from fridgesense.alignment import shift_box  # alignment imports this module

        rules = tuple(replace(r, box=shift_box(r.box, dx, dy)) for r in self.rules)
        return replace(self, rules=rules)

    def fridge_light(self, threshold: float) -> "DoorCheck":
        """The same zone boxes, each judged by the fridge light alone (blue above `threshold`)."""
        rules = tuple(ZoneRule(r.box, "blue", "above", threshold) for r in self.rules)
        return replace(self, rules=rules, source="fallback")

    def evaluate(self, stills: list[bytes]) -> tuple[bool, float, int]:
        """(door open?, best still's value, its 1-based zone) over all stills."""
        best = self.best(self.results(stills))
        return best.is_open, best.value, best.zone


STILL_RETRY_DELAYS_S = (3, 6)
DENSE_RETRY_DELAYS_S = (1, 2)  # many stills per window: shorter waits keep the task under 90 s
NOT_READY = {416, 425}


def stills_prefix(account_id: str, device_id: str, start_ms: int) -> str:
    return f"accounts/{account_id}/devices/{device_id}/events/{start_ms}/"


@dataclass(frozen=True)
class Downloaded:
    """One requested still: its bytes, or the last HTTP status (None when Ring or OAuth failed)."""

    n: int  # 1-based
    at_ms: int
    data: bytes | None
    status: int | None = None


def download_all_stills(
    ring: RingClient,
    http: httpx.Client,
    state: dict,
    sleep: Callable[[float], None] = time.sleep,
    interval_ms: int = STILL_INTERVAL_MS,
) -> list[Downloaded]:
    """Every still requested for the window, downloaded into memory or with why it is missing."""
    window = state["window"]
    count = still_count(window["end_ms"] - window["start_ms"], interval_ms)
    times = still_times(window["start_ms"], window["end_ms"], count)
    delays = STILL_RETRY_DELAYS_S if count <= STILL_COUNT else DENSE_RETRY_DELAYS_S

    def fetch(ts: int) -> tuple[bytes | None, int | None]:
        return fetch_still(ring, http, state["device_id"], ts, sleep, delays)

    if count <= STILL_COUNT:
        results = [fetch(ts) for ts in times]
    else:  # many stills: download in parallel to stay well inside the task timeout
        with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as pool:
            results = list(pool.map(fetch, times))
    return [
        Downloaded(n, ts, data, status)
        for n, (ts, (data, status)) in enumerate(zip(times, results, strict=True), start=1)
    ]


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
    stills = download_all_stills(ring, http, state, sleep, interval_ms)
    return [(s.n, s.data) for s in stills if s.data is not None]


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


def fetch_still(
    ring: RingClient,
    http: httpx.Client,
    device_id: str,
    ts: int,
    sleep: Callable[[float], None],
    delays: tuple[int, ...] = STILL_RETRY_DELAYS_S,
) -> tuple[bytes | None, int | None]:
    """(JPEG, None), or (None, the last HTTP status) — status None when Ring or OAuth failed.

    A still that is not ready yet is asked for again after each delay in `delays`.
    """
    body = {"type": "at_timestamp", "timestamp": ts, "image_options": {"format": "jpeg"}}
    for attempt in range(len(delays) + 1):
        try:
            resp = ring.post(f"/v1/devices/{device_id}/media/image/download", json=body)
            if resp.is_redirect and resp.headers.get("location"):
                # Pre-signed link: fetched without the Ring token.
                media = http.get(resp.headers["location"], timeout=10.0)
                if media.status_code == 200:
                    return media.content, None
                status = media.status_code
            else:
                status = resp.status_code
        except (httpx.HTTPError, RingAuthError, OAuthRejected, OAuthUnavailable) as e:
            log_event("still_failed", logging.WARNING, timestamp=ts, error=type(e).__name__)
            return None, None
        if status not in NOT_READY or attempt == len(delays):
            log_event("still_missing", logging.WARNING, timestamp=ts, status=status)
            return None, status
        sleep(delays[attempt])
    return None, None


MIN_STILLS = 2
FRAME_JPEG_QUALITY = 90


def _frame_jpeg(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=FRAME_JPEG_QUALITY)
    return buf.getvalue()


def clip_frames_checked(
    ring: RingClient,
    http: httpx.Client,
    check: "DoorCheck",
    state: dict,
    interval_ms: int,
    sleep: Callable[[float], None],
    clip_dir=None,
    keep: list[Path] | None = None,
) -> tuple[list[Downloaded], list[list["ZoneValue"]]]:
    """The event clip's frames every `interval_ms` (as JPEG `Downloaded`s) and their zone values.

    Each frame is scored as it is decoded, so a long clip never sits in memory decoded.
    The temp clip file is deleted whatever happens, unless it decoded and `keep` is given:
    then it is appended to `keep` and the caller deletes it. Raises ClipUnavailable.
    """
    from fridgesense import clip_frames

    window = state["window"]
    started = time.monotonic()
    path = clip_frames.download_clip(
        ring,
        http,
        state["device_id"],
        window["start_ms"],
        window["end_ms"] - window["start_ms"],
        sleep,
        directory=clip_dir,
    )
    downloaded_ms = round((time.monotonic() - started) * 1000)
    frames, values = [], []
    try:
        for n, (offset, img) in enumerate(clip_frames.sample_frames(path, interval_ms), start=1):
            values.append(check.zone_values(img))
            frames.append(Downloaded(n, window["start_ms"] + offset, _frame_jpeg(img)))
        clip_bytes = path.stat().st_size
        if keep is not None:
            keep.append(path)
    finally:
        if keep is None or path not in keep:
            path.unlink(missing_ok=True)
    log_event(
        "clip_frames",
        device_id=state["device_id"],
        frames=len(frames),
        clip_bytes=clip_bytes,
        clip_download_ms=downloaded_ms,
        clip_decode_ms=round((time.monotonic() - started) * 1000) - downloaded_ms,
    )
    return frames, values


def _device_check(
    default: "DoorCheck",
    setup_for: Callable[[str, str], "DoorCheck | None"] | None,
    account_id: str,
    device_id: str,
) -> "DoorCheck":
    """The device's setup rules if setup ran; otherwise (or if the lookup fails) the default."""
    if setup_for is None:
        return default
    try:
        found = setup_for(account_id, device_id)
    except Exception as e:  # a table hiccup must not drop a door opening
        log_event(
            "door_setup_unavailable", logging.WARNING, device_id=device_id, error=type(e).__name__
        )
        return default
    return found or default


@dataclass(frozen=True)
class FollowPlan:
    """What the door check needs to follow the camera: the closed anchor and the stored shift,
    plus the anchor's visible map and the setup's named zones for spotting a mask change."""

    anchor: bytes
    dx: float
    dy: float
    anchor_visible: bytes | None = None
    zones: tuple[tuple[str, Box], ...] = ()


def _follow_plan(
    table: FridgeTable, account_id: str, device_id: str, check: "DoorCheck"
) -> FollowPlan | None:
    """None for default rules, a setup made before anchors existed, or a table hiccup."""
    if check.source == "default":
        return None
    from fridgesense import alignment, door_calibration  # both import this module

    try:
        anchor = door_calibration.load_anchor(table, account_id, device_id)
        if anchor is None:
            return None
        stored = alignment.load_alignment(table, account_id, device_id)
        visible = door_calibration.load_anchor_visible(table, account_id, device_id)
        setup = door_calibration.load_setup(table, account_id, device_id)
    except Exception as e:  # a table hiccup must not drop a door opening
        log_event(
            "door_alignment_unavailable",
            logging.WARNING,
            device_id=device_id,
            error=type(e).__name__,
        )
        return None
    zones = tuple((z.name, z.box) for z in setup.zones) if setup else ()
    return FollowPlan(
        anchor, stored.dx if stored else 0.0, stored.dy if stored else 0.0, visible, zones
    )


def _align(table, account_id, device_id, plan: FollowPlan, first, last, window):
    """Line the bookends up with the anchor and store the result; None if that fails."""
    from fridgesense import alignment

    try:
        aligned = alignment.align_event(
            table,
            account_id,
            device_id,
            plan.anchor,
            first,
            last,
            window["start_ms"],
            plan.anchor_visible,
        )
    except Exception as e:
        log_event(
            "door_alignment_unavailable",
            logging.WARNING,
            device_id=device_id,
            error=type(e).__name__,
        )
        return None
    _check_mask(table, account_id, device_id, plan, aligned, window)
    return aligned


def _check_mask(table, account_id, device_id, plan: FollowPlan, aligned, window) -> None:
    """Keep the mask-change state and adopt a new mask that hides no zone; a failure here
    never changes the event's outcome."""
    from fridgesense import alignment, door_calibration  # both import this module

    if aligned is None or aligned.visible is None:
        return
    try:
        adopt = alignment.record_mask(
            table,
            account_id,
            device_id,
            aligned.visible,
            plan.anchor_visible,
            list(plan.zones),
            window["start_ms"],
        )
        if adopt is not None:
            door_calibration.save_anchor_visible(table, account_id, device_id, adopt)
            log_event("privacy_mask_adopted", account_id=account_id, device_id=device_id)
    except Exception as e:
        log_event("mask_check_failed", logging.WARNING, device_id=device_id, error=type(e).__name__)


def _learn(table, account_id, device_id, check: "DoorCheck", raw, aligned, window) -> None:
    """Sample an aligned event and re-tune the rules; a failure here never changes the
    event's outcome."""
    if aligned is None or not aligned.ok:
        return
    from fridgesense import self_tuning  # it imports this module

    try:
        frames = [data for _, data in raw]
        if self_tuning.learn(
            table, account_id, device_id, check, frames, aligned, window["start_ms"]
        ):
            self_tuning.retune(table, account_id, device_id, window["start_ms"])
    except Exception as e:
        log_event(
            "door_sample_failed", logging.WARNING, device_id=device_id, error=type(e).__name__
        )


def _count_suspect(table, account_id: str, device_id: str, suspect: bool) -> None:
    """Keep the device's suspect streak; a failure here never changes the event's outcome."""
    from fridgesense import alignment  # alignment imports this module

    try:
        alignment.record_suspect(table, account_id, device_id, suspect)
    except Exception as e:
        log_event(
            "suspect_streak_failed", logging.WARNING, device_id=device_id, error=type(e).__name__
        )


def _alignment_json(aligned) -> dict | None:
    if aligned is None:
        return None
    return {
        "dx": round(aligned.dx, 4),
        "dy": round(aligned.dy, 4),
        "error": round(aligned.error, 4),
        "ok": aligned.ok,
    }


def iso_utc(ms: int) -> str:
    dt = datetime.fromtimestamp(ms // 1000, UTC)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ms % 1000:03d}Z"


def drop_raw_clip(s3, bucket: str, state: dict) -> dict:
    """The workflow's catch after BlurClip fails: delete the raw clip and log it. The door event
    keeps its analysis and never links an unblurred clip."""
    s3.delete_object(Bucket=bucket, Key=state["clip"]["raw_key"])  # no error if already gone
    log_event(
        "clip_not_stored",
        logging.WARNING,
        device_id=state["device_id"],
        reason="blur_failed",
        error=(state.get("error") or {}).get("Error"),
    )
    return {**state, "outcome": "clip_dropped"}


def store_analysis_video(
    s3,
    bucket: str,
    state: dict,
    frames: list[tuple[int, bytes]],
    indexes: list[int],
    step: int,
    crop: Box | None,
    interval_ms: int,
) -> dict:
    """Encode the chosen clip frames (cropped, unblurred) as `analysis.mp4`, tagged transient,
    and return the step output's `analysis_video`; {} if encoding or the upload failed
    (logged as analysis_video_not_stored): analysis then falls back to the stills."""
    from fridgesense import clip_frames

    def cropped(data: bytes) -> Image.Image:
        img = Image.open(io.BytesIO(data)).convert("RGB")
        return _crop_box(img, crop) if crop is not None else img

    key = stills_prefix(state["account_id"], state["device_id"], state["window"]["start_ms"])
    key += "analysis.mp4"
    try:
        body = clip_frames.encode_video([cropped(frames[i][1]) for i in indexes])
    except Exception as e:  # a missing video only costs the analysis its best input
        log_event(
            "analysis_video_not_stored",
            logging.WARNING,
            device_id=state["device_id"],
            reason="encode_failed",
            error=type(e).__name__,
        )
        return {}
    try:
        s3.put_object(
            Bucket=bucket, Key=key, Body=body, ContentType="video/mp4", Tagging="transient=true"
        )
    except Exception as e:
        log_event(
            "analysis_video_not_stored",
            logging.WARNING,
            device_id=state["device_id"],
            reason="upload_failed",
            error=type(e).__name__,
        )
        return {}
    return {"key": key, "frame_ms": interval_ms * step, "frames": len(indexes)}


def store_open_clip(
    s3,
    bucket: str,
    state: dict,
    clip: Path,
    opened_ms: int,
    closed_ms: int | None,
    clip_dir=None,
    raw: bool = False,
) -> dict:
    """Cut the clip to the open span and store it next to the stills.

    Without `raw` (face blurring off) it is `clip.mp4`, and this returns the door event's
    `clip_key` and `clip_span`. With `raw` it is `clip-raw.mp4`, tagged transient and never
    linked, and this returns `{"clip": {"raw_key", "clip_span"}}` for the BlurClip step.
    Returns {} when the cut or upload failed (logged as clip_not_stored): a missing clip never
    costs the door event or its analysis.
    """
    from fridgesense import clip_frames

    start_ms = state["window"]["start_ms"]
    close = None if closed_ms is None else closed_ms - start_ms
    try:
        cut, (start_s, end_s) = clip_frames.cut_clip(clip, opened_ms - start_ms, close, clip_dir)
    except clip_frames.ClipUnavailable:
        log_event(
            "clip_not_stored", logging.WARNING, device_id=state["device_id"], reason="cut_failed"
        )
        return {}
    name = "clip-raw.mp4" if raw else "clip.mp4"
    key = stills_prefix(state["account_id"], state["device_id"], start_ms) + name
    extra = {"Tagging": "transient=true"} if raw else {}
    try:
        s3.put_object(
            Bucket=bucket, Key=key, Body=cut.read_bytes(), ContentType="video/mp4", **extra
        )
    except Exception as e:  # S3 trouble must not drop the door opening
        log_event(
            "clip_not_stored",
            logging.WARNING,
            device_id=state["device_id"],
            reason="upload_failed",
            error=type(e).__name__,
        )
        return {}
    finally:
        cut.unlink(missing_ok=True)
    if raw:
        return {"clip": {"raw_key": key, "clip_span": [start_s, end_s]}}
    return {"clip_key": key, "clip_span": [Decimal(str(start_s)), Decimal(str(end_s))]}


def fetch_stills(*args, **kwargs) -> dict:
    kept: list[Path] = []  # the downloaded clip, while the open span is cut from it
    try:
        return _fetch_stills(*args, kept=kept, **kwargs)
    finally:
        for path in kept:
            path.unlink(missing_ok=True)


def _fetch_stills(
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
    setup_for: Callable[[str, str], "DoorCheck | None"] | None = None,
    writer=None,
    frame_interval_ms: int | None = None,
    clip_dir=None,
    face_blur: bool = True,
    paused_for: Callable[[str, str], bool] | None = None,
    kept: list[Path] | None = None,
    area_for: Callable[[str, str], Box | None] | None = None,
) -> dict:
    """Download stills, run the door check, and claim + record the door event.

    With `frame_interval_ms`, the check first runs on the event clip's frames at that spacing
    and the frames picked from the open span are the stills (no Ring still is requested); if
    the clip can't be used it falls back to sampling stills across the window (the only path
    without it).

    The door check runs on the raw, uncropped stills in memory. For a door opening, up to
    4 stills from the open span are cropped to `crop`, go through `blurrer` (face detection,
    unless blurring is off), and are stored; the span also gives the event's open and close times.
    A clip's open span is also cut and stored as `clip.mp4` (best effort: see `store_open_clip`).
    Outcomes: door_open (go on to analysis), not_door, no_media, duplicate, and paused when
    `paused_for` says the owner paused the camera (checked before anything is downloaded).
    With a trace `writer`, every outcome also leaves a debug trace of what the check saw.
    """
    from fridgesense.traces import DoorTrace  # traces imports this module

    account_id, device_id, window = state["account_id"], state["device_id"], state["window"]
    if paused_for is not None and paused_for(account_id, device_id):
        log_event("door_check_paused", account_id=account_id, device_id=device_id)
        return {**state, "outcome": "paused"}
    if area_for is not None:  # the owner's fridge area, once per motion, wins over STILL_CROP
        from fridgesense.fridge_area import analysis_box  # fridge_area imports this module

        crop = analysis_box(area_for(account_id, device_id), crop)
    fallback_threshold = check.threshold  # DOOR_THRESHOLD: the default rules' threshold
    base = _device_check(check, setup_for, account_id, device_id)
    plan = _follow_plan(table, account_id, device_id, base)
    check = base.shifted(plan.dx, plan.dy) if plan else base
    clip = None
    if frame_interval_ms is not None:
        from fridgesense.clip_frames import ClipUnavailable

        try:
            clip = clip_frames_checked(
                ring, http, check, state, frame_interval_ms, sleep, clip_dir, keep=kept
            )
        except ClipUnavailable as e:
            log_event("clip_unavailable", logging.WARNING, device_id=device_id, reason=e.reason)
    if clip is not None:
        downloaded, clip_values = clip
    else:
        downloaded = download_all_stills(ring, http, state, sleep, interval_ms)
    raw = [(d.n, d.data) for d in downloaded if d.data is not None]
    aligned = None
    if plan is not None and len(raw) >= 2:
        aligned = _align(table, account_id, device_id, plan, raw[0][1], raw[-1][1], window)
        if aligned is not None and aligned.ok and (aligned.dx, aligned.dy) != (plan.dx, plan.dy):
            check = base.shifted(aligned.dx, aligned.dy)
            if clip is not None:  # frames were scored with the stored shift: score them again
                clip_values = [check.zone_values(data) for _, data in raw]
    times = [d.at_ms for d in downloaded]
    opened_ms, closed_ms = window["start_ms"], window["end_ms"]
    still_keys: list[str] = []
    still_ms: list[int] = []
    clip_fields: dict = {}
    video_span: list[int] | None = None
    status = "no_media"
    rule_log: dict = {"zones_source": check.source, "source": "clip" if clip else "stills"}
    trace = DoorTrace(
        stills=downloaded, values={}, check=check, outcome="no_media", face_blur=face_blur
    )
    trace.alignment = _alignment_json(aligned)
    suspect = False

    def done(result: dict) -> dict:
        if suspect:
            result = {**result, "suspect": True}
        if writer is not None:
            trace.outcome = result["outcome"]
            writer.door(state, trace)
        return result

    def learn() -> None:
        if not suspect:  # rules that read open throughout would teach the wrong thing
            _learn(table, account_id, device_id, check, raw, aligned, window)

    if len(raw) >= MIN_STILLS:
        values = clip_values if clip else [check.zone_values(data) for _, data in raw]
        trace.values = {n: v for (n, _), v in zip(raw, values, strict=True)}
        results = [check.result_of(v) for v in values]
        opened = [r.is_open for r in results]
        if clip is not None and check.source in ("setup", "tuned"):
            _count_suspect(table, account_id, device_id, is_suspect(opened, check.source))
        if clip is not None and is_suspect(opened, check.source):
            suspect = True
            log_event(
                "door_check_suspect",
                account_id=account_id,
                device_id=device_id,
                frames=len(opened),
                open_share=round(sum(opened) / len(opened), 3),
                zones_source=check.source,
            )
            check = check.fridge_light(fallback_threshold)
            trace.check = check
            rule_log = {**rule_log, "zones_source": check.source}
            values = [check.zone_values(data) for _, data in raw]
            trace.values = {n: v for (n, _), v in zip(raw, values, strict=True)}
            results = [check.result_of(v) for v in values]
        best = check.best(results)
        rule_log = {**rule_log, "feature": best.feature, "threshold": best.threshold}
        span = open_span([1.0 if r.is_open else 0.0 for r in results], 1.0)
        if span is None:
            log_event(
                "motion_not_door",
                account_id=account_id,
                device_id=device_id,
                score=round(best.value, 3),
                zone=best.zone,
                **rule_log,
            )
            learn()
            return done({**state, "outcome": "not_door", "score": round(best.value, 3)})
        opened_ms = times[raw[span[0]][0] - 1]
        if not results[span[-1]].is_open:  # the first closed still after the opening
            closed_ms = times[raw[span[-1]][0] - 1]
        picks = pick(span)
        video_span = span
        trace.open_span = [raw[i][0] for i in span]
        trace.picked = [raw[i][0] for i in picks]
        # On the clip path these are the scored frames themselves: a Ring still at the same
        # time can show another moment (it is the nearest frame within ±10 s).
        picked = [(k, crop_still(raw[i][1], crop)) for k, i in enumerate(picks, start=1)]
        stills = store_blurred_stills(s3, bucket, blurrer, state, picked)
        still_keys = [k for k, _ in stills]
        pick_ms = {f"still-{k}.jpg": times[raw[i][0] - 1] for k, i in enumerate(picks, start=1)}
        still_ms = [pick_ms[key.rsplit("/", 1)[1]] for key in still_keys]
        trace.stored_keys = still_keys
        if clip and kept:
            closed = closed_ms if not results[span[-1]].is_open else None
            clip_fields = store_open_clip(
                s3, bucket, state, kept[0], opened_ms, closed, clip_dir, raw=face_blur
            )
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
        **{k: v for k, v in clip_fields.items() if k != "clip"},
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
            if "clip" in clip_fields:  # nothing will blur it
                s3.delete_object(Bucket=bucket, Key=clip_fields["clip"]["raw_key"])
            return done({**state, "outcome": "duplicate"})
        raise
    outcome = "door_open" if status == "analyzing" else "no_media"
    video: dict = {}
    if outcome == "door_open" and clip is not None and video_span is not None:
        indexes, step = video_frame_indexes(video_span)
        video = store_analysis_video(
            s3, bucket, state, raw, indexes, step, crop, frame_interval_ms or 0
        )
        if video:
            video = {**video, "start_ms": times[raw[indexes[0]][0] - 1]}
    learn()
    log_event(
        "door_event_recorded", account_id=account_id, door_sk=door_sk, outcome=outcome, **rule_log
    )
    trace.door_sk = door_sk
    trace.opened_at, trace.closed_at = event["opened_at"], event["closed_at"]
    raw_clip = {"clip": clip_fields["clip"]} if "clip" in clip_fields else {}
    analysis_video = {"analysis_video": video} if video else {}
    return done(
        {
            **state,
            "outcome": outcome,
            "door_sk": door_sk,
            "still_keys": still_keys,
            "still_ms": still_ms,
            **raw_clip,
            **analysis_video,
        }
    )
