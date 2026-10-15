"""HMAC helpers shared by the webhook and account linking.

Ring uses one HMAC key for both: webhook signatures are hex, link nonces are base64url.
"""

import base64
import hashlib
import hmac

LINK_MAX_AGE_MS = 600_000


def verify_signature(raw_body: bytes, header: str | None, key: str) -> bool:
    """Check an `X-Signature: sha256=<hex>` header against the raw request body."""
    if not header or not header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(key.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header)


def nonce_for(key: str, time_ms: str, account_id: str) -> str:
    """The nonce Ring puts on the Account Link URL for this account and time."""
    mac = hmac.new(key.encode(), f"{time_ms}:{account_id}".encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac).rstrip(b"=").decode()


def is_fresh(time_ms: str, *, now_ms: int) -> bool:
    """True if a link `time` is at most 10 minutes old and not in the future."""
    try:
        age = now_ms - int(time_ms)
    except ValueError:
        return False
    return 0 <= age <= LINK_MAX_AGE_MS
