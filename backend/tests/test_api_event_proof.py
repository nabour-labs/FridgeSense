"""inventory-api: proof still links on each change of a door event listing."""

from urllib.parse import urlparse

import pytest

from fridgesense.handlers import api
from fridgesense.store import load_app_config
from fridgesense.table import FridgeTable
from tests.api_helpers import NOW, call, configure, link_account, sign_in
from tests.test_api_reads import DAY_MS, HOUR_MS, PK, put_event


@pytest.fixture
def tokens(aws, monkeypatch):
    monkeypatch.setattr(api, "now", lambda: NOW)
    link_account()
    configure(user_passcode="come-in", demo_passcode="look-only")
    load_app_config(refresh=True)
    return {"owner": sign_in(), "user": sign_in("come-in"), "viewer": sign_in("look-only")}


def with_proof(sk: str, proof) -> list[str]:
    """Gives the event's one change this `proof` (None leaves it out); returns its still keys."""
    item = FridgeTable().get(PK, sk)
    [change] = item["changes"]
    if proof is not None:
        change = {**change, "proof": proof}
    FridgeTable().put({**item, "changes": [change]})
    return item["still_keys"]


def proof_of(token, **query) -> list[str]:
    status, body = call("GET", "/api/events", token=token, query=query or None)
    assert status == 200
    [event] = body["events"]
    [change] = event["changes"]
    return change["proof"]


# Scenario: Proof links listed
def test_proof_links_listed(tokens):
    keys = with_proof(put_event(int(NOW * 1000) - HOUR_MS, stills=4), [2, 3])
    links = proof_of(tokens["owner"])
    assert len(links) == 2
    assert all(urlparse(lk).path.endswith(f"/{k}") for lk, k in zip(links, keys[2:], strict=True))
    assert all("X-Amz-Signature" in link for link in links)


# Scenario: Viewer gets proof
def test_viewer_gets_proof(tokens):
    keys = with_proof(put_event(int(NOW * 1000) - HOUR_MS, stills=4), [2, 3])
    links = proof_of(tokens["viewer"])
    assert all(urlparse(lk).path.endswith(f"/{k}") for lk, k in zip(links, keys[2:], strict=True))


# Scenario: Change without proof
def test_change_without_proof(tokens):
    with_proof(put_event(int(NOW * 1000) - HOUR_MS, stills=4), None)
    assert proof_of(tokens["owner"]) == []


# Scenario: Index past the stored stills
def test_index_past_the_stored_stills(tokens):
    keys = with_proof(put_event(int(NOW * 1000) - HOUR_MS, stills=4), [1, 5])
    [link] = proof_of(tokens["owner"])
    assert urlparse(link).path.endswith(f"/{keys[1]}")


# Scenario: Old event
def test_old_event_has_no_proof(tokens):
    with_proof(put_event(int(NOW * 1000) - 8 * DAY_MS, stills=4), [0])
    assert proof_of(tokens["owner"], days="30") == []
