"""fridge-ask: spoken sentences built from the fridge answers."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from fridgesense.ask import (
    HINT,
    ago,
    ask,
    plural,
    say_activity,
    say_find,
    say_inventory,
    say_last_opened,
)
from fridgesense.fridge_answers import (
    ActivityResult,
    Counted,
    FindItemResult,
    InventoryItem,
    InventoryResult,
    ItemMatch,
    LastOpenedResult,
)


# Plural names
@pytest.mark.parametrize(
    ("count", "name", "spoken"),
    [
        (6, "Soda can", "6 soda cans"),
        (12, "Eggs", "12 eggs"),
        (1, "Milk", "1 milk"),
        (0, "egg", "0 eggs"),
    ],
)
def test_plural_names(count, name, spoken):
    assert plural(count, name) == spoken


# Time phrases
@pytest.mark.parametrize(
    ("minutes", "phrase"),
    [
        (0, "just now"),
        (1, "1 minute ago"),
        (59, "59 minutes ago"),
        (60, "1 hour ago"),
        (90, "1 hour ago"),
        (150, "2 hours ago"),
        (1439, "23 hours ago"),
        (1440, "1 day ago"),
        (3000, "2 days ago"),
    ],
)
def test_time_phrases(minutes, phrase):
    assert ago(minutes) == phrase


def found(query, *matches):
    items = [ItemMatch(name=n, count=c, minutes_ago=m) for n, c, m in matches]
    total = sum(i.count for i in items)
    return FindItemResult(query=query, in_fridge=total > 0, total_count=total, matches=items)


# One match
def test_one_match():
    assert say_find(found("milk", ("Milk", 1, 2))) == "Yes, you have 1 milk, changed 2 minutes ago."


# Several matches
def test_several_matches():
    result = found("milk", ("Oat milk", 2, 300), ("Milk", 1, 2))
    assert say_find(result) == "Yes, you have 2 oat milks and 1 milk."


def test_several_matches_skip_run_out_and_list_three():
    result = found(
        "milk", ("Oat milk", 2, 3), ("Milk", 1, 2), ("Soy milk", 1, 9), ("Goat milk", 0, 5)
    )
    assert say_find(result) == "Yes, you have 2 oat milks, 1 milk and 1 soy milk."


# Ran out
def test_ran_out():
    assert say_find(found("butter", ("Butter", 0, 45))) == "You're out of butter."


# Never seen
def test_never_seen():
    assert say_find(found("pickles")) == "I haven't seen any pickles in the fridge."


def stocked(*items):
    rows = [InventoryItem(name=n, category="dairy", count=c) for n, c in items]
    return InventoryResult(total_items=len(rows), items=rows, pending_count=0)


# Short inventory
def test_short_inventory():
    result = stocked(("Eggs", 12), ("Milk", 1))
    assert say_inventory(result, None) == "You have 2 items: 12 eggs and 1 milk."


def test_one_item():
    assert say_inventory(stocked(("Milk", 1)), None) == "You have 1 item: 1 milk."


# Long inventory
def test_long_inventory():
    result = stocked(*[(f"Item{n}", 1) for n in range(1, 10)])
    assert say_inventory(result, None) == (
        "You have 9 items: 1 item1, 1 item2, 1 item3, 1 item4, 1 item5 and 4 more."
    )


# Empty category
def test_empty_category():
    assert say_inventory(stocked(), "seafood") == "You have no seafood right now."


def test_empty_fridge():
    assert say_inventory(stocked(), None) == "Your fridge looks empty."


def opened(period, opens, average=None):
    return ActivityResult(
        period=period,
        opens=opens,
        average_open_seconds=average,
        last_opened_at=None,
        busiest_hour=None,
    )


# Openings today
def test_openings_today():
    assert say_activity(opened("today", 3, 10)) == (
        "The fridge was opened 3 times today, for 10 seconds on average."
    )


def test_one_opening_this_week():
    assert say_activity(opened("week", 1, 1)) == (
        "The fridge was opened 1 time this week, for 1 second on average."
    )


# No openings this week
def test_no_openings_this_week():
    assert say_activity(opened("week", 0)) == "The fridge hasn't been opened this week."


def last(minutes, added=(), removed=(), unsure=0):
    return LastOpenedResult(
        opened_at="2026-10-15T08:57:35.638Z" if minutes is not None else None,
        minutes_ago=minutes,
        duration_s=14 if minutes is not None else None,
        added=[Counted(name=n, count=c) for n, c in added],
        removed=[Counted(name=n, count=c) for n, c in removed],
        unsure_count=unsure,
    )


# Milk just went in
def test_milk_just_went_in():
    assert say_last_opened(last(2, added=[("Milk", 1)])) == (
        "The fridge was last opened 2 minutes ago. Added 1 milk."
    )


# Unsure change
def test_unsure_change():
    assert say_last_opened(last(45, removed=[("Butter", 1)], unsure=1)) == (
        "The fridge was last opened 45 minutes ago. Removed 1 butter. 1 change to check in the app."
    )


def test_added_removed_and_several_unsure():
    result = last(5, added=[("Eggs", 12), ("Milk", 1)], removed=[("Soda can", 2)], unsure=2)
    assert say_last_opened(result) == (
        "The fridge was last opened 5 minutes ago. Added 12 eggs and 1 milk. "
        "Removed 2 soda cans. 2 changes to check in the app."
    )


# Never opened
def test_never_opened():
    assert say_last_opened(last(None)) == "The fridge hasn't been opened yet."


class FakeTable:
    """Just enough of FridgeTable for the answer functions: rows under one account."""

    def __init__(self, rows=()):
        self.rows = sorted(rows, key=lambda r: r["sk"])
        self.calls = 0

    def query(self, account_id, prefix):
        self.calls += 1
        return [r for r in self.rows if r["sk"].startswith(prefix)]

    def query_range(self, account_id, low, high, newest_first=False, limit=None):
        self.calls += 1
        rows = [r for r in self.rows if low <= r["sk"] <= high]
        rows = rows[::-1] if newest_first else rows
        return rows[:limit] if limit else rows


NOW = datetime(2026, 10, 15, 13, 0, tzinfo=UTC)  # 09:00 in Toronto
TZ = ZoneInfo("America/Toronto")


def door(opened_at, seconds, changes=()):
    return {
        "sk": f"DOOR#{opened_at}#cam",
        "opened_at": opened_at,
        "duration_s": seconds,
        "changes": list(changes),
    }


ROWS = [
    {
        "sk": "ITEM#milk",
        "name": "Milk",
        "category": "dairy",
        "quantity": 1,
        "last_changed_at": "2026-10-15T12:58:00.000Z",
    },
    {"sk": "ITEM#apple", "name": "Apple", "category": "produce", "quantity": 3},
    door(
        "2026-10-15T12:58:00.000Z",
        14,
        [{"item": "milk", "name": "Milk", "direction": "added", "quantity": 1, "applied": True}],
    ),
    door("2026-10-13T12:00:00.000Z", 10),
]


def test_ask_find_item():
    result = ask(FakeTable(ROWS), "acct", "Do I have milk?", now=NOW, tz=TZ)
    assert result.intent == "find_item"
    assert result.answer == "Yes, you have 1 milk, changed 2 minutes ago."
    assert result.data["query"] == "milk"
    assert result.data["total_count"] == 1


def test_ask_inventory_category():
    result = ask(FakeTable(ROWS), "acct", "What fruit do I have?", now=NOW, tz=TZ)
    assert (result.intent, result.answer) == ("get_inventory", "You have 1 item: 3 apples.")
    assert [i["name"] for i in result.data["items"]] == ["Apple"]


def test_ask_activity_week():
    result = ask(FakeTable(ROWS), "acct", "How often did we open it this week?", now=NOW, tz=TZ)
    assert result.intent == "fridge_activity"
    assert result.answer == "The fridge was opened 2 times this week, for 12 seconds on average."
    assert result.data["period"] == "week"


def test_ask_last_opened():
    result = ask(FakeTable(ROWS), "acct", "What changed?", now=NOW, tz=TZ)
    assert result.intent == "last_opened"
    assert result.answer == "The fridge was last opened 2 minutes ago. Added 1 milk."


# Hint
def test_hint_without_reading_the_table():
    table = FakeTable(ROWS)
    result = ask(table, "acct", "Play some jazz", now=NOW, tz=TZ)
    assert result.intent == "unknown"
    assert result.answer == HINT
    assert result.answer == (
        "Try asking: do I have milk, what's in my fridge, or when was the fridge last opened?"
    )
    assert result.data is None
    assert table.calls == 0
