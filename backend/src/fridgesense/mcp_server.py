"""FridgeSense MCP server: four read-only tools for voice assistants and MCP clients."""

import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from fridgesense import fridge_answers as answers
from fridgesense.store import TokenStore
from fridgesense.table import FridgeTable

INSTRUCTIONS = (
    "FridgeSense knows what is in the user's fridge, from a camera that watches each door "
    "opening. Use these tools to answer questions like 'Do I have milk?', 'What's in my "
    "fridge?' or 'When was the fridge last opened?'. Answers are spoken: keep them short, "
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
