"""What changed in the fridge: one Bedrock Nova request per door opening."""

import logging
import os
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Literal

from botocore.exceptions import ClientError
from pydantic import BaseModel, ValidationError, field_validator

from fridgesense.logs import log_event

DEFAULT_MODEL_ID = "us.amazon.nova-2-lite-v1:0"
DEFAULT_PRICE_IN = 0.00033  # USD per 1K input tokens (Nova 2 Lite, us. profile)
DEFAULT_PRICE_OUT = 0.00275  # USD per 1K output tokens
TOOL_NAME = "record_fridge_changes"
MAX_IMAGES = 4
CATEGORIES = [
    "dairy",
    "produce",
    "meat",
    "seafood",
    "beverage",
    "snack",
    "condiment",
    "leftovers",
    "bakery",
    "frozen",
    "other",
]
RETRYABLE = {
    "ThrottlingException",
    "ModelTimeoutException",
    "ServiceUnavailableException",
    "InternalServerException",
}

_CHANGE_SCHEMA = {
    "type": "object",
    "properties": {
        "item": {"type": "string", "description": "Item type, e.g. milk, eggs, soda can"},
        "category": {"type": "string", "enum": CATEGORIES},
        "quantity": {"type": "integer", "description": "How many whole items"},
        "confidence": {"type": "number", "description": "0 to 1; below 0.7 means unsure"},
    },
    "required": ["item", "category", "quantity", "confidence"],
}
TOOL_SPEC = {
    "toolSpec": {
        "name": TOOL_NAME,
        "description": "Record the items put into and taken out of the fridge in this opening.",
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "added": {"type": "array", "items": _CHANGE_SCHEMA},
                    "removed": {"type": "array", "items": _CHANGE_SCHEMA},
                },
                "required": ["added", "removed"],
            }
        },
    }
}
INSTRUCTIONS = (
    "The images above are stills from a camera watching a fridge, in time order, "
    "while the door was open. Compare them and report what was put into the fridge "
    "(added) and what was taken out (removed).\n"
    "- Name item types, not brands (milk, eggs, chocolate bar, soda can).\n"
    "- Reuse a name from the current inventory when it is the same kind of item.\n"
    "- Count whole items; use quantity 1 if unsure of the count.\n"
    "- Set confidence from 0 to 1; use less than 0.7 when you are unsure.\n"
    "- If nothing was added or removed, return empty lists.\n"
    "Current inventory: {inventory}\n"
)
TOOL_LINE = f"Call {TOOL_NAME} with your answer."
REFERENCE_HEADER = (
    "Reference images: examples of items in this fridge. They are not part of this door opening."
)


class BedrockRetryable(Exception):
    """Throttling, timeout or a Bedrock server error: the workflow retries."""


class BedrockRejected(Exception):
    """Bedrock refused the request (validation, access): retrying will not help."""


