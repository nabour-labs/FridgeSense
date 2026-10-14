"""Redaction for log lines (ring-account-link: Secrets never logged)."""

import json
import logging

from fridgesense.logs import log_event, redact

SECRET_KEYS = ["code", "access_token", "refresh_token", "client_secret", "passcode", "hmac_key"]


def test_redact_drops_secret_keys_at_any_depth():
    data = {k: "s3cret" for k in SECRET_KEYS}
    data["nested"] = {"inner": [{"refresh_token": "s3cret", "ok": 1}]}
    data["account_id"] = "ava1.ring.account.A1"
    out = redact(data)
    assert "s3cret" not in json.dumps(out)
    assert out["account_id"] == "ava1.ring.account.A1"
    assert out["nested"]["inner"][0]["ok"] == 1


def test_redact_does_not_modify_input():
    data = {"access_token": "at1"}
    redact(data)
    assert data == {"access_token": "at1"}


def test_log_event_writes_redacted_json(caplog):
    caplog.set_level(logging.INFO)
    log_event("token_exchange", code="abc123", account_id="A1")
    record = json.loads(caplog.records[-1].getMessage())
    assert record == {"event": "token_exchange", "code": "[redacted]", "account_id": "A1"}
