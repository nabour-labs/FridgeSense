"""fridge-mcp: Last opening."""

from datetime import timedelta

from fridgesense.fridge_answers import last_opened
from fridgesense.table import FridgeTable
from tests.mcp_helpers import ACCOUNT, NOW, change, put_door


# Milk just went in
def test_milk_just_went_in(aws):
    put_door(NOW - timedelta(hours=5), 30, [change("eggs", "removed", 2)])
    put_door(
        NOW - timedelta(minutes=3),
        18,
        [
            change("milk"),
            change("chocolate bar", "removed", applied=False),
            change("jam", applied=False, rejected=True),
        ],
        pending_count=1,
    )
    result = last_opened(FridgeTable(), ACCOUNT, now=NOW)
    assert result.minutes_ago == 3 and result.duration_s == 18
    assert [(a.name, a.count) for a in result.added] == [("milk", 1)]
    assert result.removed == []
    assert result.unsure_count == 1
    assert result.opened_at == "2026-10-15T23:57:00.000Z"


# Never opened
def test_never_opened(aws):
    result = last_opened(FridgeTable(), ACCOUNT, now=NOW)
    assert result.opened_at is None and result.minutes_ago is None
    assert (result.added, result.removed, result.unsure_count) == ([], [], 0)
