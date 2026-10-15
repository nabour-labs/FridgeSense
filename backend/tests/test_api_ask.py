"""inventory-api: POST /api/ask answers a fridge question for the app's Ask screen."""

import json
from datetime import UTC, datetime

import pytest

from fridgesense import assistant, voice
from fridgesense.door_events import iso_utc
from fridgesense.handlers import api
from fridgesense.store import load_app_config
from fridgesense.table import FridgeTable, account_pk
from fridgesense.web import Request
from tests.api_helpers import ACCOUNT, NOW, call, configure, link_account, sign_in
from tests.conftest import API_HOST, api_event

PK = account_pk(ACCOUNT)
AUDIO = "QVVESU8="
REAL_SPEAK = voice.speak
MCP_KEY = "k" * 64
MILK = "Yes, you have 1 milk, changed 2 minutes ago."


@pytest.fixture(autouse=True)
def spoken(monkeypatch):
    """Polly stand-in: every answer gets AUDIO; records the texts spoken."""
    texts = []
    monkeypatch.setattr(api.voice, "speak", lambda text, *a, **k: texts.append(text) or AUDIO)
    monkeypatch.delenv("ASK_AGENT", raising=False)
    return texts


class FakeAssistant:
    """Replaces assistant.run; returns `outcome` (or raises it) and records each call."""

    def __init__(self, outcome):
        self.outcome = outcome
        self.calls = []

    async def __call__(self, question, **kwargs):
        self.calls.append({"question": question, **kwargs})
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


@pytest.fixture
def agent_on(owner, monkeypatch):
    monkeypatch.setenv("ASK_AGENT", "on")
    configure(mcp_key=MCP_KEY)
    load_app_config(refresh=True)

    def use(outcome):
        fake = FakeAssistant(outcome)
        monkeypatch.setattr(api.assistant, "run", fake)
        return fake

    return use


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


def test_what_should_i_eat_first(owner):
    put_milk()
    status, body = call("POST", "/api/ask", {"question": "What should I eat first?"}, owner)
    assert status == 200
    assert body["intent"] == "oldest_items"
    assert body["answer"].startswith("Use these first: 1 milk from")
    assert body["data"]["items"][0]["name"] == "Milk"


def test_what_do_i_need_to_buy(owner):
    put_milk()
    status, body = call("POST", "/api/ask", {"question": "What do I need to buy?"}, owner)
    assert status == 200
    assert body["intent"] == "low_stock"
    assert body["answer"] == "Nothing has run out or is running low."


# Do I have milk
def test_do_i_have_milk(owner):
    put_milk()
    status, body = call("POST", "/api/ask", {"question": "Do I have milk?"}, owner)
    assert status == 200
    assert body["source"] == "keywords"
    assert body["intent"] == "find_item"
    assert body["answer"] == MILK
    assert body["audio"] == AUDIO
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
    assert body["source"] == "keywords"
    assert body["intent"] == "get_inventory"
    assert body["answer"] == "You have 1 item: 1 milk."


# Unknown question
def test_unknown_question(owner):
    status, body = call("POST", "/api/ask", {"question": "Play some jazz"}, owner)
    assert status == 200
    assert body["intent"] == "unknown"
    assert body["source"] == "keywords"
    assert body["answer"].startswith("Try asking:")
    assert body["data"] is None
    assert body["audio"] == AUDIO


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
    assert body["source"] == "keywords"
    assert body["data"]["opens"] == opens
    assert body["answer"] == answer


def test_request_keeps_api_host():
    req = Request.from_event(api_event("POST", "/api/ask", "{}"))
    assert req.host == API_HOST


# Assistant answers
def test_assistant_answers(agent_on, spoken):
    fake = agent_on(
        assistant.AssistantResult("Yes, you have 1 milk, added 2 minutes ago.", ["find_item"])
    )
    token = sign_in()
    status, body = call("POST", "/api/ask", {"question": "Do I have milk?"}, token)
    assert status == 200
    assert body == {
        "intent": "agent",
        "answer": "Yes, you have 1 milk, added 2 minutes ago.",
        "data": {"tools": ["find_item"]},
        "source": "agent",
        "audio": AUDIO,
    }
    [run] = fake.calls
    assert run["question"] == "Do I have milk?"
    assert run["server"] == f"https://{API_HOST}/mcp/{MCP_KEY}"
    assert spoken == ["Yes, you have 1 milk, added 2 minutes ago."]


