"""Signature, nonce and freshness helpers (ring-webhook-intake, ring-account-link)."""

import base64
import hashlib
import hmac

from fridgesense.crypto import is_fresh, nonce_for, verify_signature

KEY = "test-hmac-key"
BODY = b'{"meta":{"request_id":"R1"}}'


def sign(body: bytes, key: str = KEY) -> str:
    return "sha256=" + hmac.new(key.encode(), body, hashlib.sha256).hexdigest()


# ring-webhook-intake: Valid signature
def test_valid_signature():
    assert verify_signature(BODY, sign(BODY), KEY)


# ring-webhook-intake: Invalid signature
def test_invalid_signature():
    assert not verify_signature(BODY, "sha256=" + "0" * 64, KEY)
    assert not verify_signature(BODY, sign(BODY, "other-key"), KEY)
    assert not verify_signature(BODY + b" ", sign(BODY), KEY)


def test_signature_without_prefix_is_rejected():
    assert not verify_signature(BODY, sign(BODY).removeprefix("sha256="), KEY)


# ring-webhook-intake: Missing signature header
def test_missing_signature_header():
    assert not verify_signature(BODY, None, KEY)
    assert not verify_signature(BODY, "", KEY)


def test_nonce_matches_ring_formula():
    mac = hmac.new(KEY.encode(), b"1771130906289:ava1.ring.account.A1", hashlib.sha256).digest()
    expected = base64.urlsafe_b64encode(mac).rstrip(b"=").decode()
    assert nonce_for(KEY, "1771130906289", "ava1.ring.account.A1") == expected
    assert "=" not in expected


# ring-account-link: Nonce does not match
def test_nonce_differs_for_another_account_or_time():
    n = nonce_for(KEY, "1771130906289", "ava1.ring.account.A1")
    assert n != nonce_for(KEY, "1771130906289", "ava1.ring.account.B2")
    assert n != nonce_for(KEY, "1771130906290", "ava1.ring.account.A1")


NOW_MS = 1_771_131_000_000


def test_fresh_within_window():
    assert is_fresh(str(NOW_MS - 600_000), now_ms=NOW_MS)
    assert is_fresh(str(NOW_MS), now_ms=NOW_MS)


# ring-account-link: Stale link request
def test_stale_link_request():
    assert not is_fresh(str(NOW_MS - 601_000), now_ms=NOW_MS)


# ring-account-link: Time in the future
def test_time_in_the_future():
    assert not is_fresh(str(NOW_MS + 1), now_ms=NOW_MS)


def test_time_not_a_number():
    assert not is_fresh("yesterday", now_ms=NOW_MS)
