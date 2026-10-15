"""fridge-assistant: failures, the round and time limits, and the per-question cost log."""

import json
import logging
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from fridgesense import assistant
from fridgesense.mcp_server import FridgeContext, build_server
from fridgesense.table import FridgeTable, account_pk
from fridgesense.usage import Prices, Tokens, UsageRecorder
from tests.mcp_helpers import ACCOUNT, NOW, put_item

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def server(aws):
    def context():
        return FridgeContext(FridgeTable(), ACCOUNT, NOW, ZoneInfo("America/Toronto"))

    return build_server(context)


class FakeClock:
    """Returns `times` in order, then keeps returning the last one."""

    def __init__(self, *times: float):
        self.times = list(times)

    def __call__(self) -> float:
        return self.times.pop(0) if len(self.times) > 1 else self.times[0]


def events(caplog, name: str) -> list[dict]:
    out = []
    for record in caplog.records:
        try:
            data = json.loads(record.getMessage())
        except ValueError:
            continue
        if data.get("event") == name:
            out.append(data)
    return out


async def ask(question, server, stub, **kw):
    return await assistant.run(question, server=server, bedrock=stub.client, **kw)


# Bedrock error
async def test_bedrock_error(server, converse_stub):
    converse_stub.fail("ThrottlingException")
    result = await ask("Do I have milk?", server, converse_stub)
    assert isinstance(result, assistant.AssistantFailure)
    assert result.reason == "bedrock_error"


# Too many rounds
async def test_too_many_rounds(server, converse_stub):
    put_item("milk", 1)
    converse_stub.answer(*["tool_use_find_milk.json"] * 4)
    result = await ask("Do I have milk?", server, converse_stub)
    assert result.reason == "too_many_rounds"
    assert len(converse_stub.requests) == 4
    converse_stub.stubber.assert_no_pending_responses()


# Too slow
async def test_too_slow(server, converse_stub):
    put_item("milk", 1)
    converse_stub.answer("tool_use_find_milk.json", "end_turn_milk.json")
    # start, before the 1st model call, then past 12 s before the tool call
    clock = FakeClock(0.0, 1.0, 13.0)
    result = await ask("Do I have milk?", server, converse_stub, clock=clock)
    assert result.reason == "timeout"
    assert len(converse_stub.requests) == 1


async def test_real_deadline(server, converse_stub, monkeypatch):
    """A hung MCP call is cut off by the real deadline too, not only the clock checks."""
    import anyio

    async def hang(*_a, **_k):
        await anyio.sleep(5)

    monkeypatch.setattr("mcp.Client.call_tool", hang)
    converse_stub.answer("tool_use_find_milk.json")
    result = await ask("Do I have milk?", server, converse_stub, deadline_s=0.2)
    assert result.reason == "timeout"


# Empty answer
async def test_empty_answer(server, converse_stub):
    converse_stub.answer("end_turn_thinking_only.json")
    result = await ask("Do I have milk?", server, converse_stub)
    assert result.reason == "empty_answer"


# MCP server unreachable
async def test_mcp_unreachable(aws, converse_stub):
    result = await ask("Do I have milk?", "http://127.0.0.1:9/mcp/x", converse_stub)
    assert result.reason == "mcp_error"
    assert converse_stub.requests == []


# Answered question
async def test_cost_logged_for_answer(server, converse_stub, caplog):
    caplog.set_level(logging.INFO, logger="fridgesense")
    put_item("milk", 1)
    converse_stub.answer("tool_use_find_milk.json", "end_turn_milk.json")
    question = "Do I have milk?"
    url_like = "https://h/mcp/secret-key"
    await ask(question, server, converse_stub)

    [event] = events(caplog, "ask_agent")
    assert event["outcome"] == "answered"
    assert event["rounds"] == 2
    assert event["tools"] == ["find_item"]
    assert event["input_tokens"] == 2700
    assert event["output_tokens"] == 70
    assert event["usd"] == 0.001084
    assert isinstance(event["ms"], int)
    text = caplog.text
    assert question not in text
    assert url_like not in text


# Failed question still logs cost
async def test_cost_logged_for_failure(server, converse_stub, caplog):
    caplog.set_level(logging.INFO, logger="fridgesense")
    put_item("milk", 1)
    converse_stub.answer("tool_use_find_milk.json").fail("ThrottlingException")
    await ask("Do I have milk?", server, converse_stub)

    [event] = events(caplog, "ask_agent")
    assert event["outcome"] == "bedrock_error"
    assert event["input_tokens"] == 1200
    assert event["output_tokens"] == 40


