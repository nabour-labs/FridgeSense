"""The owner's reference images and custom instructions that guide the Nova analysis."""

import base64
import binascii
import secrets
from dataclasses import dataclass, field
from typing import Any

from fridgesense.door_events import iso_utc
from fridgesense.table import FridgeTable, account_pk

MAX_ANNOTATION = 300
MAX_IMAGE_BYTES = 200_000
MAX_INSTRUCTIONS = 1000
MAX_REFERENCES = 30
JPEG_MAGIC = b"\xff\xd8\xff"
REF_PREFIX = "REF#"
INSTRUCTIONS_SK = "CONFIG#instructions"


class Invalid(Exception):
    """A config value the API answers 400 to; `message` is the response's error text."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def validate_annotation(value: Any) -> str:
    text = value.strip() if isinstance(value, str) else ""
    if not 1 <= len(text) <= MAX_ANNOTATION:
        raise Invalid(f"annotation must be 1 to {MAX_ANNOTATION} characters")
    return text


def decode_image(value: Any) -> bytes:
    """The JPEG bytes of a base64 image, at most MAX_IMAGE_BYTES."""
    try:
        data = base64.b64decode(value, validate=True) if isinstance(value, str) else b""
    except (binascii.Error, ValueError):
        data = b""
    if not data.startswith(JPEG_MAGIC) or len(data) > MAX_IMAGE_BYTES:
        raise Invalid("image must be a JPEG of at most 200 KB")
    return data


def validate_instructions(value: Any) -> str:
    if not isinstance(value, str) or len(value.strip()) > MAX_INSTRUCTIONS:
        raise Invalid(f"instructions must be text of at most {MAX_INSTRUCTIONS} characters")
    return value.strip()


class TooMany(Exception):
    """The account already holds MAX_REFERENCES reference images."""


@dataclass
class Reference:
    sk: str
    annotation: str
    image: bytes
    created_at: str


@dataclass
class AnalysisConfig:
    instructions: str = ""
    references: list[Reference] = field(default_factory=list)


def _reference(item: dict) -> Reference:
    return Reference(
        sk=item["sk"],
        annotation=item["annotation"],
        image=base64.b64decode(item["image_b64"]),
        created_at=item["created_at"],
    )


def load(table: FridgeTable, account_id: str) -> AnalysisConfig:
    """The account's instructions and references, oldest reference first."""
    saved = table.get(account_pk(account_id), INSTRUCTIONS_SK)
    refs = sorted(table.query(account_id, REF_PREFIX), key=lambda i: i["sk"])
    return AnalysisConfig(
        instructions=saved.get("text", "") if saved else "",
        references=[_reference(i) for i in refs],
    )


def add_reference(
    table: FridgeTable, account_id: str, annotation: str, image: bytes, now_ms: int
) -> Reference:
    if len(table.query(account_id, REF_PREFIX)) >= MAX_REFERENCES:
        raise TooMany()
    # Zero-padded time first, so sort keys list references oldest first.
    item = {
        "pk": account_pk(account_id),
        "sk": f"{REF_PREFIX}{now_ms:013d}-{secrets.token_hex(3)}",
        "annotation": annotation,
        "image_b64": base64.b64encode(image).decode(),
        "created_at": iso_utc(now_ms),
    }
    table.put(item)
    return _reference(item)


def delete_reference(table: FridgeTable, account_id: str, sk: str) -> bool:
    """False if the account has no such reference."""
    return sk.startswith(REF_PREFIX) and table.delete(account_pk(account_id), sk)


def update_reference(
    table: FridgeTable,
    account_id: str,
    sk: str,
    annotation: str | None,
    image: bytes | None,
    now_ms: int,
) -> bool:
    """Change the annotation and/or image in place, keeping the sort key (so the id and
    order); False if the account has no such reference."""
    item = table.get(account_pk(account_id), sk) if sk.startswith(REF_PREFIX) else None
    if item is None:
        return False
    if annotation is not None:
        item["annotation"] = annotation
    if image is not None:
        item["image_b64"] = base64.b64encode(image).decode()
    table.put({**item, "updated_at": iso_utc(now_ms)})
    return True


def save_instructions(table: FridgeTable, account_id: str, text: str, now_ms: int) -> None:
    table.put(
        {
            "pk": account_pk(account_id),
            "sk": INSTRUCTIONS_SK,
            "text": text,
            "updated_at": iso_utc(now_ms),
        }
    )
