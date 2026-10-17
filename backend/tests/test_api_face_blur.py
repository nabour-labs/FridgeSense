"""face-blur-setting: GET and PUT /api/settings/face-blur."""

import json
import logging

import pytest

from fridgesense.handlers import api
from fridgesense.store import load_app_config
from tests.api_helpers import NOW, call, configure, link_account, sign_in
from tests.conftest import api_event

PATH = "/api/settings/face-blur"


@pytest.fixture
def tokens(aws, monkeypatch):
    monkeypatch.setattr(api, "now", lambda: NOW)
    link_account()
    configure(demo_passcode="look-only", user_passcode="family")
    load_app_config(refresh=True)
    return {"owner": sign_in(), "user": sign_in("family"), "viewer": sign_in("look-only")}


def logged(caplog, event: str) -> list[dict]:
    return [json.loads(r.getMessage()) for r in caplog.records if f'"{event}"' in r.getMessage()]


# Default is on
def test_default_is_on(tokens):
    assert call("GET", PATH, token=tokens["viewer"]) == (200, {"enabled": True})


# Saved off
def test_saved_off(tokens):
    call("PUT", PATH, {"enabled": False}, tokens["owner"])
    assert call("GET", PATH, token=tokens["user"]) == (200, {"enabled": False})


# Not signed in
def test_not_signed_in(tokens):
    assert call("GET", PATH) == (401, {"error": "sign in"})


# Owner turns blurring off
def test_owner_turns_blurring_off(tokens, caplog):
    caplog.set_level(logging.INFO)
    assert call("PUT", PATH, {"enabled": False}, tokens["owner"]) == (200, {"enabled": False})
    assert call("GET", PATH, token=tokens["owner"]) == (200, {"enabled": False})
    [line] = logged(caplog, "face_blur_changed")
    assert line["enabled"] is False


# Owner turns blurring back on
def test_owner_turns_blurring_back_on(tokens):
    call("PUT", PATH, {"enabled": False}, tokens["owner"])
    assert call("PUT", PATH, {"enabled": True}, tokens["owner"]) == (200, {"enabled": True})
    assert call("GET", PATH, token=tokens["owner"]) == (200, {"enabled": True})


# User cannot change it
def test_user_cannot_change_it(tokens):
    assert call("PUT", PATH, {"enabled": False}, tokens["user"]) == (403, {"error": "admin only"})
    assert call("GET", PATH, token=tokens["owner"]) == (200, {"enabled": True})


# Viewer cannot change it
def test_viewer_cannot_change_it(tokens):
    assert call("PUT", PATH, {"enabled": False}, tokens["viewer"]) == (403, {"error": "read-only"})
    assert call("GET", PATH, token=tokens["owner"]) == (200, {"enabled": True})


# Bad body
@pytest.mark.parametrize("body", [{"enabled": "no"}, {"enabled": 0}, {}, ["enabled"]])
def test_bad_body(tokens, body):
    assert call("PUT", PATH, body, tokens["owner"]) == (400, {"error": "bad setting"})
    assert call("GET", PATH, token=tokens["owner"]) == (200, {"enabled": True})


def test_bad_body_not_json(tokens):
    headers = {"content-type": "application/json", "Authorization": f"Bearer {tokens['owner']}"}
    resp = api.handler(api_event("PUT", PATH, "{not json", headers), None)
    assert resp["statusCode"] == 400
    assert json.loads(resp["body"]) == {"error": "bad setting"}
