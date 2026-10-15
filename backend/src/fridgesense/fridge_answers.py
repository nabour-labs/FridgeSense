"""Answers to spoken fridge questions, shared by the MCP tools.

Pure functions over the single table: no Ring calls, so they stay fast.
"""

from collections import Counter
from datetime import datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from fridgesense.door_events import iso_utc
from fridgesense.table import FridgeTable

_ES_ENDINGS = ("s", "x", "z", "ch", "sh", "o")


def _singular(word: str) -> str:
    if word.endswith("es") and word[:-2].endswith(_ES_ENDINGS):
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss") and len(word) > 1:
        return word[:-1]
    return word


def normalize_query(text: str) -> str:
    """Lower case, single spaces, last word singular: "Soda Cans" -> "soda can"."""
    words = text.lower().split()
    if not words:
        return ""
    words[-1] = _singular(words[-1])
    return " ".join(words)


def name_matches(query: str, name: str) -> bool:
    """Same item, or the query as whole words inside a longer name ("milk" in "oat milk")."""
    q, n = normalize_query(query), normalize_query(name)
    if not q:
        return False
    if q == n:
        return True
    # Compare word by word with every word made singular, so "cans" finds "soda can".
    q_words = [_singular(w) for w in q.split()]
    n_words = [_singular(w) for w in n.split()]
    size = len(q_words)
    return any(n_words[i : i + size] == q_words for i in range(len(n_words) - size + 1))


def minutes_since(iso: str | None, now: datetime) -> int | None:
    if not iso:
        return None
    then = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return max(0, int((now - then).total_seconds() // 60))


class ItemMatch(BaseModel):
    name: str
    count: int
    last_changed_at: str | None = None
    minutes_ago: int | None = None


class FindItemResult(BaseModel):
    query: str
    in_fridge: bool
    total_count: int
    matches: list[ItemMatch]


def find_item(table: FridgeTable, account_id: str, query: str, now: datetime) -> FindItemResult:
    matches = [
        ItemMatch(
            name=i.get("name", i["sk"].removeprefix("ITEM#")),
            count=i.get("quantity", 0),
            last_changed_at=i.get("last_changed_at"),
            minutes_ago=minutes_since(i.get("last_changed_at"), now),
        )
        for i in table.query(account_id, "ITEM#")
        if name_matches(query, i["sk"].removeprefix("ITEM#"))
        or name_matches(query, i.get("name", ""))
    ]
    matches.sort(key=lambda m: (-m.count, m.name.lower()))
    total = sum(m.count for m in matches)
    return FindItemResult(query=query, in_fridge=total > 0, total_count=total, matches=matches)


class InventoryItem(BaseModel):
    name: str
    category: str
    count: int


class InventoryResult(BaseModel):
    total_items: int
    items: list[InventoryItem]
    pending_count: int


def inventory(table: FridgeTable, account_id: str, category: str | None = None) -> InventoryResult:
    wanted = category.strip().lower() if category else None
    items = [
        InventoryItem(
            name=i.get("name", i["sk"].removeprefix("ITEM#")),
            category=i.get("category", "other"),
            count=i.get("quantity", 0),
        )
        for i in table.query(account_id, "ITEM#")
        if i.get("quantity", 0) > 0
    ]
    if wanted:
        items = [i for i in items if i.category.lower() == wanted]
    items.sort(key=lambda i: (i.category, i.name.lower()))
    pending = len(table.query(account_id, "PENDING#"))
    return InventoryResult(total_items=len(items), items=items, pending_count=pending)


Period = Literal["today", "week"]


class ActivityResult(BaseModel):
    period: Period
    opens: int
    average_open_seconds: int | None
    last_opened_at: str | None
    busiest_hour: int | None


def _iso_z(dt: datetime) -> str:
    return iso_utc(int(dt.timestamp() * 1000))


def activity(
    table: FridgeTable, account_id: str, period: Period, now: datetime, tz: ZoneInfo
) -> ActivityResult:
    """Door openings since local midnight (today) or local midnight six days ago (week)."""
    local_now = now.astimezone(tz)
    start_day = local_now.date() - timedelta(days=0 if period == "today" else 6)
    start = datetime.combine(start_day, time.min, tzinfo=tz)
    events = table.query_range(account_id, f"DOOR#{_iso_z(start)}", "DOOR#~")
    if not events:
        return ActivityResult(
            period=period,
            opens=0,
            average_open_seconds=None,
            last_opened_at=None,
            busiest_hour=None,
        )
    hours = Counter(
        datetime.fromisoformat(e["opened_at"].replace("Z", "+00:00")).astimezone(tz).hour
        for e in events
    )
    busiest = min(hours, key=lambda h: (-hours[h], h))
    durations = [e.get("duration_s", 0) for e in events]
    return ActivityResult(
        period=period,
        opens=len(events),
        average_open_seconds=round(sum(durations) / len(durations)),
        last_opened_at=max(e["opened_at"] for e in events),
        busiest_hour=busiest,
    )


class Counted(BaseModel):
    name: str
    count: int


class LastOpenedResult(BaseModel):
    opened_at: str | None
    minutes_ago: int | None
    duration_s: int | None
    added: list[Counted]
    removed: list[Counted]
    unsure_count: int


def last_opened(table: FridgeTable, account_id: str, now: datetime) -> LastOpenedResult:
    events = table.query_range(account_id, "DOOR#", "DOOR#~", newest_first=True, limit=1)
    if not events:
        return LastOpenedResult(
            opened_at=None, minutes_ago=None, duration_s=None, added=[], removed=[], unsure_count=0
        )
    e = events[0]
    changes = e.get("changes", [])

    def applied(direction: str) -> list[Counted]:
        return [
            Counted(name=c.get("name", c["item"]), count=c.get("quantity", 1))
            for c in changes
            if c.get("direction") == direction and c.get("applied")
        ]

    unsure = sum(1 for c in changes if not c.get("applied") and not c.get("rejected"))
    return LastOpenedResult(
        opened_at=e.get("opened_at"),
        minutes_ago=minutes_since(e.get("opened_at"), now),
        duration_s=e.get("duration_s"),
        added=applied("added"),
        removed=applied("removed"),
        unsure_count=unsure,
    )