def test_assistant_budget_is_counted(agent_on, monkeypatch):
    fake = agent_on(assistant.AssistantResult("Hi.", []))
    monkeypatch.setenv("ASK_AGENT_DAILY_LIMIT", "1")
    token = sign_in()
    call("POST", "/api/ask", {"question": "Hi"}, token)
    budget = fake.calls[0]["budget"]
    assert budget() is True  # the first question of the day
    assert budget() is False  # limit 1 reached


# Assistant off by setting
@pytest.mark.parametrize("setting", [None, "off"])
def test_assistant_off_by_setting(agent_on, monkeypatch, setting):
    fake = agent_on(assistant.AssistantResult("never", []))
    if setting is None:
        monkeypatch.delenv("ASK_AGENT")
    else:
        monkeypatch.setenv("ASK_AGENT", setting)
    put_milk()
    status, body = call("POST", "/api/ask", {"question": "Do I have milk?"}, sign_in())
    assert (status, body["source"], body["intent"]) == (200, "keywords", "find_item")
    assert fake.calls == []


# No MCP key
def test_no_mcp_key(agent_on):
    fake = agent_on(assistant.AssistantResult("never", []))
    configure(mcp_key="")
    load_app_config(refresh=True)
    status, body = call("POST", "/api/ask", {"question": "Do I have milk?"}, sign_in())
    assert (status, body["source"]) == (200, "keywords")
    assert fake.calls == []


# Assistant fails
@pytest.mark.parametrize(
    "outcome",
    [
        assistant.AssistantFailure("timeout"),
        assistant.AssistantFailure("bedrock_error"),
        assistant.AssistantFailure("mcp_error"),
        assistant.AssistantFailure("too_many_rounds"),
        assistant.AssistantFailure("empty_answer"),
        assistant.AssistantFailure("over_budget"),
        RuntimeError("bug"),
    ],
)
def test_assistant_fails(agent_on, outcome):
    fake = agent_on(outcome)
    put_milk()
    status, body = call("POST", "/api/ask", {"question": "Do I have milk?"}, sign_in())
    assert status == 200
    assert (body["source"], body["intent"], body["answer"]) == ("keywords", "find_item", MILK)
    assert len(fake.calls) == 1


@pytest.fixture
def polly(monkeypatch):
    """The real voice.speak, with a stubbed Polly client."""
    import io

    import boto3
    from botocore.response import StreamingBody
    from botocore.stub import Stubber

    client = boto3.client("polly", region_name="us-east-1")
    monkeypatch.setattr(api.voice, "speak", REAL_SPEAK)
    monkeypatch.setattr(api, "polly_client", lambda: client)
    with Stubber(client) as stub:
        stub.body = lambda data: StreamingBody(io.BytesIO(data), len(data))
        yield stub


# Audio returned (through the route)
def test_route_audio_returned(owner, polly):
    FridgeTable().put(
        {
            "pk": PK,
            "sk": "ITEM#butter",
            "name": "Butter",
            "category": "dairy",
            "quantity": 0,
            "last_changed_at": iso_utc(int((NOW - 600) * 1000)),
        }
    )
    polly.add_response(
        "synthesize_speech",
        {"AudioStream": polly.body(b"ID3fake")},
        {
            "Text": "You're out of butter.",
            "Engine": "neural",
            "VoiceId": "Joanna",
            "OutputFormat": "mp3",
            "SampleRate": "24000",
        },
    )
    status, body = call("POST", "/api/ask", {"question": "Do I have butter?"}, owner)
    assert (status, body["answer"], body["audio"]) == (200, "You're out of butter.", "SUQzZmFrZQ==")


# Polly fails (through the route)
def test_route_polly_fails(owner, polly):
    put_milk()
    polly.add_client_error("synthesize_speech", service_error_code="ServiceFailureException")
    status, body = call("POST", "/api/ask", {"question": "Do I have milk?"}, owner)
    assert (status, body["answer"], body["audio"]) == (200, MILK, None)