# Second round read from cache
async def test_second_round_read_from_cache(server, converse_stub, caplog):
    caplog.set_level(logging.INFO, logger="fridgesense")
    put_item("milk", 1)
    converse_stub.answer("tool_use_find_milk.json", "end_turn_milk_cached.json")
    await ask("Do I have milk?", server, converse_stub)

    [event] = events(caplog, "ask_agent")
    assert event["input_tokens"] == 1500
    assert event["cache_read_tokens"] == 1200
    assert event["cache_write_tokens"] == 0
    assert event["output_tokens"] == 70
    assert event["usd"] == 0.000787


# No cache fields
async def test_no_cache_fields(server, converse_stub, caplog):
    caplog.set_level(logging.INFO, logger="fridgesense")
    put_item("milk", 1)
    converse_stub.answer("tool_use_find_milk.json", "end_turn_milk.json")
    await ask("Do I have milk?", server, converse_stub)

    [event] = events(caplog, "ask_agent")
    assert (event["cache_read_tokens"], event["cache_write_tokens"]) == (0, 0)


# Assistant rounds (llm-usage-tracking): one usage record per model call
async def test_on_usage_called_per_model_call(server, converse_stub):
    put_item("milk", 1)
    converse_stub.answer("tool_use_find_milk.json", "end_turn_milk_cached.json")
    calls = []
    await ask(
        "Do I have milk?", server, converse_stub, on_usage=lambda t, usd: calls.append((t, usd))
    )
    assert calls == [
        (Tokens(input=1200, output=40), 0.000506),
        (Tokens(input=300, output=30, cache_read=1200), 0.000281),
    ]


async def test_on_usage_records_rounds_before_a_failure(server, converse_stub):
    put_item("milk", 1)
    converse_stub.answer("tool_use_find_milk.json").fail("ThrottlingException")
    calls = []
    result = await ask(
        "Do I have milk?", server, converse_stub, on_usage=lambda t, usd: calls.append(t)
    )
    assert result == assistant.AssistantFailure("bedrock_error")
    assert calls == [Tokens(input=1200, output=40)]


async def test_cache_prices_used(server, converse_stub, caplog):
    caplog.set_level(logging.INFO, logger="fridgesense")
    put_item("milk", 1)
    converse_stub.answer("tool_use_find_milk.json", "end_turn_milk_cached.json")
    prices = Prices(input=0.0, output=0.0, cache_read=0.001, cache_write=0.0)
    await ask("Do I have milk?", server, converse_stub, prices=prices)
    [event] = events(caplog, "ask_agent")
    assert event["usd"] == 0.0012


TORONTO = ZoneInfo("America/Toronto")


def tracker(table):
    return UsageRecorder(
        table,
        TORONTO,
        source="assistant",
        account_id=ACCOUNT,
        model_id="us.amazon.nova-2-lite-v1:0",
    )


def usage_day():
    return f"USAGE#{datetime.now(UTC).astimezone(TORONTO).date().isoformat()}"


# Assistant rounds, No content in the log (llm-usage-tracking)
async def test_assistant_rounds_tracked_without_content(server, converse_stub, caplog):
    caplog.set_level(logging.INFO, logger="fridgesense")
    put_item("milk", 1)
    converse_stub.answer("tool_use_find_milk.json", "end_turn_milk.json")
    table = FridgeTable()
    await ask("Do I have milk?", server, converse_stub, on_usage=tracker(table))

    usage = events(caplog, "llm_usage")
    assert [u["source"] for u in usage] == ["assistant", "assistant"]
    assert len(events(caplog, "ask_agent")) == 1
    for u in usage:
        text = json.dumps(u)
        assert "milk" not in text
        assert assistant.SYSTEM_PROMPT[:30] not in text
        assert "in_fridge" not in text
    assert table.get(account_pk(ACCOUNT), usage_day())["assistant_calls"] == 2


class BrokenTable:
    def add_many(self, *args, **kwargs):
        raise RuntimeError("boom")


# DynamoDB error during a question
async def test_totals_failure_does_not_break_the_answer(server, converse_stub, caplog):
    caplog.set_level(logging.INFO, logger="fridgesense")
    put_item("milk", 1)
    converse_stub.answer("tool_use_find_milk.json", "end_turn_milk.json")
    result = await ask("Do I have milk?", server, converse_stub, on_usage=tracker(BrokenTable()))

    assert result.answer == "Yes, you have 1 milk, added 2 minutes ago."
    [event] = events(caplog, "ask_agent")
    assert event["outcome"] == "answered"
    assert len(events(caplog, "llm_usage_store_failed")) == 2


# Over-budget question records nothing
async def test_over_budget_records_nothing(server, converse_stub, caplog):
    caplog.set_level(logging.INFO, logger="fridgesense")
    table = FridgeTable()
    result = await ask(
        "Do I have milk?", server, converse_stub, budget=lambda: False, on_usage=tracker(table)
    )
    assert result == assistant.AssistantFailure("over_budget")
    assert events(caplog, "llm_usage") == []
    assert table.get(account_pk(ACCOUNT), usage_day()) is None
