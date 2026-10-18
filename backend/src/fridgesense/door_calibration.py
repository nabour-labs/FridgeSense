"""The owner's door zones (a named box around a door or drawer), their references
(open/closed snapshots of a zone) and the setup run that turns them into the door check's
per-zone rules: which feature, which way, what threshold."""

import base64
import binascii
import io
import secrets
import time
from dataclasses import dataclass
from typing import Any

from PIL import Image

from fridgesense import alignment
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
MAX_REFERENCES = 24
MAX_ZONES = 6
MAX_NAME = 30
MIN_SIDE = 0.02
MIN_MARGIN = 0.01
STATUSES = ("open", "closed")


def ref_prefix(device_id: str) -> str:
    return f"DOORREF#{device_id}#"


def zone_prefix(device_id: str) -> str:
    return f"DOORZONE#{device_id}#"


def setup_sk(device_id: str) -> str:
    return f"DOORSETUP#{device_id}"


def marker_sk(device_id: str) -> str:
    return f"DOORREFS#{device_id}"


class TooMany(Exception):
    """The device already holds MAX_REFERENCES door references."""


class TooManyZones(Exception):
    """The device already holds MAX_ZONES door zones."""


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


def validate_name(value: Any) -> str:
    name = value.strip() if isinstance(value, str) else ""
    if not 1 <= len(name) <= MAX_NAME:
        raise Invalid(f"name must be 1 to {MAX_NAME} characters")
    return name


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
class DoorZone:
    sk: str
    name: str
    box: Box
    created_at: str


@dataclass(frozen=True)
class DoorReference:
    sk: str
    image: bytes
    zone_id: str  # the zone's sk
    box: Box  # the zone's current box
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
    zone_id: str = ""  # empty for a setup run before zones existed
    name: str = ""


@dataclass(frozen=True)
class Setup:
    zones: tuple[SetupZone, ...]
    ran_at: str
    stale: bool
    tuned_at: str | None = None  # when the rules were last re-tuned from event samples
    tuned_from: int | None = None  # how many samples that used
    tuned: tuple[SetupZone, ...] = ()  # the re-tuned rules, used instead of `zones` when set


def _box_of(item: dict) -> Box:
    b = item["box"]
    return (float(b["x"]), float(b["y"]), float(b["width"]), float(b["height"]))


def _zone(item: dict) -> DoorZone:
    return DoorZone(item["sk"], item["name"], _box_of(item), item["created_at"])


def list_zones(table: FridgeTable, account_id: str, device_id: str) -> list[DoorZone]:
    """The device's door zones, oldest first."""
    items = sorted(table.query(account_id, zone_prefix(device_id)), key=lambda i: i["sk"])
    return [_zone(i) for i in items]


def list_references(table: FridgeTable, account_id: str, device_id: str) -> list[DoorReference]:
    """The device's door references, oldest first. References with no zone (stored before
    zones existed, or left by a zone delete that stopped partway) are skipped."""
    boxes = {z.sk: z.box for z in list_zones(table, account_id, device_id)}
    items = sorted(table.query(account_id, ref_prefix(device_id)), key=lambda i: i["sk"])
    return [
        DoorReference(
            sk=i["sk"],
            image=bytes(i["image"]),
            zone_id=i["zone_id"],
            box=boxes[i["zone_id"]],
            status=i["status"],
            created_at=i["created_at"],
        )
        for i in items
        if i.get("zone_id") in boxes
    ]


def _mark_changed(table: FridgeTable, account_id: str, device_id: str, now_ms: int) -> None:
    table.put({"pk": account_pk(account_id), "sk": marker_sk(device_id), "changed_ms": now_ms})


def add_reference(
    table: FridgeTable,
    account_id: str,
    device_id: str,
    image: bytes,
    zone_id: Any,
    status: str,
    now_ms: int,
) -> DoorReference:
    """Invalid("pick a door zone") unless zone_id is one of the device's zones."""
    zones = {z.sk: z for z in list_zones(table, account_id, device_id)}
    if not isinstance(zone_id, str) or zone_id not in zones:
        raise Invalid("pick a door zone")
    if len(list_references(table, account_id, device_id)) >= MAX_REFERENCES:
        raise TooMany()
    # Zero-padded time first, so sort keys list references oldest first.
    item = {
        "pk": account_pk(account_id),
        "sk": f"{ref_prefix(device_id)}{now_ms:013d}-{secrets.token_hex(3)}",
        "image": image,  # Binary: 300 KB fits under DynamoDB's 400 KB item limit
        "zone_id": zone_id,
        "status": status,
        "created_at": iso_utc(now_ms),
    }
    table.put(item)
    _mark_changed(table, account_id, device_id, now_ms)
    return DoorReference(item["sk"], image, zone_id, zones[zone_id].box, status, item["created_at"])


