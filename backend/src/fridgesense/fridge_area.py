"""The owner's box around the fridge in the camera's view, one per device, for cropping
stills later. Stored with the snapshot it was drawn on."""

from dataclasses import dataclass
from typing import Any

from fridgesense.door_calibration import box_json, validate_box
from fridgesense.door_events import Box, iso_utc
from fridgesense.table import FridgeTable, account_pk


def area_sk(device_id: str) -> str:
    return f"FRIDGEAREA#{device_id}"


@dataclass(frozen=True)
class FridgeArea:
    image: bytes
    box: Box
    updated_at: str


def save(
    table: FridgeTable, account_id: str, device_id: str, image: bytes, box: Any, now_ms: int
) -> FridgeArea:
    """Replace the device's fridge area. Raises Invalid for a bad box."""
    area = FridgeArea(image=image, box=validate_box(box), updated_at=iso_utc(now_ms))
    table.put(
        {
            "pk": account_pk(account_id),
            "sk": area_sk(device_id),
            "image": image,  # Binary: 300 KB fits under DynamoDB's 400 KB item limit
            "box": box_json(area.box),
            "updated_at": area.updated_at,
        }
    )
    return area


def load(table: FridgeTable, account_id: str, device_id: str) -> FridgeArea | None:
    item = table.get(account_pk(account_id), area_sk(device_id))
    if item is None:
        return None
    b = item["box"]
    return FridgeArea(
        image=bytes(item["image"]),
        box=(float(b["x"]), float(b["y"]), float(b["width"]), float(b["height"])),
        updated_at=item["updated_at"],
    )


SIDE_MARGIN = 0.10  # of the area's width, each side: hands reach past the doors
END_MARGIN = 0.05  # of the area's height, above and below


def analysis_box(area: Box | None, still_crop: Box | None) -> Box | None:
    """The crop for stored stills and the analysis video: the fridge area plus room for hands,
    clamped to the frame; without an area, STILL_CROP (None: the full frame)."""
    if area is None:
        return still_crop
    x, y, w, h = area
    left, right = max(0.0, x - SIDE_MARGIN * w), min(1.0, x + w + SIDE_MARGIN * w)
    top, bottom = max(0.0, y - END_MARGIN * h), min(1.0, y + h + END_MARGIN * h)
    return (left, top, right - left, bottom - top)
