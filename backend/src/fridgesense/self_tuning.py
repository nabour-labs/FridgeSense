"""Learning from recent activity: what each door zone looked like closed and open in recent
events, and the door rules re-tuned from those samples plus the owner's references."""

import logging
from dataclasses import dataclass

from PIL import Image

from fridgesense import door_calibration as dc
from fridgesense.alignment import Alignment
from fridgesense.door_events import (
    FEATURES,
    Box,
    DoorCheck,
    _crop_box,
    _open_rgb,
    _thumb,
    iso_utc,
    measure,
)
from fridgesense.logs import log_event
from fridgesense.table import FridgeTable, account_pk

KEEP = 20  # newest sample events per device
MIN_OPEN_CHANGE = 0.08  # measured: real openings 0.10-0.22, no opening 0.03-0.05
MIN_SAMPLES = 3  # open and closed samples per zone before a re-tune
VALUE_FEATURES = ("color", "blue", "brightness")


def sample_prefix(device_id: str) -> str:
    return f"DOORSAMPLE#{device_id}#"


@dataclass(frozen=True)
class Look:
    """One zone in one frame: its feature values and its 32x32 RGB thumbnail."""

    color: float
    blue: float
    brightness: float
    thumb: bytes


@dataclass(frozen=True)
class ZoneSample:
    closed: Look | None
    open: Look | None


@dataclass(frozen=True)
class SampleEvent:
    at_ms: int
    zones: tuple[ZoneSample, ...]


def _look(img: Image.Image, box: Box) -> Look:
    return Look(
        color=measure(img, box, "color"),
        blue=measure(img, box, "blue"),
        brightness=measure(img, box, "brightness"),
        thumb=_thumb(_crop_box(img, box)),
    )


def _change(thumb: bytes, baseline: bytes) -> float:
    return sum(abs(a - b) for a, b in zip(thumb, baseline, strict=True)) / len(thumb) / 255


def sample_event(
    check: DoorCheck, frames: list[bytes | Image.Image], used: str
) -> tuple[ZoneSample, ...]:
    """Each zone's closed look (the alignment bookend, if the rules call it closed there) and
    open look (the frame that differs most from it, if clearly)."""
    images = [_open_rgb(f) for f in frames]
    bookend = 0 if used == "first" else len(images) - 1
    zones = []
    for rule in check.rules:
        closed_img = images[bookend]
        if rule.is_open(rule.value(closed_img)):
            zones.append(ZoneSample(None, None))
            continue
        closed = _look(closed_img, rule.box)
        best, best_change = None, MIN_OPEN_CHANGE
        for k, img in enumerate(images):
            if k == bookend:
                continue
            change = _change(_thumb(_crop_box(img, rule.box)), closed.thumb)
            if change >= best_change:
                best, best_change = img, change
        zones.append(ZoneSample(closed, None if best is None else _look(best, rule.box)))
    return tuple(zones)


def _look_json(look: Look | None) -> dict | None:
    if look is None:
        return None
    return {
        "color": look.color,
        "blue": look.blue,
        "brightness": look.brightness,
        "thumb": look.thumb,
    }


def _look_of(item: dict | None) -> Look | None:
    if item is None:
        return None
    return Look(
        float(item["color"]), float(item["blue"]), float(item["brightness"]), bytes(item["thumb"])
    )


def store_sample(table: FridgeTable, account_id: str, device_id: str, at_ms: int, zones) -> None:
    """Store one event's samples and keep only the newest KEEP events."""
    table.put(
        {
            "pk": account_pk(account_id),
            "sk": f"{sample_prefix(device_id)}{at_ms:013d}",
            "zones": [{"closed": _look_json(z.closed), "open": _look_json(z.open)} for z in zones],
        }
    )
    items = sorted(table.query(account_id, sample_prefix(device_id)), key=lambda i: i["sk"])
    for item in items[:-KEEP]:
        table.delete(item["pk"], item["sk"])


