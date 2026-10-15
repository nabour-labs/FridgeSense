"""Structured JSON logging that never writes secrets."""

import json
import logging
from typing import Any

logger = logging.getLogger("fridgesense")

REDACTED = "[redacted]"
_EXACT = {"code", "passcode", "hmac_key", "authorization"}


def _is_secret(key: str) -> bool:
    # "access_token" is secret; token counts like "input_tokens" are not.
    k = key.lower()
    return k in _EXACT or k.endswith("token") or "secret" in k


def redact(value: Any) -> Any:
    """Return a copy of `value` with every secret-looking key's value replaced."""
    if isinstance(value, dict):
        return {k: REDACTED if _is_secret(str(k)) else redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def log_event(event: str, level: int = logging.INFO, **fields: Any) -> None:
    logger.log(level, json.dumps(redact({"event": event, **fields}), default=str))
