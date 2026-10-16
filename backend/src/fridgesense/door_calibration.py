"""The owner's door references (open/closed snapshots with a box) and the setup run that
turns them into the door check's per-zone rules: which feature, which way, what threshold."""

import base64
import binascii
import io
import secrets
import time
from dataclasses import dataclass
from typing import Any

from PIL import Image

from fridgesense.analysis_config import JPEG_MAGIC, Invalid
from fridgesense.door_events import (
    FEATURES,
    Box,
    DoorCheck,
    ZoneRule,
    baseline_of,
    iso_utc,
    measure,
)
from fridgesense.table import FridgeTable, account_pk

MAX_IMAGE_BYTES = 300_000
MAX_REFERENCES = 12
MAX_ZONES = 6
MIN_SIDE = 0.02
GROUP_IOU = 0.3
MIN_MARGIN = 0.01
STATUSES = ("open", "closed")


def ref_prefix(device_id: str) -> str:
    return f"DOORREF#{device_id}#"


def setup_sk(device_id: str) -> str:
    return f"DOORSETUP#{device_id}"


def marker_sk(device_id: str) -> str:
    return f"DOORREFS#{device_id}"


class TooMany(Exception):
    """The device already holds MAX_REFERENCES door references."""


class SetupFailed(Exception):
    """Setup could not find a rule; `scores` maps each reference's sk to its color value."""

    def __init__(self, message: str, scores: dict[str, float]):
        super().__init__(message)
        self.message = message
        self.scores = scores


BOX_ERROR = "box must be inside the image and at least 2% wide and tall"


def validate_box(value: Any) -> Box:
    try:
        parts = tuple(value[k] for k in ("x", "y", "width", "height"))
    except (TypeError, KeyError, IndexError):
        raise Invalid(BOX_ERROR) from None
    if not all(isinstance(v, int | float) and not isinstance(v, bool) for v in parts):
        raise Invalid(BOX_ERROR)
    x, y, w, h = (float(v) for v in parts)
    if x < 0 or y < 0 or w < MIN_SIDE or h < MIN_SIDE or x + w > 1 or y + h > 1:
        raise Invalid(BOX_ERROR)
    return x, y, w, h


def validate_status(value: Any) -> str:
    if value not in STATUSES:
        raise Invalid("status must be open or closed")
    return value


def decode_image(value: Any) -> bytes:
    """The JPEG bytes of a base64 image, at most MAX_IMAGE_BYTES."""
    try:
        data = base64.b64decode(value, validate=True) if isinstance(value, str) else b""
    except (binascii.Error, ValueError):
        data = b""
    if not data.startswith(JPEG_MAGIC) or len(data) > MAX_IMAGE_BYTES:
        raise Invalid("image must be a JPEG of at most 300 KB")
    return data


def box_json(box: Box) -> dict:
    x, y, w, h = box
    return {"x": x, "y": y, "width": w, "height": h}


@dataclass(frozen=True)
class DoorReference:
    sk: str
    image: bytes
    box: Box
    status: str
    created_at: str


@dataclass(frozen=True)
class SetupZone:
    box: Box
    feature: str
    direction: str
    threshold: float
    margin: float
    baseline: bytes


@dataclass(frozen=True)
class Setup:
    zones: tuple[SetupZone, ...]
    ran_at: str
    stale: bool


def _box_of(item: dict) -> Box:
    b = item["box"]
    return (float(b["x"]), float(b["y"]), float(b["width"]), float(b["height"]))


def _reference(item: dict) -> DoorReference:
    return DoorReference(
        sk=item["sk"],
        image=bytes(item["image"]),
        box=_box_of(item),
        status=item["status"],
        created_at=item["created_at"],
    )


def list_references(table: FridgeTable, account_id: str, device_id: str) -> list[DoorReference]:
    """The device's door references, oldest first."""
    items = sorted(table.query(account_id, ref_prefix(device_id)), key=lambda i: i["sk"])
    return [_reference(i) for i in items]


def _mark_changed(table: FridgeTable, account_id: str, device_id: str, now_ms: int) -> None:
    table.put({"pk": account_pk(account_id), "sk": marker_sk(device_id), "changed_ms": now_ms})


def add_reference(
    table: FridgeTable,
    account_id: str,
    device_id: str,
    image: bytes,
    box: Any,
    status: str,
    now_ms: int,
) -> DoorReference:
    box = validate_box(box) if isinstance(box, dict) else box
    if len(table.query(account_id, ref_prefix(device_id))) >= MAX_REFERENCES:
        raise TooMany()
    # Zero-padded time first, so sort keys list references oldest first.
    item = {
        "pk": account_pk(account_id),
        "sk": f"{ref_prefix(device_id)}{now_ms:013d}-{secrets.token_hex(3)}",
        "image": image,  # Binary: 300 KB fits under DynamoDB's 400 KB item limit
        "box": box_json(box),
        "status": status,
        "created_at": iso_utc(now_ms),
    }
    table.put(item)
    _mark_changed(table, account_id, device_id, now_ms)
    return _reference(item)


def delete_reference(
    table: FridgeTable, account_id: str, device_id: str, sk: str, now_ms: int = 0
) -> bool:
    """False if the device has no such reference."""
    if not sk.startswith(ref_prefix(device_id)):
        return False
    if not table.delete(account_pk(account_id), sk):
        return False
    _mark_changed(table, account_id, device_id, now_ms or int(time.time() * 1000))
    return True


