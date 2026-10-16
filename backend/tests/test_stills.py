"""door-event-detection: Stills across the opening."""

import json

import boto3
import httpx
import pytest
import respx

from fridgesense.door_events import download_all_stills, download_stills, store_blurred_stills
from fridgesense.oauth import OAuthClient
from fridgesense.ring import API_BASE, RingClient
from fridgesense.store import Tokens
from tests.conftest import BUCKET, FakeBlurrer, MemoryTokenStore, jpeg

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
    """The 4-still path (a 10 s interval on a 25 s window), as before dense sampling."""
    ring, http = clients
    return download_stills(
        ring, http, STATE, Sleeps() if sleep is None else sleep, interval_ms=10_000
    )


def store(raw, blurrer=None):
    return store_blurred_stills(
        boto3.client("s3"), BUCKET, FakeBlurrer() if blurrer is None else blurrer, STATE, raw
    )


def s3_keys() -> list[str]:
    listing = boto3.client("s3").list_objects_v2(Bucket=BUCKET)
    return sorted(o["Key"] for o in listing.get("Contents", []))


def stored(key: str) -> bytes:
    return boto3.client("s3").get_object(Bucket=BUCKET, Key=key)["Body"].read()


def redirect_for_each_request(request):
    ts = json.loads(request.content)["timestamp"]
    return httpx.Response(303, headers={"Location": location(ts)})


# Four stills when the interval is longer than a quarter of the window
@respx.mock
def test_four_evenly_spaced_stills(aws, clients):
    post = respx.post(DOWNLOAD).mock(side_effect=redirect_for_each_request)
    respx.get(url__startswith="https://download-us.example.com/").respond(
        200, content=jpeg(0.5), headers={"content-type": "image/jpeg"}
    )
    raw = run(clients)
    assert [n for n, _ in raw] == [1, 2, 3, 4]
    assert s3_keys() == []  # downloads stay in memory
    stills = store(raw)
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
    keys = s3_keys()
    assert keys == [f"{PREFIX}still-{n}.jpg" for n in range(1, 5)]
    assert [k for k, _ in stills] == keys
    head = boto3.client("s3").head_object(Bucket=BUCKET, Key=keys[0])
    assert head["ContentType"] == "image/jpeg"


# Detection sees the downloaded bytes, S3 sees only the result
@respx.mock
def test_s3_stores_only_the_blurred_still(aws, clients):
    respx.post(DOWNLOAD).mock(side_effect=redirect_for_each_request)
    downloaded = jpeg(0.5)
    respx.get(url__startswith="https://download-us.example.com/").respond(200, content=downloaded)
    blurrer = FakeBlurrer(blurred=lambda data: b"blurred:" + data)
    raw = run(clients)
    assert [data for _, data in raw] == [downloaded] * 4
    stills = store(raw, blurrer)
    assert [stored(k) for k, _ in stills] == [b"blurred:" + downloaded] * 4
    assert [data for _, data in stills] == [b"blurred:" + downloaded] * 4
    assert blurrer.contexts == [
        {"account_id": "ava1.ring.account.A1", "device_id": "ava1.ring.device.D1", "still": n}
        for n in range(1, 5)
    ]


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
    assert s3_keys() == []


def test_store_skips_stills_that_fail_detection(aws):
    raw = [(n, jpeg(0.5)) for n in range(1, 5)]
    stills = store(raw, FakeBlurrer(drop={2}))
    assert [k for k, _ in stills] == [f"{PREFIX}still-{n}.jpg" for n in (1, 3, 4)]
    assert s3_keys() == [k for k, _ in stills]


# pipeline-debug-traces: every requested still with its missing status
def run_all(clients):
    ring, http = clients
    return download_all_stills(ring, http, STATE, Sleeps(), interval_ms=10_000)


@respx.mock
def test_all_stills_report_forbidden_status(aws, clients):
    answers = iter(
        [httpx.Response(303, headers={"Location": location(1)})]
        + [httpx.Response(403, json={"errors": [{"status": "403"}]})] * 3
    )
    respx.post(DOWNLOAD).mock(side_effect=lambda request: next(answers))
    respx.get(url__startswith="https://download-us.example.com/").respond(200, content=jpeg(0.5))
    stills = run_all(clients)
    assert [(s.n, s.at_ms, s.status) for s in stills] == [
        (1, 1786715601000, None),
        (2, 1786715606000, 403),
        (3, 1786715611000, 403),
        (4, 1786715616000, 403),
    ]
    assert stills[0].data == jpeg(0.5)
    assert [s.data for s in stills[1:]] == [None, None, None]


@respx.mock
def test_all_stills_report_not_ready_after_retries(aws, clients):
    respx.post(DOWNLOAD).respond(416)
    assert [s.status for s in run_all(clients)] == [416] * 4


@respx.mock
def test_all_stills_ring_error_has_no_status(aws, clients):
    respx.post(DOWNLOAD).mock(side_effect=httpx.ConnectError("down"))
    stills = run_all(clients)
    assert [(s.data, s.status) for s in stills] == [(None, None)] * 4