class Change(BaseModel):
    item: str
    category: str = "other"
    quantity: int = 1
    confidence: float = 0.0

    @field_validator("item")
    @classmethod
    def _item(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("empty item")
        return v.strip()

    @field_validator("category", mode="before")
    @classmethod
    def _category(cls, v: Any) -> str:
        v = str(v).strip().lower() if v is not None else ""
        return v if v in CATEGORIES else "other"

    @field_validator("quantity", mode="before")
    @classmethod
    def _quantity(cls, v: Any) -> int:
        try:
            q = int(v)
        except (TypeError, ValueError):
            return 1
        return q if q >= 1 else 1

    @field_validator("confidence", mode="before")
    @classmethod
    def _confidence(cls, v: Any) -> float:
        try:
            c = float(v)
        except (TypeError, ValueError):
            return 0.0
        return min(max(c, 0.0), 1.0)


class FridgeChanges(BaseModel):
    added: list[Change]
    removed: list[Change]


@dataclass
class Usage:
    input_tokens: int
    output_tokens: int
    usd: float


@dataclass
class AnalysisResult:
    changes: FridgeChanges | None
    usage: list[Usage] = field(default_factory=list)

    @property
    def usd(self) -> float:
        return round(sum(u.usd for u in self.usage), 6)


def build_request(
    model_id: str,
    stills: list[bytes],
    inventory: list[str],
    references: Sequence[tuple[str, bytes]] = (),
    instructions: str = "",
) -> dict:
    """References (annotation, JPEG) go first, then the stills; the owner's instructions
    sit in the final text before the tool line. Without config the request is unchanged."""
    content: list[dict] = []
    if references:
        content.append({"text": REFERENCE_HEADER})
        for n, (annotation, data) in enumerate(references, start=1):
            content.append({"text": f"Reference {n}: {annotation}"})
            content.append({"image": {"format": "jpeg", "source": {"bytes": data}}})
    images = stills[:MAX_IMAGES]
    for n, data in enumerate(images, start=1):
        content.append({"text": f"Image {n} of {len(images)}"})
        content.append({"image": {"format": "jpeg", "source": {"bytes": data}}})
    text = INSTRUCTIONS.format(inventory="[" + ", ".join(inventory) + "]")
    if instructions:
        text += f"Owner's instructions: {instructions}\n"
    content.append({"text": text + TOOL_LINE})
    return {
        "modelId": model_id,
        "messages": [{"role": "user", "content": content}],
        "inferenceConfig": {"maxTokens": 1024, "temperature": 0},
        "toolConfig": {"tools": [TOOL_SPEC], "toolChoice": {"tool": {"name": TOOL_NAME}}},
    }


def parse_response(resp: dict) -> FridgeChanges | None:
    """The validated tool input, or None if Nova did not answer with the tool."""
    for block in resp.get("output", {}).get("message", {}).get("content", []):
        tool = block.get("toolUse")
        if tool and tool.get("name") == TOOL_NAME:
            try:
                return FridgeChanges.model_validate(tool.get("input"))
            except ValidationError:
                return None
    return None


def cost_usd(input_tokens: int, output_tokens: int, price_in: float, price_out: float) -> float:
    """USD for one call, rounded half-up to 6 decimals (exact decimal math, no float drift)."""
    usd = (
        Decimal(input_tokens) * Decimal(str(price_in))
        + Decimal(output_tokens) * Decimal(str(price_out))
    ) / 1000
    return float(usd.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


Kind = Literal["retryable", "rejected"]


class NovaAnalyzer:
    def __init__(
        self,
        client,
        model_id: str = DEFAULT_MODEL_ID,
        price_in: float = DEFAULT_PRICE_IN,
        price_out: float = DEFAULT_PRICE_OUT,
        attempts: int = 2,
    ):
        self.client = client
        self.model_id = model_id
        self.price_in = price_in
        self.price_out = price_out
        self.attempts = attempts

    @classmethod
    def from_env(cls, client) -> "NovaAnalyzer":
        return cls(
            client,
            model_id=os.environ.get("NOVA_MODEL_ID") or DEFAULT_MODEL_ID,
            price_in=float(os.environ.get("NOVA_PRICE_IN") or DEFAULT_PRICE_IN),
            price_out=float(os.environ.get("NOVA_PRICE_OUT") or DEFAULT_PRICE_OUT),
        )

    def analyze(
        self,
        stills: list[bytes],
        inventory: list[str],
        context: dict | None = None,
        references: Sequence[tuple[str, bytes]] = (),
        instructions: str = "",
    ) -> AnalysisResult:
        """Ask Nova; one more request if the answer is invalid. Raises BedrockRetryable
        or BedrockRejected for API errors."""
        result = AnalysisResult(changes=None)
        request = build_request(self.model_id, stills, inventory, references, instructions)
        for _ in range(self.attempts):
            try:
                resp = self.client.converse(**request)
            except ClientError as e:
                code = e.response["Error"]["Code"]
                log_event("nova_error", logging.WARNING, code=code, **(context or {}))
                if code in RETRYABLE:
                    raise BedrockRetryable(code) from None
                raise BedrockRejected(code) from None
            usage = resp.get("usage", {})
            spent = Usage(
                input_tokens=int(usage.get("inputTokens", 0)),
                output_tokens=int(usage.get("outputTokens", 0)),
                usd=cost_usd(
                    int(usage.get("inputTokens", 0)),
                    int(usage.get("outputTokens", 0)),
                    self.price_in,
                    self.price_out,
                ),
            )
            result.usage.append(spent)
            log_event(
                "nova_cost",
                model_id=self.model_id,
                input_tokens=spent.input_tokens,
                output_tokens=spent.output_tokens,
                usd=spent.usd,
                **(context or {}),
            )
            changes = parse_response(resp)
            if changes is not None:
                result.changes = changes
                return result
            log_event(
                "nova_invalid_answer",
                logging.WARNING,
                stop_reason=resp.get("stopReason"),
                **(context or {}),
            )
        return result
