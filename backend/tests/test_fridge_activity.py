"""fridge-mcp: Fridge activity in the household's time zone."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from fridgesense.fridge_answers import activity
from fridgesense.table import FridgeTable
from tests.mcp_helpers import ACCOUNT, NOW, put_door

TORONTO = ZoneInfo("America/Toronto")


def utc(y, mo, d, h, mi):
    return datetime(y, mo, d, h, mi, tzinfo=UTC)


# Opens today
def test_opens_today(aws):
    put_door(utc(2026, 10, 15, 12, 10), 20)  # 08:10 EDT
    put_door(utc(2026, 10, 15, 12, 40), 30)  # 08:40 EDT
    put_door(utc(2026, 10, 15, 22, 5), 40)  # 18:05 EDT
    put_door(utc(2026, 10, 14, 13, 0), 50)  # yesterday 09:00 EDT
    put_door(utc(2026, 10, 15, 3, 30), 60)  # 23:30 EDT on Oct 14: yesterday locally
    result = activity(FridgeTable(), ACCOUNT, "today", now=NOW, tz=TORONTO)
    assert result.period == "today"
    assert result.opens == 3
    assert result.average_open_seconds == 30
    assert result.busiest_hour == 8
    assert result.last_opened_at == "2026-10-15T22:05:00.000Z"


def test_week_includes_the_last_seven_days(aws):
    put_door(utc(2026, 10, 15, 12, 10), 20)
    put_door(utc(2026, 10, 9, 5, 0), 40)  # Oct 9 01:00 EDT: inside the week
    put_door(utc(2026, 10, 9, 3, 0), 40)  # Oct 8 23:00 EDT: outside
    result = activity(FridgeTable(), ACCOUNT, "week", now=NOW, tz=TORONTO)
    assert result.opens == 2 and result.average_open_seconds == 30


# No opens
def test_no_opens(aws):
    result = activity(FridgeTable(), ACCOUNT, "week", now=NOW, tz=TORONTO)
    assert (result.opens, result.average_open_seconds, result.busiest_hour) == (0, None, None)
    assert result.last_opened_at is None
