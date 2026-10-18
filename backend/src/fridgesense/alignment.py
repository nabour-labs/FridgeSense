"""Keeping the door zones on the doors when the camera shifts: a closed anchor from setup, each
event's bookend frames lined up with it, and the device's alignment state."""

import io
from dataclasses import asdict, dataclass, replace

from PIL import Image, ImageChops, ImageFilter, ImageOps, ImageStat

from fridgesense.door_events import Box
from fridgesense.table import FridgeTable, account_pk

SIZE = (128, 72)
MAX_SHIFT = 8  # pixels at SIZE, each way on both axes
# Measured on 12 real clips: aligned views 0.004-0.037, a 5-15 degree rotation 0.075-0.091.
ALIGN_MAX_ERROR = 0.05


def edge_map(still: bytes | Image.Image) -> Image.Image:
    """The still in grayscale at 128x72 as edges: lighting changes move edges far less than
    they move brightness."""
    img = still if isinstance(still, Image.Image) else Image.open(io.BytesIO(still))
    small = img.convert("L").resize(SIZE, Image.Resampling.BOX)
    return ImageOps.autocontrast(small.filter(ImageFilter.FIND_EDGES))


def edges_to_bytes(edges: Image.Image) -> bytes:
    return edges.tobytes()


def edges_from_bytes(data: bytes) -> Image.Image:
    return Image.frombytes("L", SIZE, bytes(data))


@dataclass(frozen=True)
class Shift:
    px: int
    py: int
    error: float


def _error(anchor: Image.Image, edges: Image.Image, px: int, py: int) -> float:
    """Mean edge difference where `edges` moved by (px, py) overlaps the anchor, skipping the
    1 px border FIND_EDGES leaves."""
    w, h = SIZE
    x0, x1 = max(1, 1 - px), min(w - 1, w - 1 - px)
    y0, y1 = max(1, 1 - py), min(h - 1, h - 1 - py)
    a = anchor.crop((x0, y0, x1, y1))
    b = edges.crop((x0 + px, y0 + py, x1 + px, y1 + py))
    return ImageStat.Stat(ImageChops.difference(a, b)).mean[0] / 255


def best_shift(anchor: Image.Image, edges: Image.Image) -> Shift:
    """The whole-pixel move of `edges`' content against the anchor with the lowest error
    (ties keep the smaller move)."""
    span = range(-MAX_SHIFT, MAX_SHIFT + 1)
    candidates = (
        (_error(anchor, edges, px, py), abs(px) + abs(py), px, py) for px in span for py in span
    )
    error, _, px, py = min(candidates)
    return Shift(px, py, error)


@dataclass(frozen=True)
class Alignment:
    ok: bool
    dx: float  # fractions of the image: + is right
    dy: float  # + is down
    error: float
    used: str  # "first" or "last"


def align_bookends(
    anchor: Image.Image, first: bytes | Image.Image, last: bytes | Image.Image
) -> Alignment:
    """Line the event's first and last frames up with the anchor and use the better one."""
    shifts = {
        "first": best_shift(anchor, edge_map(first)),
        "last": best_shift(anchor, edge_map(last)),
    }
    used = min(shifts, key=lambda k: shifts[k].error)  # ties keep "first"
    s = shifts[used]
    w, h = SIZE
    return Alignment(s.error <= ALIGN_MAX_ERROR, s.px / w, s.py / h, s.error, used)


def shift_box(box: Box, dx: float, dy: float) -> Box:
    """`box` moved by (dx, dy), kept inside the image."""
    x, y, w, h = box
    return (min(max(x + dx, 0.0), 1 - w), min(max(y + dy, 0.0), 1 - h), w, h)


MOVED_FAILURES = 3  # failed alignments in a row
MOVED_SHIFT = 0.04  # of the frame, either axis: references and the fridge area are visibly off


def align_sk(device_id: str) -> str:
    return f"ALIGN#{device_id}"


@dataclass(frozen=True)
class AlignState:
    dx: float = 0.0
    dy: float = 0.0
    error: float | None = None
    failures: int = 0
    moved: bool = False
    moved_at_ms: int | None = None
    last_moved_at_ms: int | None = None  # kept by a setup run, for the fridge-area warning
    checked_at_ms: int | None = None
    suspect_streak: int = 0  # suspect clips in a row (rules read open throughout)


def _opt_int(value) -> int | None:
    return None if value is None else int(value)


def load_alignment(table: FridgeTable, account_id: str, device_id: str) -> AlignState | None:
    item = table.get(account_pk(account_id), align_sk(device_id))
    if item is None:
        return None
    return AlignState(
        dx=float(item["dx"]),
        dy=float(item["dy"]),
        error=None if item.get("error") is None else float(item["error"]),
        failures=int(item["failures"]),
        moved=bool(item["moved"]),
        moved_at_ms=_opt_int(item.get("moved_at_ms")),
        last_moved_at_ms=_opt_int(item.get("last_moved_at_ms")),
        checked_at_ms=_opt_int(item.get("checked_at_ms")),
        suspect_streak=int(item.get("suspect_streak", 0)),
    )


def _save(table: FridgeTable, account_id: str, device_id: str, s: AlignState) -> None:
    table.put({"pk": account_pk(account_id), "sk": align_sk(device_id), **asdict(s)})


def reset(table: FridgeTable, account_id: str, device_id: str) -> None:
    """After a setup run: no shift, not moved, no suspect streak; when the camera last moved
    is kept."""
    old = load_alignment(table, account_id, device_id)
    last = old.last_moved_at_ms if old else None
    _save(table, account_id, device_id, AlignState(last_moved_at_ms=last))


def record_suspect(table: FridgeTable, account_id: str, device_id: str, suspect: bool) -> int:
    """One more suspect clip in a row, or back to 0 after a clip the rules read normally."""
    old = load_alignment(table, account_id, device_id) or AlignState()
    streak = old.suspect_streak + 1 if suspect else 0
    if streak != old.suspect_streak:
        _save(table, account_id, device_id, replace(old, suspect_streak=streak))
    return streak


def record(
    table: FridgeTable, account_id: str, device_id: str, result: Alignment, at_ms: int
) -> AlignState:
    """Store one event's alignment and work out whether the camera has moved."""
    old = load_alignment(table, account_id, device_id) or AlignState()
    if result.ok:
        s = replace(old, dx=result.dx, dy=result.dy, error=result.error, failures=0)
        moving = abs(result.dx) >= MOVED_SHIFT or abs(result.dy) >= MOVED_SHIFT
    else:
        s = replace(old, failures=old.failures + 1)
        moving = s.failures >= MOVED_FAILURES
    s = replace(s, checked_at_ms=at_ms)
    if moving and not s.moved:
        s = replace(s, moved=True, moved_at_ms=at_ms, last_moved_at_ms=at_ms)
    _save(table, account_id, device_id, s)
    return s


def align_event(
    table: FridgeTable,
    account_id: str,
    device_id: str,
    anchor: bytes | None,
    first: bytes | Image.Image | None,
    last: bytes | Image.Image | None,
    at_ms: int,
) -> Alignment | None:
    """Align an event's bookends with the device's anchor and record it; None (and nothing
    stored) without an anchor or bookends."""
    if anchor is None or first is None or last is None:
        return None
    result = align_bookends(edges_from_bytes(anchor), first, last)
    record(table, account_id, device_id, result, at_ms)
    return result