def add_zone(
    table: FridgeTable, account_id: str, device_id: str, name: Any, box: Any, now_ms: int
) -> DoorZone:
    name = validate_name(name)
    box = validate_box(box)
    if len(list_zones(table, account_id, device_id)) >= MAX_ZONES:
        raise TooManyZones()
    item = {
        "pk": account_pk(account_id),
        "sk": f"{zone_prefix(device_id)}{now_ms:013d}-{secrets.token_hex(3)}",
        "name": name,
        "box": box_json(box),
        "created_at": iso_utc(now_ms),
    }
    table.put(item)
    _mark_changed(table, account_id, device_id, now_ms)
    return _zone(item)


def update_zone(
    table: FridgeTable,
    account_id: str,
    device_id: str,
    sk: str,
    now_ms: int,
    name: Any = None,
    box: Any = None,
) -> bool:
    """Rename and/or redraw a zone (None leaves a field as it is); False if there is no such
    zone. Its references follow the new box."""
    if not sk.startswith(zone_prefix(device_id)):
        return False
    item = table.get(account_pk(account_id), sk)
    if item is None:
        return False
    if name is not None:
        item["name"] = validate_name(name)
    if box is not None:
        item["box"] = box_json(validate_box(box))
    table.put(item)
    _mark_changed(table, account_id, device_id, now_ms)
    return True


def delete_zone(table: FridgeTable, account_id: str, device_id: str, sk: str, now_ms: int) -> bool:
    """Delete a zone and its references; False if there is no such zone."""
    if not sk.startswith(zone_prefix(device_id)):
        return False
    if not table.delete(account_pk(account_id), sk):
        return False
    for ref in table.query(account_id, ref_prefix(device_id)):
        if ref.get("zone_id") == sk:
            table.delete(account_pk(account_id), ref["sk"])
    _mark_changed(table, account_id, device_id, now_ms)
    return True


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


def _image(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data)).convert("RGB")


def _choose(opened: list[float], closed: list[float]) -> tuple[str, float, float] | None:
    """(direction, threshold, margin) if the values separate, else None."""
    if min(opened) > max(closed):
        return "above", (min(opened) + max(closed)) / 2, min(opened) - max(closed)
    if max(opened) < min(closed):
        return "below", (max(opened) + min(closed)) / 2, min(closed) - max(opened)
    return None


Rule = tuple[str, str, float, float]  # feature, direction, threshold, margin


def choose_feature(values: dict[str, tuple[list[float], list[float]]]) -> Rule | None:
    """The zone's rule from each feature's (open values, closed values), or None.

    `blue` wins whenever it separates: it needs no baseline, so unlike `change` it is not
    thrown off by a picture framed differently from the clips the door check scores.
    Otherwise the largest margin wins, ties keeping the earlier feature in FEATURES."""
    best = None
    for feature in FEATURES:
        rule = _choose(*values[feature])
        if rule is None or rule[2] < MIN_MARGIN:
            continue
        if feature == "blue":
            return (feature, *rule)
        if best is None or rule[2] > best[3]:
            best = (feature, *rule)
    return best


