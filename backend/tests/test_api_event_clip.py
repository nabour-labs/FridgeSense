"""inventory-api: the open-span clip link on door event listings."""

from decimal import Decimal
from urllib.parse import parse_qs, urlparse

import boto3
import pytest

from fridgesense.handlers import api
from fridgesense.store import load_app_config
from fridgesense.table import FridgeTable
from tests.api_helpers import NOW, call, configure, link_account, sign_in
from tests.conftest import BUCKET
from tests.test_api_reads import DAY_MS, HOUR_MS, PK, put_event


@pytest.fixture
def tokens(aws, monkeypatch):
    monkeypatch.setattr(api, "now", lambda: NOW)
    link_account()
    configure(user_passcode="come-in", demo_passcode="look-only")
    load_app_config(refresh=True)
    return {"owner": sign_in(), "user": sign_in("come-in"), "viewer": sign_in("look-only")}


def with_clip(sk: str, opened_ms: int) -> str:
    key = f"accounts/ava1.ring.account.A1/devices/D1/events/{opened_ms}/clip.mp4"
    boto3.client("s3").put_object(Bucket=BUCKET, Key=key, Body=b"mp4")
    item = FridgeTable().get(PK, sk)
    FridgeTable().put({**item, "clip_key": key, "clip_span": [Decimal("0.5"), Decimal("8.5")]})
    return key


def listed(token, **query) -> dict:
    status, body = call("GET", "/api/events", token=token, query=query or None)
    assert status == 200
    [event] = body["events"]
    return event


# Recent event with a clip
@pytest.mark.parametrize("role", ["owner", "user"])
def test_recent_event_with_a_clip(tokens, role):
    opened = int(NOW * 1000) - HOUR_MS
    key = with_clip(put_event(opened, stills=4), opened)
    clip = listed(tokens[role])["clip"]
    link, fragment = clip.split("#")
    assert fragment == "t=0.5,8.5"
    url = urlparse(link)
    q = parse_qs(url.query)
    assert url.path.endswith(f"/{key}")
    assert q["X-Amz-Expires"] == ["900"] and "X-Amz-Signature" in q


# Viewer gets no clip
def test_viewer_gets_no_clip(tokens):
    opened = int(NOW * 1000) - HOUR_MS
    with_clip(put_event(opened, stills=4), opened)
    event = listed(tokens["viewer"])
    assert event["clip"] is None
    assert len(event["stills"]) == 4


# Event without a clip
def test_event_without_a_clip(tokens):
    put_event(int(NOW * 1000) - HOUR_MS, stills=4)
    assert listed(tokens["owner"])["clip"] is None


# Old event
def test_old_event_has_no_clip(tokens):
    opened = int(NOW * 1000) - 8 * DAY_MS
    with_clip(put_event(opened, stills=4), opened)
    event = listed(tokens["owner"], days="30")
    assert event["stills"] == [] and event["clip"] is None
