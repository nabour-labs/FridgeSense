"""fridge-assistant: the daily question budget (moto)."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from fridgesense import assistant
from fridgesense.table import FridgeTable, account_pk

ACCOUNT = "ava1.ring.account.A1"
TZ = ZoneInfo("America/Toronto")
# 20:00 on Oct 15 and 09:00 on Oct 16 in Toronto (EDT)
EVENING = datetime(2026, 10, 16, 0, 0, tzinfo=UTC)
NEXT_MORNING = datetime(2026, 10, 16, 13, 0, tzinfo=UTC)


def count_on(day: str) -> int | None:
    item = FridgeTable().get(account_pk(ACCOUNT), f"ASKBUDGET#{day}")
    return None if item is None else int(item["count"])


def test_increment_below(aws):
    table = FridgeTable()
    pk, sk = account_pk(ACCOUNT), "ASKBUDGET#2026-10-15"
    assert table.increment_below(pk, sk, "count", 2) is True
    assert table.increment_below(pk, sk, "count", 2) is True
    assert table.increment_below(pk, sk, "count", 2) is False
    assert int(table.get(pk, sk)["count"]) == 2


# Under the limit
def test_under_the_limit(aws):
    table = FridgeTable()
    assert assistant.take_budget(table, ACCOUNT, EVENING, TZ, limit=2) is True
    assert assistant.take_budget(table, ACCOUNT, EVENING, TZ, limit=2) is True
    assert count_on("2026-10-15") == 2


# Limit reached
def test_limit_reached(aws):
    table = FridgeTable()
    for _ in range(2):
        assistant.take_budget(table, ACCOUNT, EVENING, TZ, limit=2)
    assert assistant.take_budget(table, ACCOUNT, EVENING, TZ, limit=2) is False
    assert count_on("2026-10-15") == 2


# New day
def test_new_day(aws):
    table = FridgeTable()
    for _ in range(2):
        assistant.take_budget(table, ACCOUNT, EVENING, TZ, limit=2)
    assert assistant.take_budget(table, ACCOUNT, NEXT_MORNING, TZ, limit=2) is True
    assert count_on("2026-10-16") == 1


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_over_budget_calls_nothing(aws, converse_stub, anyio_backend):
    result = await assistant.run(
        "Do I have milk?",
        server="http://127.0.0.1:9/mcp/x",  # would be mcp_error if it connected
        bedrock=converse_stub.client,
        budget=lambda: False,
    )
    assert result.reason == "over_budget"
    assert converse_stub.requests == []