def run(table: FridgeTable, account_id: str, device_id: str, now_ms: int) -> Setup:
    """Work out each zone's rule from the references and store it; SetupFailed leaves the
    stored setup unchanged."""
    zones = list_zones(table, account_id, device_id)
    refs = list_references(table, account_id, device_id)
    images = [_image(r.image) for r in refs]
    scores = {r.sk: measure(img, r.box, "color") for r, img in zip(refs, images, strict=True)}
    if len(zones) > MAX_ZONES:
        raise SetupFailed(f"at most {MAX_ZONES} door zones", scores)
    if not zones:
        raise SetupFailed("add a door zone first", scores)

    chosen: list[SetupZone] = []
    for z in zones:
        zone = z.box
        mine = [i for i, r in enumerate(refs) if r.zone_id == z.sk]
        opened = [images[i] for i in mine if refs[i].status == "open"]
        closed = [images[i] for i in mine if refs[i].status == "closed"]
        if not opened or not closed:
            raise SetupFailed(f"{z.name} needs an open and a closed reference", scores)
        baseline = baseline_of(closed, zone)
        best = choose_feature(
            {
                f: (
                    [measure(img, zone, f, baseline) for img in opened],
                    [measure(img, zone, f, baseline) for img in closed],
                )
                for f in FEATURES
            }
        )
        if best is None:
            raise SetupFailed(f"{z.name}: open and closed references overlap", scores)
        feature, direction, threshold, margin = best
        chosen.append(
            SetupZone(
                zone,
                feature,
                direction,
                round(threshold, 4),
                round(margin, 4),
                baseline,
                zone_id=z.sk,
                name=z.name,
            )
        )

    newest_closed = next(
        img for r, img in zip(reversed(refs), reversed(images), strict=True) if r.status == "closed"
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
                    "zone_id": z.zone_id,
                    "name": z.name,
                }
                for z in chosen
            ],
            "ran_ms": now_ms,
            "ran_at": iso_utc(now_ms),
            # What the whole view looks like closed, for lining up later events' frames
            "anchor": alignment.edges_to_bytes(alignment.edge_map(newest_closed)),
        }
    )
    alignment.reset(table, account_id, device_id)
    from fridgesense import self_tuning  # it builds on this module

    self_tuning.delete_samples(table, account_id, device_id)  # learned against the old setup
    return Setup(tuple(chosen), iso_utc(now_ms), stale=False)


def load_anchor(table: FridgeTable, account_id: str, device_id: str) -> bytes | None:
    """The closed anchor stored by the last setup run (None before setup, or from a run made
    before anchors existed)."""
    item = table.get(account_pk(account_id), setup_sk(device_id))
    if item is None or item.get("anchor") is None:
        return None
    return bytes(item["anchor"])


def load_setup(table: FridgeTable, account_id: str, device_id: str) -> Setup | None:
    item = table.get(account_pk(account_id), setup_sk(device_id))
    if item is None:
        return None
    marker = table.get(account_pk(account_id), marker_sk(device_id))
    stale = marker is not None and int(marker["changed_ms"]) > int(item["ran_ms"])
    tuned_from = item.get("tuned_from")
    return Setup(
        _zones_of(item["zones"]),
        item["ran_at"],
        stale,
        tuned_at=item.get("tuned_at"),
        tuned_from=None if tuned_from is None else int(tuned_from),
        tuned=_zones_of(item.get("tuned_zones") or []),
    )


def _zones_of(items: list[dict]) -> tuple[SetupZone, ...]:
    return tuple(
        SetupZone(
            box=_box_of({"box": z}),
            feature=z["feature"],
            direction=z["direction"],
            threshold=float(z["threshold"]),
            margin=float(z["margin"]),
            baseline=bytes(z["baseline"]),
            zone_id=z.get("zone_id", ""),
            name=z.get("name", ""),
        )
        for z in items
    )


def setup_check(table: FridgeTable, account_id: str, device_id: str) -> DoorCheck | None:
    """The door check from the device's tuned rules, else its setup result; None if setup
    never ran. Zones are where setup put them; the caller applies the camera shift."""
    setup = load_setup(table, account_id, device_id)
    if setup is None:
        return None
    zones = setup.tuned or setup.zones
    rules = tuple(
        ZoneRule(z.box, z.feature, z.direction, z.threshold, z.baseline, z.margin) for z in zones
    )
    return DoorCheck(rules=rules, source="tuned" if setup.tuned else "setup", ran_at=setup.ran_at)


def reference_scores(refs: list[DoorReference], setup: Setup | None) -> dict[str, float | None]:
    """Each reference's value of its setup zone's feature (None: no setup, or the setup has no
    zone with the reference's zone_id)."""
    scores: dict[str, float | None] = {}
    for ref in refs:
        zone = None
        if setup is not None:
            zone = next((z for z in setup.zones if z.zone_id and z.zone_id == ref.zone_id), None)
        scores[ref.sk] = (
            None if zone is None else measure(ref.image, zone.box, zone.feature, zone.baseline)
        )
    return scores
