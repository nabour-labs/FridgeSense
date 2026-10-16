"""App session tokens: signed with a key derived from the role's passcode.

Changing a passcode invalidates that role's tokens; there is no separate secret.
"""

import base64
import hashlib
import hmac
import json
from typing import Literal

from fridgesense.store import AppConfig

TTL_S = 24 * 3600  # sign in again once a day
Role = Literal["owner", "user", "viewer"]
ROLES: tuple[Role, ...] = ("owner", "user", "viewer")  # sign-in order when passcodes match


def _key(passcode: str) -> bytes:
    # v2 since tokens last 24 h: v1 (30-day) tokens no longer verify.
    return hmac.new(passcode.encode(), b"fridgesense-session-v2", hashlib.sha256).digest()


def _passcode_for(cfg: AppConfig, role: str) -> str:
    passcodes = {"owner": cfg.passcode, "user": cfg.user_passcode, "viewer": cfg.demo_passcode}
    return passcodes.get(role, "")


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def issue(cfg: AppConfig, role: Role, now: int) -> tuple[str, int]:
    exp = now + TTL_S
    payload = _b64(json.dumps({"exp": exp, "role": role}, separators=(",", ":")).encode())
    sig = hmac.new(_key(_passcode_for(cfg, role)), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}", exp


def sign_in(cfg: AppConfig, passcode: str, now: int) -> tuple[str, int, Role] | None:
    """(token, expires_at, role) for a matching passcode, checked in ROLES order."""
    for role in ROLES:
        expected = _passcode_for(cfg, role)
        if expected and hmac.compare_digest(passcode.encode(), expected.encode()):
            token, exp = issue(cfg, role, now)
            return token, exp, role
    return None


def verify(cfg: AppConfig, token: str, now: int) -> Role | None:
    """The token's role if it is genuine and unexpired, else None."""
    try:
        payload, sig = token.split(".")
        claims = json.loads(_unb64(payload))
        role, exp = claims["role"], int(claims["exp"])
    except (ValueError, KeyError, TypeError):
        return None
    passcode = _passcode_for(cfg, role)
    if not passcode:
        return None
    expected = hmac.new(_key(passcode), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return None
    return role if now <= exp else None