def iou(a: Box, b: Box) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    w = max(0.0, min(ax + aw, bx + bw) - max(ax, bx))
    h = max(0.0, min(ay + ah, by + bh) - max(ay, by))
    overlap = w * h
    union = aw * ah + bw * bh - overlap
    return overlap / union if union > 0 else 0.0


def _bounding(a: Box, b: Box) -> Box:
    left, top = min(a[0], b[0]), min(a[1], b[1])
    right, bottom = max(a[0] + a[2], b[0] + b[2]), max(a[1] + a[3], b[1] + b[3])
    return left, top, right - left, bottom - top


def _round_box(box: Box) -> Box:
    return tuple(round(v, 3) for v in box)


def group_boxes(boxes: list[Box]) -> tuple[list[Box], list[int]]:
    """(zones, the 0-based zone of each box): a box joins the first group it overlaps enough."""
    groups: list[Box] = []
    member: list[int] = []
    for box in boxes:
        for k, group in enumerate(groups):
            if iou(box, group) >= GROUP_IOU:
                groups[k] = _bounding(group, box)
                member.append(k)
                break
        else:
            groups.append(box)
            member.append(len(groups) - 1)
    return [_round_box(g) for g in groups], member


def _image(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data)).convert("RGB")


def _choose(opened: list[float], closed: list[float]) -> tuple[str, float, float] | None:
    """(direction, threshold, margin) if the values separate, else None."""
    if min(opened) > max(closed):
        return "above", (min(opened) + max(closed)) / 2, min(opened) - max(closed)
    if max(opened) < min(closed):
        return "below", (max(opened) + min(closed)) / 2, min(closed) - max(opened)
    return None


def run(table: FridgeTable, account_id: str, device_id: str, now_ms: int) -> Setup:
    """Work out each zone's rule from the references and store it; SetupFailed leaves the
    stored setup unchanged."""
    refs = list_references(table, account_id, device_id)
    images = [_image(r.image) for r in refs]
    zones, member = group_boxes([r.box for r in refs])
    scores = {
        r.sk: measure(img, zones[member[i]], "color")
        for i, (r, img) in enumerate(zip(refs, images, strict=True))
    }
    if len(zones) > MAX_ZONES:
        raise SetupFailed(f"at most {MAX_ZONES} separate zones", scores)
    if not zones:
        raise SetupFailed("zone 1 needs an open and a closed reference", scores)

    chosen: list[SetupZone] = []
    for k, zone in enumerate(zones):
        mine = [i for i, z in enumerate(member) if z == k]
        opened = [images[i] for i in mine if refs[i].status == "open"]
        closed = [images[i] for i in mine if refs[i].status == "closed"]
        if not opened or not closed:
            raise SetupFailed(f"zone {k + 1} needs an open and a closed reference", scores)
        baseline = baseline_of(closed, zone)
        best = None
        for feature in FEATURES:  # ties keep the earlier feature
            values_open = [measure(img, zone, feature, baseline) for img in opened]
            values_closed = [measure(img, zone, feature, baseline) for img in closed]
            rule = _choose(values_open, values_closed)
            if rule and rule[2] >= MIN_MARGIN and (best is None or rule[2] > best[3]):
                best = (feature, *rule)
        if best is None:
            raise SetupFailed(f"zone {k + 1}: open and closed references overlap", scores)
        feature, direction, threshold, margin = best
        chosen.append(
            SetupZone(zone, feature, direction, round(threshold, 4), round(margin, 4), baseline)
        )

    table.put(
        {
            "pk": account_pk(account_id),
            "sk": setup_sk(device_id),
            "zones": [
                {
                    **box_json(z.box),
                    "feature": z.feature,
                    "direction": z.direction,
                    "threshold": z.threshold,
                    "margin": z.margin,
                    "baseline": z.baseline,
                }
                for z in chosen
            ],
            "ran_ms": now_ms,
            "ran_at": iso_utc(now_ms),
        }
    )
    return Setup(tuple(chosen), iso_utc(now_ms), stale=False)


def load_setup(table: FridgeTable, account_id: str, device_id: str) -> Setup | None:
    item = table.get(account_pk(account_id), setup_sk(device_id))
    if item is None:
        return None
    marker = table.get(account_pk(account_id), marker_sk(device_id))
    stale = marker is not None and int(marker["changed_ms"]) > int(item["ran_ms"])
    zones = tuple(
        SetupZone(
            box=_box_of({"box": z}),
            feature=z["feature"],
            direction=z["direction"],
            threshold=float(z["threshold"]),
            margin=float(z["margin"]),
            baseline=bytes(z["baseline"]),
        )
        for z in item["zones"]
    )
    return Setup(zones, item["ran_at"], stale)


def setup_check(table: FridgeTable, account_id: str, device_id: str) -> DoorCheck | None:
    """The door check from the device's setup result, or None if setup never ran."""
    setup = load_setup(table, account_id, device_id)
    if setup is None:
        return None
    rules = tuple(
        ZoneRule(z.box, z.feature, z.direction, z.threshold, z.baseline) for z in setup.zones
    )
    return DoorCheck(rules=rules, source="setup")


def reference_scores(refs: list[DoorReference], setup: Setup | None) -> dict[str, float | None]:
    """Each reference's value of its setup zone's feature (None: no setup or no matching zone)."""
    scores: dict[str, float | None] = {}
    for ref in refs:
        zone = None
        if setup is not None:
            zone = next((z for z in setup.zones if iou(ref.box, z.box) >= GROUP_IOU), None)
        scores[ref.sk] = (
            None if zone is None else measure(ref.image, zone.box, zone.feature, zone.baseline)
        )
    return scores
