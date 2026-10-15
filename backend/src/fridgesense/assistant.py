"""Fridge questions answered by Nova acting as an MCP client of the FridgeSense MCP server.

A stand-in for a voice assistant's model: list the server's tools, let Nova pick which to
call through Bedrock Converse tool use, and return a short sentence to speak.
"""

import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from functools import partial
from typing import Any, Literal
from zoneinfo import ZoneInfo

import anyio
from botocore.exceptions import BotoCoreError, ClientError
from mcp import Client

from fridgesense.analysis import DEFAULT_MODEL_ID
from fridgesense.logs import log_event
from fridgesense.table import account_pk
from fridgesense.usage import Prices, Tokens, price

SYSTEM_PROMPT = (
    "You are FridgeSense, a kitchen voice assistant that knows what is in the user's fridge "
    "from a camera that watches each door opening. Your reply is spoken aloud: answer in at "
    "most two short sentences of plain spoken English, with no markdown, lists or emoji. "
    "Use the tools for every fact about the fridge and never guess one: say counts and how "
    "long ago, and say so when an item ran out. For what to cook, suggest one or two ideas "
    "from what is in stock."
)
INFERENCE = {"maxTokens": 300, "temperature": 0.2}
# Bedrock prompt caching: the tool specs and system prompt are read from cache each round.
# Nova 2 Lite rejects a cache point after a toolResult block, and in tools; no ttl.
CACHE_POINT = {"cachePoint": {"type": "default"}}
DEADLINE_S = 12.0
MAX_ROUNDS = 4
DAILY_LIMIT = 100

# The MCP client's HTTP library logs every request URL at INFO, and the URL holds mcp_key.
for _name in ("httpx", "httpx2"):
    logging.getLogger(_name).setLevel(logging.WARNING)

Reason = Literal[
    "mcp_error", "bedrock_error", "too_many_rounds", "timeout", "empty_answer", "over_budget"
]

THINKING = re.compile(r"<thinking>.*?</thinking>", re.DOTALL)
LIST_MARKER = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+", re.MULTILINE)
MARKDOWN = re.compile(r"[*_#`]")


def clean(text: str) -> str:
    """Spoken text: no <thinking> blocks, markdown or list markers, single spaces."""
    text = THINKING.sub(" ", text)
    text = LIST_MARKER.sub("", text)
    text = MARKDOWN.sub("", text)
    return " ".join(text.split())


def mcp_url(host: str, key: str) -> str:
    return f"https://{host}/mcp/{key}"


def tool_specs(tools: list[Any]) -> list[dict]:
    """MCP tools as Converse tool specs, in the server's order."""
    return [
        {
            "toolSpec": {
                "name": t.name,
                "description": t.description or t.name,
                "inputSchema": {"json": t.input_schema},
            }
        }
        for t in tools
    ]


def take_budget(table: Any, account_id: str, now: datetime, tz: ZoneInfo, limit: int) -> bool:
    """Count one assistant question for today (household time); False once `limit` is used."""
    day = now.astimezone(tz).date().isoformat()
    return table.increment_below(account_pk(account_id), f"ASKBUDGET#{day}", "count", limit)


@dataclass
class AssistantResult:
    answer: str
    tools: list[str] = field(default_factory=list)


@dataclass
class AssistantFailure:
    reason: Reason


class _Fail(Exception):
    def __init__(self, reason: Reason):
        super().__init__(reason)
        self.reason = reason


@dataclass
class _Run:
    """What one question has spent and done so far, for the result and the cost log."""

    prices: Prices
    on_usage: Callable[[Tokens, float], None] | None = None
    tools: list[str] = field(default_factory=list)
    rounds: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    usd: float = 0.0
    answer: str | None = None
    started: bool = False  # the MCP connection is up

    def spend(self, usage: dict | None) -> None:
        tokens = Tokens.from_converse(usage)
        usd = price(tokens, self.prices)
        self.rounds += 1
        self.input_tokens += tokens.input
        self.output_tokens += tokens.output
        self.cache_read_tokens += tokens.cache_read
        self.cache_write_tokens += tokens.cache_write
        self.usd = round(self.usd + usd, 6)
        if self.on_usage is not None:
            self.on_usage(tokens, usd)


def _text(result: Any) -> str:
    return " ".join(getattr(c, "text", "") for c in result.content).strip()


def _tool_result(tool_use_id: str, result: Any) -> dict:
    if result.is_error:
        content = [{"text": _text(result) or "The tool failed."}]
    elif result.structured_content is not None:
        content = [{"json": result.structured_content}]
    else:
        content = [{"text": _text(result)}]
    return {
        "toolResult": {
            "toolUseId": tool_use_id,
            "content": content,
            "status": "error" if result.is_error else "success",
        }
    }


