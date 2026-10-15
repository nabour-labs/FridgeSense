"""FridgeSense MCP server: six read-only tools for voice assistants and MCP clients."""

import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from fridgesense import fridge_answers as answers
from fridgesense.store import TokenStore
from fridgesense.table import FridgeTable

INSTRUCTIONS = (
    "FridgeSense knows what is in the user's fridge, from a camera that watches each door "
    "opening. Use these tools to answer questions like 'Do I have milk?', 'What's in my "
    "fridge?', 'What should I eat first?', 'What do I need to buy?' or 'When was the fridge "
    "last opened?'. Answers are spoken: keep them short, "
    "say counts and how long ago, and mention items that ran out."
)
READ_ONLY = ToolAnnotations(
    read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False
)


@dataclass
class FridgeContext:
    table: FridgeTable
    account_id: str
    now: datetime
    tz: ZoneInfo


def build_server(context: Callable[[], FridgeContext]) -> MCPServer:
    """`context` gives each call the table, account, clock and household time zone."""
    server = MCPServer("fridgesense", instructions=INSTRUCTIONS)

    @server.tool(annotations=READ_ONLY)
    def find_item(name: str) -> answers.FindItemResult:
        """Check whether an item is in the fridge now and how many, e.g. "Do I have milk?".
        Matches plurals and partial names ("milk" finds "oat milk"). An item with count 0
        ran out; no matches means the camera has never seen it."""
        c = context()
        return answers.find_item(c.table, c.account_id, name, now=c.now)

    @server.tool(annotations=READ_ONLY)
    def get_inventory(category: str | None = None) -> answers.InventoryResult:
        """List what is in the fridge now with counts, e.g. "What's in my fridge?". Optionally
        only one category: dairy, produce, meat, seafood, beverage, snack, condiment,
        leftovers, bakery, frozen or other. pending_count is how many changes the user
        still has to confirm in the app."""
        c = context()
        return answers.inventory(c.table, c.account_id, category)

    @server.tool(annotations=READ_ONLY)
    def fridge_activity(period: answers.Period) -> answers.ActivityResult:
        """How often the fridge was opened "today" (since midnight) or this "week" (last
        7 days), the average time the door stayed open in seconds, the busiest hour (0-23,
        local time) and when it was last opened."""
        c = context()
        return answers.activity(c.table, c.account_id, period, now=c.now, tz=c.tz)

    @server.tool(annotations=READ_ONLY)
    def last_opened() -> answers.LastOpenedResult:
        """When the fridge was last opened, how long ago, and what was put in or taken out
        that time. unsure_count is how many changes the camera wasn't sure about."""
        c = context()
        return answers.last_opened(c.table, c.account_id, now=c.now)

    @server.tool(annotations=READ_ONLY)
    def oldest_items(
        category: str | None = None,
        limit: Annotated[int, Field(ge=1, le=20)] = 5,
    ) -> answers.OldestItemsResult:
        """What to eat or use first, e.g. "What should I eat first?" or "What's going bad?".
        Items in the fridge now, oldest first, with days_in_fridge since they were last
        stocked (an estimate from the camera; there are no expiry dates). Condiments, frozen
        food and beverages keep for weeks, so they are left out (skipped_categories) unless
        that category is asked for. limit: 1-20, default 5."""
        c = context()
        return answers.oldest_items(
            c.table, c.account_id, now=c.now, category=category, limit=limit
        )

    @server.tool(annotations=READ_ONLY)
    def low_stock() -> answers.LowStockResult:
        """A shopping list, e.g. "What do I need to buy?" or "What's running low?". ran_out:
        items that hit zero in the last 30 days, most recent first. running_low: items down
        to a quarter or less of usual_count, the most held since they were last restocked."""
        c = context()
        return answers.low_stock(c.table, c.account_id, now=c.now)

    return server


NOT_LINKED = "No camera is linked yet. Link the Ring camera from the Ring app first."


def default_context() -> FridgeContext:
    tokens = TokenStore().load()
    if tokens is None:
        raise ToolError(NOT_LINKED)
    return FridgeContext(
        table=FridgeTable(),
        account_id=tokens.account_id,
        now=datetime.now(UTC),
        tz=ZoneInfo(os.environ.get("TIME_ZONE") or "America/Toronto"),
    )
