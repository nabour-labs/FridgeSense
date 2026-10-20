"""Keeping the door zones on the doors when the camera shifts: a closed anchor from setup, each
event's bookend frames lined up with it, and the device's alignment state."""

import io
from dataclasses import asdict, dataclass, replace

from PIL import Image, ImageChops, ImageFilter, ImageOps, ImageStat

from fridgesense.door_events import Box
from fridgesense.table import FridgeTable, account_pk

SIZE = (128, 72)
MAX_SHIFT = 8  # pixels at SIZE, each way on both axes
# Views are compared in BLOCK x BLOCK blocks: a person in front of the fridge covers some
# blocks and leaves the rest lined up, while a rotation moves every block a different way.
BLOCK = 8
BLOCK_MAX_ERROR = 0.12  # mean edge difference / 255 for a block to match
MIN_BLOCK_EDGES = 8  # mean anchor edge value: flatter blocks match at any shift
MIN_BLOCKS = 8
# Share of blocks that match. Measured on the 2026-10-18 frames: closed references 1.0, a
# person in front of the fridge 0.57-0.62, a 3-15 degree rotation 0.33-0.46.
ALIGN_MIN_MATCH = 0.5
ALIGN_MAX_ERROR = 1 - ALIGN_MIN_MATCH  # error is 1 - match share


def edge_map(still: bytes | Image.Image) -> Image.Image:
    """The still in grayscale at 128x72 as edges: lighting changes move edges far less than
    they move brightness."""
    img = still if isinstance(still, Image.Image) else Image.open(io.BytesIO(still))
    small = img.convert("L").resize(SIZE, Image.Resampling.BOX)
    return ImageOps.autocontrast(small.filter(ImageFilter.FIND_EDGES))


MASK_DARK = 16  # gray below this counts as dark
MASK_SHARE = 0.8  # of a pixel's 9x9 neighborhood dark: the pixel is under the privacy mask
MASK_GROW = 2  # px the masked area grows, so the mask's border edge is never compared


def visible_map(still: bytes | Image.Image) -> Image.Image:
    """The pixels at 128x72 the privacy mask leaves visible (255) or covers (0). Ring paints
    the mask black; its overlay text inside the mask is too sparse to unmask it."""
    img = still if isinstance(still, Image.Image) else Image.open(io.BytesIO(still))
    small = img.convert("L").resize(SIZE, Image.Resampling.BOX)
    dark = small.point(lambda v: 255 if v < MASK_DARK else 0)
    # Close the dark area over light marks up to 4 px thick: the overlay text.
    dark = dark.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(5))
    share = dark.filter(ImageFilter.BoxBlur(4))  # mean over 9x9
    masked = share.point(lambda v: 255 if v >= MASK_SHARE * 255 else 0)
    # The share test leaves the outer 3 px of a black area unmasked; grow those back too.
    masked = masked.filter(ImageFilter.MaxFilter(2 * (MASK_GROW + 3) + 1))
    return ImageOps.invert(masked)


def visible_to_bytes(vis: Image.Image) -> bytes:
    return vis.tobytes()


def visible_from_bytes(data: bytes) -> Image.Image:
    return Image.frombytes("L", SIZE, bytes(data))


def edges_to_bytes(edges: Image.Image) -> bytes:
    return edges.tobytes()


def edges_from_bytes(data: bytes) -> Image.Image:
    return Image.frombytes("L", SIZE, bytes(data))


@dataclass(frozen=True)
class Shift:
    px: int
    py: int
    error: float