def _find_fail(exc: BaseException) -> _Fail | None:
    """The _Fail inside `exc`, which task groups may have wrapped in an exception group."""
    if isinstance(exc, _Fail):
        return exc
    if isinstance(exc, BaseExceptionGroup):
        for inner in exc.exceptions:
            if found := _find_fail(inner):
                return found
    return None


async def _converse(bedrock: Any, request: dict) -> dict:
    try:
        return await anyio.to_thread.run_sync(
            partial(bedrock.converse, **request), abandon_on_cancel=True
        )
    except (ClientError, BotoCoreError):
        raise _Fail("bedrock_error") from None


async def _loop(
    question: str,
    server: Any,
    bedrock: Any,
    model_id: str,
    state: _Run,
    check_time: Callable[[], None],
    max_rounds: int,
) -> None:
    async with Client(server, mode="legacy") as client:
        state.started = True
        try:
            specs = tool_specs((await client.list_tools()).tools)
        except Exception:
            raise _Fail("mcp_error") from None
        messages: list[dict] = [{"role": "user", "content": [{"text": question}]}]
        for round_no in range(1, max_rounds + 1):
            check_time()
            resp = await _converse(
                bedrock,
                {
                    "modelId": model_id,
                    "system": [{"text": SYSTEM_PROMPT}, CACHE_POINT],
                    "messages": messages,
                    "toolConfig": {"tools": specs},
                    "inferenceConfig": INFERENCE,
                },
            )
            state.spend(resp.get("usage", {}))
            message = resp["output"]["message"]
            messages.append(message)
            uses = [b["toolUse"] for b in message["content"] if "toolUse" in b]
            if resp.get("stopReason") != "tool_use" or not uses:
                answer = clean(" ".join(b["text"] for b in message["content"] if "text" in b))
                if not answer:
                    raise _Fail("empty_answer")
                state.answer = answer
                return
            if round_no == max_rounds:
                break
            results = []
            for use in uses:
                check_time()
                state.tools.append(use["name"])
                try:
                    result = await client.call_tool(use["name"], use.get("input") or {})
                except Exception:
                    raise _Fail("mcp_error") from None
                results.append(_tool_result(use["toolUseId"], result))
            messages.append({"role": "user", "content": results})
    raise _Fail("too_many_rounds")


async def run(
    question: str,
    *,
    server: Any,
    bedrock: Any,
    model_id: str = DEFAULT_MODEL_ID,
    prices: Prices | None = None,
    on_usage: Callable[[Tokens, float], None] | None = None,
    clock: Callable[[], float] = time.monotonic,
    deadline_s: float = DEADLINE_S,
    max_rounds: int = MAX_ROUNDS,
    budget: Callable[[], bool] | None = None,
) -> AssistantResult | AssistantFailure:
    """Answer `question` with Nova, calling the MCP `server` (a URL, or an MCPServer in tests).

    Never raises for the known failures: they come back as an AssistantFailure. Logs one
    `ask_agent` cost event per question, without the question or the URL. `budget` is
    asked first; when it says no, nothing is connected or called. `on_usage` gets each
    model call's tokens and cost."""
    if budget is not None and not budget():
        log_event("ask_agent", logging.WARNING, outcome="over_budget")
        return AssistantFailure("over_budget")
    began = time.monotonic()
    start = clock()
    state = _Run(prices or Prices(), on_usage)

    def check_time() -> None:
        if clock() - start > deadline_s:
            raise _Fail("timeout")

    reason: Reason | None = None
    try:
        with anyio.fail_after(deadline_s):
            await _loop(question, server, bedrock, model_id, state, check_time, max_rounds)
    except TimeoutError:
        reason = "timeout"
    except Exception as exc:
        if fail := _find_fail(exc):
            reason = fail.reason
        elif not state.started:
            reason = "mcp_error"  # couldn't connect or initialize
        elif state.answer is None:
            raise
    if state.answer is None and reason is None:
        reason = "timeout"

    log_event(
        "ask_agent",
        logging.INFO if reason is None else logging.WARNING,
        outcome=reason or "answered",
        rounds=state.rounds,
        tools=state.tools,
        input_tokens=state.input_tokens,
        output_tokens=state.output_tokens,
        cache_read_tokens=state.cache_read_tokens,
        cache_write_tokens=state.cache_write_tokens,
        usd=state.usd,
        ms=int((time.monotonic() - began) * 1000),
    )
    if reason is not None:
        return AssistantFailure(reason)
    return AssistantResult(answer=state.answer or "", tools=state.tools)
