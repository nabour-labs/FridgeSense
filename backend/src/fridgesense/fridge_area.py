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
