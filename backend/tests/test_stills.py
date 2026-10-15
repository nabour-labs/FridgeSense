"""door-event-detection: Stills across the opening."""

import json

import boto3
import httpx
import pytest
import respx

from fridgesense.door_events import download_stills
from fridgesense.oauth import OAuthClient
from fridgesense.ring import API_BASE, RingClient
from fridgesense.store import Tokens
from tests.conftest import BUCKET, MemoryTokenStore, jpeg

NOW = 1_786_715_700.0
DOWNLOAD = f"{API_BASE}/v1/devices/ava1.ring.device.D1/media/image/download"
STATE = {
    "account_id": "ava1.ring.account.A1",
    "device_id": "ava1.ring.device.D1",
    "timestamp_ms": 1786715596787,
    "window": {
        "status": "ready",
        "start_ms": 1786715596000,
        "end_ms": 1786715621000,
        "ring_event_id": "evt_1786715596000",
    },
}
PREFIX = "accounts/ava1.ring.account.A1/devices/ava1.ring.device.D1/events/1786715596000/"


def location(ts: int) -> str:
    return f"https://download-us.example.com/v1/download?security_token=tok&ts={ts}"


@pytest.fixture
def clients():
    tokens = Tokens(
        account_id="ava1.ring.account.A1",
        access_token="at1",
        refresh_token="rt1",
        expires_at=int(NOW) + 3600,
        link_status="linked",
    )
    with httpx.Client() as http:
        ring = RingClient(http, MemoryTokenStore(tokens), OAuthClient(http, "c", "s"), lambda: NOW)
        yield ring, http


class Sleeps(list):
    def __call__(self, seconds):
        self.append(seconds)


def run(clients, sleep=None):
    ring, http = clients
    return download_stills(
        ring, http, boto3.client("s3"), BUCKET, STATE, Sleeps() if sleep is None else sleep
    )


def redirect_for_each_request(request):
    ts = json.loads(request.content)["timestamp"]
    return httpx.Response(303, headers={"Location": location(ts)})


# Four stills saved
@respx.mock
def test_four_stills_saved(aws, clients):
    post = respx.post(DOWNLOAD).mock(side_effect=redirect_for_each_request)
    respx.get(url__startswith="https://download-us.example.com/").respond(
        200, content=jpeg(0.5), headers={"content-type": "image/jpeg"}
    )
    stills = run(clients)
    bodies = [json.loads(c.request.content) for c in post.calls]
    assert [b["timestamp"] for b in bodies] == [
        1786715601000,
        1786715606000,
        1786715611000,
        1786715616000,
    ]
    assert all(
        b["type"] == "at_timestamp" and b["image_options"] == {"format": "jpeg"} for b in bodies
    )
    keys = sorted(o["Key"] for o in boto3.client("s3").list_objects_v2(Bucket=BUCKET)["Contents"])
    assert keys == [f"{PREFIX}still-{n}.jpg" for n in range(1, 5)]
    assert [k for k, _ in stills] == keys
    head = boto3.client("s3").head_object(Bucket=BUCKET, Key=keys[0])
    assert head["ContentType"] == "image/jpeg"


# Download link gets no token
@respx.mock
def test_download_link_gets_no_token(aws, clients):
    post = respx.post(DOWNLOAD).mock(side_effect=redirect_for_each_request)
    get = respx.get(url__startswith="https://download-us.example.com/").respond(
        200, content=jpeg(0.5)
    )
    run(clients)
    assert post.calls.last.request.headers["authorization"] == "Bearer at1"
    assert all("authorization" not in c.request.headers for c in get.calls)


# Still not ready yet
@respx.mock
@pytest.mark.parametrize("status", [425, 416])
def test_still_not_ready_yet(aws, clients, status):
    answers = iter(
        [httpx.Response(status, json={"errors": [{"status": str(status)}]})] * 2
        + [httpx.Response(303, headers={"Location": location(1)})] * 10
    )
    post = respx.post(DOWNLOAD).mock(side_effect=lambda request: next(answers))
    respx.get(url__startswith="https://download-us.example.com/").respond(200, content=jpeg(0.5))
    sleeps = Sleeps()
    stills = run(clients, sleeps)
    assert len(stills) == 4
    assert post.call_count == 6  # first still took 3 attempts
    assert sleeps == [3, 6]


@respx.mock
def test_still_gives_up_after_three_attempts(aws, clients):
    post = respx.post(DOWNLOAD).respond(425)
    assert run(clients) == []
    assert post.call_count == 12  # 4 stills x 3 attempts


# Too few stills
@respx.mock
def test_too_few_stills_forbidden_time_range(aws, clients):
    respx.post(DOWNLOAD).respond(403, json={"errors": [{"status": "403"}]})
    assert run(clients) == []
    assert "Contents" not in boto3.client("s3").list_objects_v2(Bucket=BUCKET)
