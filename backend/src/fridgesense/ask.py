"""Free-text fridge questions ("do I have milk?") to one fridge answer and a spoken sentence.

Keyword rules only, no language model: tried in order, first match wins.
"""

import re
from datetime import datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from fridgesense import fridge_answers as answers
from fridgesense.fridge_answers import (
    ActivityResult,
    FindItemResult,
    InventoryResult,
    LastOpenedResult,
    LowStockResult,
    OldestItemsResult,
    normalize_query,
)

IntentName = Literal[
    "find_item",
    "get_inventory",
    "fridge_activity",
    "last_opened",
    "oldest_items",
    "low_stock",
    "unknown",
]


HINT = "Try asking: do I have milk, what's in my fridge, or when was the fridge last opened?"
LISTED_ITEMS = 5  # items named aloud before "and N more"
ACTIVITY_CUES = ("how many times", "how often", "today", "this week")
EAT_FIRST_CUES = ("eat first", "use first", "use up", "oldest", "going bad", "go bad", "expir")
SHOPPING_CUES = (
    "need to buy",
    "should i buy",
    "shopping list",
    "grocery list",
    "running low",
    "what ran out",
    "what have i run out of",
    "what am i out of",
)
OLDEST_SPOKEN = 3  # items named aloud for "eat first"
# Longest first where one lead-in starts another ("got any" before "any").
ITEM_LEAD_INS = ("do i have", "do we have", "have i got", "is there", "are there", "got any", "any")
ARTICLES = {"any", "some", "a", "an", "the", "more"}
TRAILING_FILLER = (
    "in the fridge",
    "in my fridge",
    "do i have",
    "do we have",
    "are there",
    "left",
    "still",
)
TRAILING = [t.split() for t in TRAILING_FILLER]
CATEGORIES = (
    "dairy",
    "produce",
    "meat",
    "seafood",
    "beverage",
    "snack",
    "condiment",
    "leftovers",
    "bakery",
    "frozen",
    "other",
)
CATEGORY_ALIASES = {
    "fruit": "produce",
    "vegetable": "produce",
    "veggie": "produce",
    "fish": "seafood",
    "drink": "beverage",
    "bread": "bakery",
    "sauce": "condiment",
}


class Intent(BaseModel):
    name: IntentName
    item: str | None = None
    category: str | None = None
    period: Literal["today", "week"] | None = None


class AskResult(BaseModel):
    intent: IntentName
    answer: str
    data: dict[str, Any] | None


def ask(table, account_id: str, question: str, now: datetime, tz: ZoneInfo) -> AskResult:
    """Answer one question: the intent, a sentence to speak, and the structured result."""
    intent = parse(question)
    match intent.name:
        case "find_item":
            result = answers.find_item(table, account_id, intent.item, now=now)
            answer = say_find(result)
        case "get_inventory":
            result = answers.inventory(table, account_id, intent.category)
            answer = say_inventory(result, intent.category)
        case "fridge_activity":
            result = answers.activity(table, account_id, intent.period, now=now, tz=tz)
            answer = say_activity(result)
        case "last_opened":
            result = answers.last_opened(table, account_id, now=now)
            answer = say_last_opened(result)
        case "oldest_items":
            result = answers.oldest_items(table, account_id, now=now)
            answer = say_oldest(result)
        case "low_stock":
            result = answers.low_stock(table, account_id, now=now)
            answer = say_low_stock(result)
        case _:
            return AskResult(intent="unknown", answer=HINT, data=None)
    return AskResult(intent=intent.name, answer=answer, data=result.model_dump())


def normalize(question: str) -> str:
    """Lower case, punctuation dropped (apostrophes kept), single spaces."""
    text = re.sub(r"[^\w\s']", " ", question.lower())
    return " ".join(text.split())


def _mentions_open(words: list[str]) -> bool:
    return any(w.startswith("open") for w in words)


def parse(question: str) -> Intent:
    text = normalize(question)
    words = text.split()
    if any(c in text for c in EAT_FIRST_CUES):
        return Intent(name="oldest_items")
    if any(c in text for c in SHOPPING_CUES):
        return Intent(name="low_stock")
    if ("last" in words and _mentions_open(words)) or "what changed" in text:
        return Intent(name="last_opened")
    if _mentions_open(words) and any(c in text for c in ACTIVITY_CUES):
        return Intent(name="fridge_activity", period="week" if "week" in words else "today")
    item = _item(text)
    if item:
        category = _category(item)
        if category:
            return Intent(name="get_inventory", category=category)
        return Intent(name="find_item", item=item)
    if item is None and (words[:1] in (["what"], ["what's"], ["list"]) or "inventory" in words):
        category = next(filter(None, map(_category, words)), None)
        return Intent(name="get_inventory", category=category)
    return Intent(name="unknown")


