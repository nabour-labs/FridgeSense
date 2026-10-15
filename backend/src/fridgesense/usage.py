"""Tokens, cost and daily totals for every LLM call."""

import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from zoneinfo import ZoneInfo

from fridgesense.logs import log_event
from fridgesense.table import account_pk

# USD per 1K tokens, Nova 2 Lite on demand in us-east-1 (AWS Price List API, 2026-10-15).
DEFAULT_PRICE_IN = 0.00033
DEFAULT_PRICE_OUT = 0.00275
DEFAULT_PRICE_CACHE_READ = 0.0000825
DEFAULT_PRICE_CACHE_WRITE = 0.0  # Nova 2 Lite doesn't charge for cache writes


@dataclass(frozen=True)
class Tokens:
    """One call's token counts. `input` is uncached input only, as Converse reports it."""

    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_write: int = 0

    @property
    def total_input(self) -> int:
        return self.input + self.cache_read + self.cache_write

    @classmethod
    def from_converse(cls, usage: dict[str, Any] | None) -> "Tokens":
        usage = usage or {}
        return cls(
            input=int(usage.get("inputTokens", 0)),
            output=int(usage.get("outputTokens", 0)),
            cache_read=int(usage.get("cacheReadInputTokens", 0)),
            cache_write=int(usage.get("cacheWriteInputTokens", 0)),
        )


@dataclass(frozen=True)
class Prices:
    """USD per 1K tokens."""

    input: float = DEFAULT_PRICE_IN
    output: float = DEFAULT_PRICE_OUT
    cache_read: float = DEFAULT_PRICE_CACHE_READ
    cache_write: float = DEFAULT_PRICE_CACHE_WRITE

    @classmethod
    def from_env(cls) -> "Prices":
        def get(name: str, default: float) -> float:
            return float(os.environ.get(name) or default)

        return cls(
            input=get("NOVA_PRICE_IN", DEFAULT_PRICE_IN),
            output=get("NOVA_PRICE_OUT", DEFAULT_PRICE_OUT),
            cache_read=get("NOVA_PRICE_CACHE_READ", DEFAULT_PRICE_CACHE_READ),
            cache_write=get("NOVA_PRICE_CACHE_WRITE", DEFAULT_PRICE_CACHE_WRITE),
        )


def price(tokens: Tokens, prices: Prices) -> float:
    """USD for one call, rounded half-up to 6 decimals (exact decimal math, no float drift)."""
    pairs = (
        (tokens.input, prices.input),
        (tokens.output, prices.output),
        (tokens.cache_read, prices.cache_read),
        (tokens.cache_write, prices.cache_write),
    )
    usd = sum(Decimal(n) * Decimal(str(p)) for n, p in pairs) / 1000
    return float(usd.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


class UsageRecorder:
    """Called with each LLM call's tokens and cost: logs `llm_usage`, then adds the call to
    the account's daily totals (`USAGE#<date>`, household day). Never raises."""

    def __init__(
        self,
        table: Any,
        tz: ZoneInfo,
        *,
        source: str,
        account_id: str,
        model_id: str,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self.table = table
        self.tz = tz
        self.source = source
        self.account_id = account_id
        self.model_id = model_id
        self.clock = clock

    def __call__(self, tokens: Tokens, usd: float) -> None:
        log_event(
            "llm_usage",
            source=self.source,
            account_id=self.account_id,
            model_id=self.model_id,
            input_tokens=tokens.input,
            output_tokens=tokens.output,
            cache_read_tokens=tokens.cache_read,
            cache_write_tokens=tokens.cache_write,
            total_input_tokens=tokens.total_input,
            usd=usd,
        )
        day = self.clock().astimezone(self.tz).date().isoformat()
        try:
            self.table.add_many(
                account_pk(self.account_id),
                f"USAGE#{day}",
                {
                    "calls": 1,
                    "input_tokens": tokens.input,
                    "output_tokens": tokens.output,
                    "cache_read_tokens": tokens.cache_read,
                    "cache_write_tokens": tokens.cache_write,
                    "usd": usd,
                    f"{self.source}_calls": 1,
                    f"{self.source}_usd": usd,
                },
            )
        except Exception as e:
            log_event(
                "llm_usage_store_failed",
                logging.WARNING,
                source=self.source,
                account_id=self.account_id,
                error=type(e).__name__,
            )
