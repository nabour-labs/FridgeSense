"""inventory-api: POST /api/ask answers a fridge question for the app's Ask screen."""

import json
from datetime import UTC, datetime

import pytest

from fridgesense.door_events import iso_utc
from fridgesense.handlers import api
from fridgesense.store import load_app_config
from fridgesense.table import FridgeTable, account_pk
from tests.api_helpers import ACCOUNT, NOW, call, configure, link_account, sign_in
from tests.conftest import api_event

PK = account_pk(ACCOUNT)


@pytest.fixture
def owner(aws, monkeypatch):
    monkeypatch.setattr(api, "now", lambda: NOW)
    link_account()
    return sign_in()


def put_milk(minutes_ago=2):
    FridgeTable().put(
        {
            "pk": PK,
            "sk": "ITEM#milk",
            "name": "Milk",
            "category": "dairy",
            "quantity": 1,
            "last_changed_at": iso_utc(int((NOW - minutes_ago * 60) * 1000)),
        }
    )


# Do I have milk
def test_do_i_have_milk(owner):
    put_milk()
    status, body = call("POST", "/api/ask", {"question": "Do I have milk?"}, owner)
    assert status == 200
    assert body["intent"] == "find_item"
    assert body["answer"] == "Yes, you have 1 milk, changed 2 minutes ago."
    assert body["data"]["query"] == "milk"
    assert body["data"]["in_fridge"] is True
    assert body["data"]["total_count"] == 1
    [match] = body["data"]["matches"]
    assert (match["name"], match["count"], match["minutes_ago"]) == ("Milk", 1, 2)


# Viewer can ask
def test_viewer_can_ask(owner):
    configure(demo_passcode="look-only")
    load_app_config(refresh=True)
    viewer = sign_in("look-only")
    put_milk()
    status, body = call("POST", "/api/ask", {"question": "What's in my fridge?"}, viewer)
    assert status == 200
    assert body["intent"] == "get_inventory"
    assert body["answer"] == "You have 1 item: 1 milk."


# Unknown question
def test_unknown_question(owner):
    status, body = call("POST", "/api/ask", {"question": "Play some jazz"}, owner)
    assert status == 200
    assert body["intent"] == "unknown"
    assert body["answer"].startswith("Try asking:")
    assert body["data"] is None


# No token
def test_no_token(owner):
    status, body = call("POST", "/api/ask", {"question": "Do I have milk?"})
    assert (status, body) == (401, {"error": "sign in"})


def post_raw(raw, token):
    headers = {"content-type": "application/json", "Authorization": f"Bearer {token}"}
    resp = api.handler(api_event("POST", "/api/ask", raw, headers), None)
    return resp["statusCode"], json.loads(resp["body"])


@pytest.fixture
def no_reads(monkeypatch):
    """Fail the test if the route reads the table."""

    def refuse(*args, **kwargs):
        raise AssertionError("table read")

    monkeypatch.setattr(FridgeTable, "query", refuse)
    monkeypatch.setattr(FridgeTable, "query_range", refuse)


# Missing question
@pytest.mark.parametrize(
    "raw", ["{}", '{"question": 5}', '{"question": null}', '{"question": "   "}', "not json", "[]"]
)
def test_missing_question(owner, no_reads, raw):
    assert post_raw(raw, owner) == (400, {"error": "question required"})


# Too long
def test_too_long(owner, no_reads):
    assert post_raw(json.dumps({"question": "m" * 201}), owner) == (
        400,
        {"error": "question required"},
    )


def test_200_characters_is_fine(owner):
    status, _ = call("POST", "/api/ask", {"question": "milk " * 40}, owner)
    assert status == 200


# Activity in the household time zone
LATE_NIGHT = datetime(2026, 10, 15, 5, 0, tzinfo=UTC).timestamp()  # 01:00 Toronto, 22:00 Vancouver


@pytest.mark.parametrize(
    ("time_zone", "opens", "answer"),
    [
        ("America/Toronto", 0, "The fridge hasn't been opened today."),
        ("America/Vancouver", 1, "The fridge was opened 1 time today, for 12 seconds on average."),
    ],
)
def test_activity_in_the_household_time_zone(aws, monkeypatch, time_zone, opens, answer):
    monkeypatch.setattr(api, "now", lambda: LATE_NIGHT)
    monkeypatch.setenv("TIME_ZONE", time_zone)
    link_account()
    token = sign_in()
    opened = int(datetime(2026, 10, 15, 3, 30, tzinfo=UTC).timestamp() * 1000)  # 23:30 Toronto
    FridgeTable().put(
        {
            "pk": PK,
            "sk": f"DOOR#{iso_utc(opened)}#cam",
            "opened_at": iso_utc(opened),
            "duration_s": 12,
            "changes": [],
        }
    )
    question = {"question": "How many times did we open the fridge today?"}
    status, body = call("POST", "/api/ask", question, token)
    assert status == 200
    assert body["data"]["opens"] == opens
    assert body["answer"] == answer