def _category(word: str) -> str | None:
    """The inventory category a word names, plurals included ("drinks" -> beverage)."""
    for w in (word, normalize_query(word)):
        if w in CATEGORIES:
            return w
        if w in CATEGORY_ALIASES:
            return CATEGORY_ALIASES[w]
    return None


def _item(text: str) -> str | None:
    """The item named by an item question, "" if it names none, None if not an item question."""
    rest = None
    for lead in ITEM_LEAD_INS:
        if text == lead or text.startswith(lead + " "):
            rest = text.removeprefix(lead)
            break
    else:
        if text.startswith("how many ") and not text.startswith("how many times"):
            rest = text.removeprefix("how many ")
    if rest is None:
        return None
    words = rest.split()
    while words and words[0] in ARTICLES:
        words.pop(0)
    trimmed = True
    while words and trimmed:
        trimmed = False
        for tail in TRAILING:
            if words[-len(tail) :] == tail:
                del words[-len(tail) :]
                trimmed = True
    return " ".join(words)


def plural(count: int, name: str) -> str:
    """Count and lower-case name, with an "s" for any count but 1: "6 soda cans"."""
    name = name.lower()
    if count != 1 and not name.endswith("s"):
        name += "s"
    return f"{count} {name}"


def ago(minutes: int) -> str:
    if minutes < 1:
        return "just now"
    if minutes < 60:
        return f"{_count(minutes, 'minute')} ago"
    if minutes < 24 * 60:
        return f"{_count(minutes // 60, 'hour')} ago"
    return f"{_count(minutes // (24 * 60), 'day')} ago"


def spoken_list(parts: list[str]) -> str:
    """Join for speech: a; a and b; a, b and c."""
    return parts[0] if len(parts) == 1 else f"{', '.join(parts[:-1])} and {parts[-1]}"


def say_find(result: FindItemResult) -> str:
    in_stock = [m for m in result.matches if m.count > 0]
    if len(in_stock) == 1:
        m = in_stock[0]
        when = f", changed {ago(m.minutes_ago)}" if m.minutes_ago is not None else ""
        return f"Yes, you have {plural(m.count, m.name)}{when}."
    if in_stock:
        return f"Yes, you have {spoken_list([plural(m.count, m.name) for m in in_stock])}."
    item = result.query.lower()
    if result.matches:
        return f"You're out of {item}."
    return f"I haven't seen any {item} in the fridge."


def say_inventory(result: InventoryResult, category: str | None) -> str:
    items = result.items
    if not items:
        return f"You have no {category} right now." if category else "Your fridge looks empty."
    noun = "item" if len(items) == 1 else "items"
    return f"You have {len(items)} {noun}: {_listed([plural(i.count, i.name) for i in items])}."


def _count(n: int, noun: str) -> str:
    return f"{n} {noun}{'' if n == 1 else 's'}"


def say_activity(result: ActivityResult) -> str:
    period = "today" if result.period == "today" else "this week"
    if not result.opens:
        return f"The fridge hasn't been opened {period}."
    return (
        f"The fridge was opened {_count(result.opens, 'time')} {period}, "
        f"for {_count(result.average_open_seconds or 0, 'second')} on average."
    )


def say_last_opened(result: LastOpenedResult) -> str:
    if result.opened_at is None:
        return "The fridge hasn't been opened yet."
    parts = [f"The fridge was last opened {ago(result.minutes_ago or 0)}."]
    if result.added:
        parts.append(f"Added {spoken_list([plural(c.count, c.name) for c in result.added])}.")
    if result.removed:
        parts.append(f"Removed {spoken_list([plural(c.count, c.name) for c in result.removed])}.")
    if result.unsure_count:
        parts.append(f"{_count(result.unsure_count, 'change')} to check in the app.")
    return " ".join(parts)


def _days(days: int) -> str:
    if days == 0:
        return "today"
    if days == 1:
        return "yesterday"
    return f"{days} days ago"


def say_oldest(result: OldestItemsResult) -> str:
    if not result.items:
        return "Nothing in the fridge needs using up."
    parts = [
        f"{plural(i.count, i.name)} from {_days(i.days_in_fridge)}"
        for i in result.items[:OLDEST_SPOKEN]
    ]
    return f"Use these first: {spoken_list(parts)}."


def _listed(parts: list[str]) -> str:
    """Up to LISTED_ITEMS parts, then "and N more"."""
    shown = parts[:LISTED_ITEMS]
    if len(parts) > LISTED_ITEMS:
        shown.append(f"{len(parts) - LISTED_ITEMS} more")
    return spoken_list(shown)


def say_low_stock(result: LowStockResult) -> str:
    sentences = []
    if result.ran_out:
        sentences.append(f"You're out of {_listed([i.name.lower() for i in result.ran_out])}.")
    if result.running_low:
        low = [plural(i.count, i.name) for i in result.running_low]
        sentences.append(f"Running low: {_listed(low)}.")
    return " ".join(sentences) or "Nothing has run out or is running low."
