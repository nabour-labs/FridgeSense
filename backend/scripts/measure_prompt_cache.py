"""Measure Bedrock prompt caching on Nova with the app's real request shapes. Calls Bedrock.

Run by hand only, with the owner's OK (it costs well under a cent):

    set -a; source ../.env; set +a
    uv run python scripts/measure_prompt_cache.py --yes

It sends:
- the door-opening analysis request with cache points (2 references, 4 stills), twice;
- the assistant's second-round request (a cache point after the system prompt only), twice.

Pass: the second analysis call reads from cache (`cacheReadInputTokens > 0`), the second
assistant call reads from cache, and no call raises ValidationException.
"""

import argparse
import io
import os
import random
import sys
import time
from typing import Any

from fridgesense.analysis import DEFAULT_MODEL_ID, build_request
from fridgesense.assistant import CACHE_POINT, INFERENCE, SYSTEM_PROMPT
from fridgesense.usage import Prices, Tokens, price

PAUSE_S = 2.0
TOOLS = [
    {
        "toolSpec": {
            "name": "find_item",
            "description": "Whether an item is in the fridge, how many, and when it last changed.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {"name": {"type": "string", "description": "e.g. milk"}},
                    "required": ["name"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "get_inventory",
            "description": "Everything in the fridge now, optionally one category.",
            "inputSchema": {
                "json": {"type": "object", "properties": {"category": {"type": "string"}}}
            },
        }
    },
]


def summarize(usage: dict[str, Any] | None, metrics: dict[str, Any] | None) -> dict[str, int]:
    """One table row from a Converse response's usage and metrics; absent fields are 0."""
    tokens = Tokens.from_converse(usage)
    return {
        "input": tokens.input,
        "cache_read": tokens.cache_read,
        "cache_write": tokens.cache_write,
        "output": tokens.output,
        "latency_ms": int((metrics or {}).get("latencyMs", 0)),
    }


def picture(seed: int, size: tuple[int, int]) -> bytes:
    """A busy JPEG, so the image costs about what a real fridge still does."""
    from PIL import Image, ImageDraw

    rng = random.Random(seed)
    img = Image.new("RGB", size, (rng.randrange(256), rng.randrange(256), rng.randrange(256)))
    draw = ImageDraw.Draw(img)
    for _ in range(60):
        x, y = rng.randrange(size[0]), rng.randrange(size[1])
        box = (x, y, x + rng.randrange(20, 200), y + rng.randrange(20, 200))
        draw.rectangle(box, fill=(rng.randrange(256), rng.randrange(256), rng.randrange(256)))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=80)
    return out.getvalue()


def analysis_request(model_id: str) -> dict:
    references = [("milk bag", picture(1, (640, 480))), ("soda can", picture(2, (640, 480)))]
    stills = [picture(10 + n, (1280, 720)) for n in range(4)]
    return build_request(model_id, stills, ["milk", "eggs"], references, cache=True)


def assistant_request(model_id: str) -> dict:
    return {
        "modelId": model_id,
        "system": [{"text": SYSTEM_PROMPT}, CACHE_POINT],
        "messages": [
            {"role": "user", "content": [{"text": "Do I have milk?"}]},
            {
                "role": "assistant",
                "content": [
                    {
                        "toolUse": {
                            "toolUseId": "tu-1",
                            "name": "find_item",
                            "input": {"name": "milk"},
                        }
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "toolResult": {
                            "toolUseId": "tu-1",
                            "content": [
                                {"json": {"query": "milk", "in_fridge": True, "total_count": 1}}
                            ],
                            "status": "success",
                        }
                    },
                ],
            },
        ],
        "toolConfig": {"tools": TOOLS},
        "inferenceConfig": INFERENCE,
    }


def send_twice(client: Any, label: str, request: dict, prices: Prices) -> list[dict]:
    rows = []
    for attempt in (1, 2):
        try:
            resp = client.converse(**request)
        except Exception as e:  # report and keep going: the error is the finding
            print(f"{label} #{attempt}: {type(e).__name__}: {e}")
            rows.append({"error": type(e).__name__})
            continue
        row = summarize(resp.get("usage"), resp.get("metrics"))
        row["usd"] = price(Tokens.from_converse(resp.get("usage")), prices)
        rows.append(row)
        print(f"{label} #{attempt}: {row}")
        time.sleep(PAUSE_S)
    return rows


def verdict(rows: list[dict]) -> bool:
    return len(rows) == 2 and "error" not in rows[1] and rows[1]["cache_read"] > 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--yes", action="store_true", help="really call Bedrock (costs money)")
    args = parser.parse_args(argv)
    if not args.yes:
        print("This calls Bedrock and costs money. Rerun with --yes.", file=sys.stderr)
        return 2

    import boto3

    model_id = os.environ.get("NOVA_MODEL_ID") or DEFAULT_MODEL_ID
    client = boto3.Session(profile_name=os.environ.get("AWS_PROFILE")).client(
        "bedrock-runtime", region_name="us-east-1"
    )
    prices = Prices.from_env()
    print(f"model: {model_id}")
    analysis = send_twice(client, "analysis", analysis_request(model_id), prices)
    assistant = send_twice(client, "assistant", assistant_request(model_id), prices)
    print(f"analysis image prefix cached: {'PASS' if verdict(analysis) else 'FAIL'}")
    print(f"assistant system cache point: {'PASS' if verdict(assistant) else 'FAIL'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