GRID = (SIZE[0] // BLOCK, SIZE[1] // BLOCK)


def _all_visible() -> Image.Image:
    return Image.new("L", SIZE, 255)


def _usable(vis: Image.Image | None) -> Image.Image:
    """The visible map without the 1 px border FIND_EDGES leaves."""
    out = Image.new("L", SIZE, 0)
    out.paste((vis or _all_visible()).crop((1, 1, SIZE[0] - 1, SIZE[1] - 1)), (1, 1))
    return out


def _moved(img: Image.Image, px: int, py: int) -> Image.Image:
    """`img` moved so its pixel (x + px, y + py) lands on (x, y); 0 where nothing lands."""
    out = Image.new("L", SIZE, 0)
    out.paste(img, (-px, -py))
    return out


def _blocks(img: Image.Image) -> list[int]:
    """Each block's mean, row by row."""
    return list(img.resize(GRID, Image.Resampling.BOX).tobytes())


def best_shift(
    anchor: Image.Image,
    edges: Image.Image,
    anchor_visible: Image.Image | None = None,
    edges_visible: Image.Image | None = None,
) -> Shift:
    """The whole-pixel move of `edges`' content against the anchor with the highest share of
    matching blocks, counting only blocks visible in both and with edges in the anchor (ties
    keep the smaller move). `error` is 1 - that share, and 1 with too few blocks to count."""
    anchor_vis = _usable(anchor_visible)
    edges_vis = _usable(edges_visible)
    textured = [m >= MIN_BLOCK_EDGES for m in _blocks(anchor)]
    anchor_whole = [m == 255 for m in _blocks(anchor_vis)]
    span = range(-MAX_SHIFT, MAX_SHIFT + 1)
    best = None
    for px in span:
        for py in span:
            seen = _blocks(_moved(edges_vis, px, py))
            diff = _blocks(ImageChops.difference(anchor, _moved(edges, px, py)))
            counted = [
                d
                for d, t, a, v in zip(diff, textured, anchor_whole, seen, strict=True)
                if t and a and v == 255
            ]
            share = 0.0
            if len(counted) >= MIN_BLOCKS:
                share = sum(d <= BLOCK_MAX_ERROR * 255 for d in counted) / len(counted)
            key = (-share, abs(px) + abs(py))
            if best is None or key < best[0]:
                best = (key, px, py, share)
    _, px, py, share = best
    return Shift(px, py, 1 - share)


@dataclass(frozen=True)
class Alignment:
    ok: bool
    dx: float  # fractions of the image: + is right
    dy: float  # + is down
    error: float
    used: str  # "first" or "last"
    visible: bytes | None = None  # the used bookend's visible map


def align_bookends(
    anchor: Image.Image,
    first: bytes | Image.Image,
    last: bytes | Image.Image,
    anchor_visible: Image.Image | None = None,
) -> Alignment:
    """Line the event's first and last frames up with the anchor, leaving out what the privacy
    mask covers in either, and use the better one."""
    shifts, maps = {}, {}
    for name, frame in (("first", first), ("last", last)):
        maps[name] = visible_map(frame)
        shifts[name] = best_shift(anchor, edge_map(frame), anchor_visible, maps[name])
    used = min(shifts, key=lambda k: shifts[k].error)  # ties keep "first"
    s = shifts[used]
    w, h = SIZE
    ok = 1 - s.error >= ALIGN_MIN_MATCH
    return Alignment(ok, s.px / w, s.py / h, s.error, used, visible_to_bytes(maps[used]))


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
    mask_streak: int = 0  # events in a row whose privacy mask differs from the anchor's
    mask_changed_at_ms: int | None = None
    mask_zones: tuple[str, ...] = ()  # zones a changed mask now partly hides


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
        mask_streak=int(item.get("mask_streak", 0)),
        mask_changed_at_ms=_opt_int(item.get("mask_changed_at_ms")),
        mask_zones=tuple(item.get("mask_zones") or ()),
    )


def _save(table: FridgeTable, account_id: str, device_id: str, s: AlignState) -> None:
    item = {**asdict(s), "mask_zones": list(s.mask_zones)}
    table.put({"pk": account_pk(account_id), "sk": align_sk(device_id), **item})


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
    anchor_visible: bytes | None = None,
) -> Alignment | None:
    """Align an event's bookends with the device's anchor and record it; None (and nothing
    stored) without an anchor or bookends."""
    if anchor is None or first is None or last is None:
        return None
    vis = visible_from_bytes(anchor_visible) if anchor_visible else None
    result = align_bookends(edges_from_bytes(anchor), first, last, vis)
    record(table, account_id, device_id, result, at_ms)
    return result


MASK_CHANGE = 0.03  # share of pixels whose visibility differs: the privacy mask changed
MASK_EVENTS = 2  # changed events in a row that confirm it
ZONE_MIN_VISIBLE = 0.95  # share of a zone's box left visible; less and the zone is hidden


def _visible_share(vis: Image.Image, box: Box) -> float:
    w, h = SIZE
    x, y, bw, bh = box
    area = (
        round(x * w),
        round(y * h),
        max(round((x + bw) * w), round(x * w) + 1),
        max(round((y + bh) * h), round(y * h) + 1),
    )
    return ImageStat.Stat(vis.crop(area)).mean[0] / 255


def record_mask(
    table: FridgeTable,
    account_id: str,
    device_id: str,
    event_visible: bytes,
    anchor_visible: bytes | None,
    zones: list[tuple[str, Box]],
    at_ms: int,
) -> bytes | None:
    """Compare an event's visible map with the anchor's and keep the mask-change state. Returns
    the event's map when a confirmed change hides no zone, for the caller to adopt as the
    anchor's; None otherwise."""
    old = load_alignment(table, account_id, device_id) or AlignState()
    new = visible_from_bytes(event_visible)
    anchor = visible_from_bytes(anchor_visible) if anchor_visible else _all_visible()
    differs = ImageStat.Stat(ImageChops.difference(new, anchor)).mean[0] / 255 > MASK_CHANGE
    streak = old.mask_streak + 1 if differs else 0
    adopt = None
    s = replace(old, mask_streak=streak)
    if streak >= MASK_EVENTS:
        hidden = tuple(name for name, box in zones if _visible_share(new, box) < ZONE_MIN_VISIBLE)
        s = replace(s, mask_streak=0)
        if hidden:
            s = replace(s, mask_zones=hidden, mask_changed_at_ms=old.mask_changed_at_ms or at_ms)
        else:
            adopt = event_visible
    if s != old:
        _save(table, account_id, device_id, s)
    return adopt
