"""Token counts, cost and daily totals for every LLM call (llm-usage-tracking)."""

import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from fridgesense.table import FridgeTable
from fridgesense.usage import Prices, Tokens, UsageRecorder, price

DEFAULT = Prices()


def test_uncached_call():
    tokens = Tokens.from_converse({"inputTokens": 1180, "outputTokens": 96})
    assert (tokens.cache_read, tokens.cache_write, tokens.total_input) == (0, 0, 1180)
    assert price(tokens, DEFAULT) == 0.000653


def test_cache_read():
    tokens = Tokens.from_converse(
        {
            "inputTokens": 1180,
            "cacheReadInputTokens": 2000,
            "cacheWriteInputTokens": 0,
            "outputTokens": 96,
        }
    )
    assert tokens.total_input == 3180
    assert price(tokens, DEFAULT) == 0.000818


def test_cache_write():
    tokens = Tokens.from_converse(
        {"inputTokens": 200, "cacheWriteInputTokens": 1500, "outputTokens": 96}
    )
    assert tokens.total_input == 1700
    assert price(tokens, DEFAULT) == 0.00033


def test_usage_missing_entirely():
    tokens = Tokens.from_converse(None)
    assert tokens == Tokens(0, 0, 0, 0)
    assert price(tokens, DEFAULT) == 0.0


def test_default_prices():
    expected = Prices(input=0.00033, output=0.00275, cache_read=0.0000825, cache_write=0.0)
    assert expected == DEFAULT


def test_cache_prices_from_configuration(monkeypatch):
    monkeypatch.setenv("NOVA_PRICE_CACHE_READ", "0.0001")
    monkeypatch.setenv("NOVA_PRICE_CACHE_WRITE", "0.0005")
    tokens = Tokens(input=0, output=0, cache_read=1000, cache_write=1000)
    assert price(tokens, Prices.from_env()) == 0.0006


def test_prices_from_env_fall_back_to_defaults(monkeypatch):
    names = ("NOVA_PRICE_IN", "NOVA_PRICE_OUT", "NOVA_PRICE_CACHE_READ", "NOVA_PRICE_CACHE_WRITE")
    for name in names:
        monkeypatch.delenv(name, raising=False)
    assert Prices.from_env() == DEFAULT


def test_add_many_creates_then_adds(aws):
    table = FridgeTable()
    table.add_many("ACCOUNT#acc-1", "USAGE#2026-10-20", {"calls": 1, "usd": 0.000818})
    table.add_many("ACCOUNT#acc-1", "USAGE#2026-10-20", {"calls": 1, "usd": 0.000506})
    item = table.get("ACCOUNT#acc-1", "USAGE#2026-10-20")
    assert item["calls"] == 2
    assert item["usd"] == 0.001324


TORONTO = ZoneInfo("America/Toronto")
MODEL = "us.amazon.nova-2-lite-v1:0"


def at(iso: str):
    return lambda: datetime.fromisoformat(iso)


def recorder(table, source="analysis", account_id="acc-1", when="2026-10-20T14:00:00+00:00"):
    return UsageRecorder(
        table, TORONTO, source=source, account_id=account_id, model_id=MODEL, clock=at(when)
    )


def usage_lines(caplog, event="llm_usage"):
    return [
        json.loads(r.getMessage())
        for r in caplog.records
        if json.loads(r.getMessage()).get("event") == event
    ]


def test_first_call_of_the_day(aws, caplog):
    caplog.set_level(logging.INFO)
    table = FridgeTable()
    recorder(table)(Tokens(input=1180, output=96, cache_read=2000, cache_write=0), 0.000818)
    item = table.get("ACCOUNT#acc-1", "USAGE#2026-10-20")
    assert item["calls"] == 1
    assert item["input_tokens"] == 1180
    assert item["cache_read_tokens"] == 2000
    assert item["cache_write_tokens"] == 0
    assert item["output_tokens"] == 96
    assert item["usd"] == 0.000818
    assert item["analysis_calls"] == 1
    assert item["analysis_usd"] == 0.000818


def test_llm_usage_event_fields(aws, caplog):
    caplog.set_level(logging.INFO)
    recorder(FridgeTable())(Tokens(input=1180, output=96, cache_read=2000, cache_write=0), 0.000818)
    [line] = usage_lines(caplog)
    assert line == {
        "event": "llm_usage",
        "source": "analysis",
        "account_id": "acc-1",
        "model_id": MODEL,
        "input_tokens": 1180,
        "output_tokens": 96,
        "cache_read_tokens": 2000,
        "cache_write_tokens": 0,
        "total_input_tokens": 3180,
        "usd": 0.000818,
    }


def test_calls_from_both_sources_add_up(aws):
    table = FridgeTable()
    recorder(table)(Tokens(input=1180, output=96, cache_read=2000), 0.000818)
    recorder(table, source="assistant")(Tokens(input=1200, output=40), 0.000506)
    item = table.get("ACCOUNT#acc-1", "USAGE#2026-10-20")
    assert item["calls"] == 2
    assert item["input_tokens"] == 2380
    assert item["output_tokens"] == 136
    assert item["usd"] == 0.001324
    assert item["analysis_calls"] == 1
    assert item["assistant_calls"] == 1
    assert item["assistant_usd"] == 0.000506


def test_household_day_boundary(aws):
    table = FridgeTable()
    recorder(table, when="2026-10-21T03:30:00+00:00")(Tokens(input=10), 0.000003)
    assert table.get("ACCOUNT#acc-1", "USAGE#2026-10-20")["calls"] == 1
    assert table.get("ACCOUNT#acc-1", "USAGE#2026-10-21") is None


def test_totals_keyed_by_account(aws):
    table = FridgeTable()
    recorder(table, account_id="acc-1")(Tokens(input=10), 0.000003)
    recorder(table, account_id="acc-2")(Tokens(input=20), 0.000007)
    assert table.get("ACCOUNT#acc-1", "USAGE#2026-10-20")["input_tokens"] == 10
    assert table.get("ACCOUNT#acc-2", "USAGE#2026-10-20")["input_tokens"] == 20


class BrokenTable:
    def add_many(self, *args, **kwargs):
        raise RuntimeError("ProvisionedThroughputExceededException")


def test_totals_failure_only_warns(caplog):
    caplog.set_level(logging.INFO)
    recorder(BrokenTable())(Tokens(input=10), 0.000003)  # does not raise
    assert len(usage_lines(caplog)) == 1
    [warning] = usage_lines(caplog, "llm_usage_store_failed")
    assert warning["source"] == "analysis"
    assert warning["account_id"] == "acc-1"
    assert warning["error"] == "RuntimeError"