def list_samples(table: FridgeTable, account_id: str, device_id: str) -> list[SampleEvent]:
    """The device's sample events, oldest first."""
    items = sorted(table.query(account_id, sample_prefix(device_id)), key=lambda i: i["sk"])
    return [
        SampleEvent(
            at_ms=int(i["sk"].removeprefix(sample_prefix(device_id))),
            zones=tuple(ZoneSample(_look_of(z["closed"]), _look_of(z["open"])) for z in i["zones"]),
        )
        for i in items
    ]


def delete_samples(table: FridgeTable, account_id: str, device_id: str) -> None:
    for item in table.query(account_id, sample_prefix(device_id)):
        table.delete(item["pk"], item["sk"])


def learn(
    table: FridgeTable,
    account_id: str,
    device_id: str,
    check: DoorCheck,
    frames: list[bytes | Image.Image],
    aligned: Alignment | None,
    at_ms: int,
) -> bool:
    """Sample an aligned event (scored with `check`, already shifted); False if not aligned."""
    if aligned is None or not aligned.ok or len(frames) < 2:
        return False
    store_sample(table, account_id, device_id, at_ms, sample_event(check, frames, aligned.used))
    return True


def _mean_thumb(thumbs: list[bytes]) -> bytes:
    return bytes(round(sum(px) / len(thumbs)) for px in zip(*thumbs, strict=True))


def _zone_rule(zone: dc.SetupZone, refs, images, events, k: int):
    """(feature, direction, threshold, margin, baseline, samples used) for one zone, or None
    when there are too few samples or no feature separates."""
    opened = [e.zones[k].open for e in events if e.zones[k].open is not None]
    closed = [e.zones[k].closed for e in events if e.zones[k].closed is not None]
    if len(opened) < MIN_SAMPLES or len(closed) < MIN_SAMPLES:
        return None
    mine = [i for i, r in enumerate(refs) if dc.iou(r.box, zone.box) >= dc.GROUP_IOU]
    ref_open = [images[i] for i in mine if refs[i].status == "open"]
    ref_closed = [images[i] for i in mine if refs[i].status == "closed"]
    ref_thumbs = [_thumb(_crop_box(img, zone.box)) for img in ref_closed]
    baseline = _mean_thumb(ref_thumbs + [s.thumb for s in closed])

    def values(feature: str, imgs, looks) -> list[float]:
        if feature == "change":
            from_refs = [measure(img, zone.box, "change", baseline) for img in imgs]
            return from_refs + [_change(s.thumb, baseline) for s in looks]
        return [measure(img, zone.box, feature) for img in imgs] + [
            getattr(s, feature) for s in looks
        ]

    best = None
    for feature in FEATURES:  # ties keep the earlier feature, as in setup
        rule = dc._choose(values(feature, ref_open, opened), values(feature, ref_closed, closed))
        if rule and rule[2] >= dc.MIN_MARGIN and (best is None or rule[2] > best[3]):
            best = (feature, *rule)
    if best is None:
        return None
    return (*best, baseline, len(opened) + len(closed))


def retune(table: FridgeTable, account_id: str, device_id: str, now_ms: int) -> bool:
    """Re-run setup's rule choice on the owner's references plus the samples; store the result
    as the tuned rules only if every zone separates. False when nothing was stored."""
    setup = dc.load_setup(table, account_id, device_id)
    if setup is None:
        return False
    events = [
        e for e in list_samples(table, account_id, device_id) if len(e.zones) == len(setup.zones)
    ]
    refs = dc.list_references(table, account_id, device_id)
    images = [_open_rgb(r.image) for r in refs]
    tuned, used = [], 0
    for k, zone in enumerate(setup.zones):
        found = _zone_rule(zone, refs, images, events, k)
        if found is None:
            log_event("door_retune_skipped", logging.INFO, device_id=device_id, zone=k + 1)
            return False
        feature, direction, threshold, margin, baseline, n = found
        used += n
        tuned.append(
            {
                **dc.box_json(zone.box),
                "feature": feature,
                "direction": direction,
                "threshold": round(threshold, 4),
                "margin": round(margin, 4),
                "baseline": baseline,
            }
        )
    table.update(
        account_pk(account_id),
        dc.setup_sk(device_id),
        {"tuned_zones": tuned, "tuned_at": iso_utc(now_ms), "tuned_from": used},
    )
    log_event("door_retuned", device_id=device_id, samples=used)
    return True
