"""Redaction for log lines (ring-account-link: Secrets never logged) and log-hygiene."""

import json
import logging
import os
import subprocess
import sys

import httpx
import pytest
import respx

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


def test_token_counts_are_not_redacted():
    assert redact({"input_tokens": 1180, "security_token": "x"}) == {
        "input_tokens": 1180,
        "security_token": "[redacted]",
    }


HANDLERS = ["api", "http", "mcp", "pipeline", "token_refresh"]


# Scenario: Handler muted on import
@pytest.mark.parametrize("name", HANDLERS)
def test_handler_muted_on_import(name):
    code = (
        f"import logging, fridgesense.handlers.{name}; "
        # The handlers raise the root logger to INFO when called.
        "logging.getLogger().setLevel(logging.INFO); "
        "print(logging.getLogger('httpx').getEffectiveLevel())"
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "AWS_DEFAULT_REGION": "us-east-1"},
    )
    assert int(out.stdout.strip().splitlines()[-1]) >= logging.WARNING


# Scenario: Signed URL fetched during a pipeline run
@respx.mock
def test_signed_url_not_logged(caplog):
    import fridgesense.handlers.pipeline  # noqa: F401  (the import mutes httpx)

    url = "https://media.example/clip.mp4?security_token=abc"
    respx.get(url).respond(200)
    with caplog.at_level(logging.INFO):
        httpx.get(url)
    assert not any("security_token=abc" in r.getMessage() for r in caplog.records)
