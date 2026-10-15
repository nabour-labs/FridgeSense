"""inventory-api: session tokens for the owner and the read-only demo viewer."""

from fridgesense.session import TTL_S, sign_in, verify
from fridgesense.store import AppConfig

NOW = 1_786_000_000
OWNER = AppConfig(passcode="open-sesame", demo_passcode="look-only")


def test_owner_sign_in_and_verify():
    token, expires_at, role = sign_in(OWNER, "open-sesame", now=NOW)
    assert role == "owner" and expires_at == NOW + TTL_S
    assert TTL_S == 30 * 24 * 3600
    assert verify(OWNER, token, now=NOW + 60) == "owner"


def test_viewer_sign_in_and_verify():
    token, _, role = sign_in(OWNER, "look-only", now=NOW)
    assert role == "viewer"
    assert verify(OWNER, token, now=NOW) == "viewer"


def test_wrong_or_empty_passcode():
    assert sign_in(OWNER, "guess", now=NOW) is None
    assert sign_in(OWNER, "", now=NOW) is None
    assert sign_in(AppConfig(passcode=""), "", now=NOW) is None


def test_expired():
    token, _, _ = sign_in(OWNER, "open-sesame", now=NOW)
    assert verify(OWNER, token, now=NOW + TTL_S) == "owner"
    assert verify(OWNER, token, now=NOW + TTL_S + 1) is None


def test_tampered():
    token, _, _ = sign_in(OWNER, "look-only", now=NOW)
    payload, sig = token.split(".")
    assert verify(OWNER, payload + "." + ("0" if sig[0] != "0" else "1") + sig[1:], now=NOW) is None
    # Swapping the role in the payload breaks the signature.
    owner_token, _, _ = sign_in(OWNER, "open-sesame", now=NOW)
    assert verify(OWNER, owner_token.split(".")[0] + "." + sig, now=NOW) is None
    for junk in ["", "abc", "a.b.c", "!!!.x"]:
        assert verify(OWNER, junk, now=NOW) is None


def test_old_owner_passcode():
    token, _, _ = sign_in(OWNER, "open-sesame", now=NOW)
    changed = OWNER.model_copy(update={"passcode": "new-pass"})
    assert verify(changed, token, now=NOW) is None


def test_viewer_token_after_demo_passcode_changes():
    viewer, _, _ = sign_in(OWNER, "look-only", now=NOW)
    owner, _, _ = sign_in(OWNER, "open-sesame", now=NOW)
    changed = OWNER.model_copy(update={"demo_passcode": "other"})
    assert verify(changed, viewer, now=NOW) is None
    assert verify(changed, owner, now=NOW) == "owner"


def test_viewer_token_with_no_demo_passcode_configured():
    viewer, _, _ = sign_in(OWNER, "look-only", now=NOW)
    assert verify(OWNER.model_copy(update={"demo_passcode": ""}), viewer, now=NOW) is None


def test_owner_passcode_wins_if_both_match():
    same = AppConfig(passcode="x", demo_passcode="x")
    assert sign_in(same, "x", now=NOW)[2] == "owner"
