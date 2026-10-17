"""Debug traces: what the door check and the Nova analysis saw, decided, spent and took.

Files go to S3 under the event's `debug/` folder (expired with the bucket after 7 days);
one TRACE# summary item per motion makes them listable. Writing a trace never raises.
"""

import io
import json
import logging
import os
import re
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from PIL import Image

from fridgesense import door_calibration
from fridgesense.analysis import RESPONSE_FIELDS, CallRecord
from fridgesense.door_events import (
    BASELINE_SIZE,
    DoorCheck,
    Downloaded,
    StillResult,
    ZoneValue,
    iso_utc,
    stills_prefix,
)
from fridgesense.logs import log_event
from fridgesense.table import FridgeTable, account_pk

TRACE_DAYS = 7
WRITE_WORKERS = 8


def debug_prefix(account_id: str, device_id: str, start_ms: int) -> str:
    return f"{stills_prefix(account_id, device_id, start_ms)}debug/"


def trace_sk(device_id: str, start_ms: int) -> str:
    return f"TRACE#{iso_utc(start_ms)}#{device_id}"


@dataclass
class DoorTrace:
    """One motion's door check: every requested still, its zone values, and the outcome."""

    stills: list[Downloaded]
    values: dict[int, list[ZoneValue]]  # by still number, for downloaded stills
    check: DoorCheck
    outcome: str
    open_span: list[int] = field(default_factory=list)  # still numbers
    picked: list[int] = field(default_factory=list)  # still numbers
    stored_keys: list[str] = field(default_factory=list)
    door_sk: str | None = None
    opened_at: str | None = None
    closed_at: str | None = None
    alignment: dict | None = None  # {"dx", "dy", "error", "ok"} when the bookends were aligned

    def results(self) -> dict[int, StillResult]:
        return {n: self.check.result_of(v) for n, v in self.values.items()}


def _box_json(box) -> dict:
    return dict(zip(("x", "y", "width", "height"), box, strict=True))


BASELINE_SCALE = 8


def baseline_png(baseline: bytes) -> bytes:
    """The 32x32 RGB baseline as a PNG, scaled up so it can be seen."""
    img = Image.frombytes("RGB", BASELINE_SIZE, baseline)
    w, h = BASELINE_SIZE
    img = img.resize((w * BASELINE_SCALE, h * BASELINE_SCALE), Image.Resampling.NEAREST)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _zone_json(v: ZoneValue) -> dict:
    return {"zone": v.zone, "value": round(v.value, 4), "threshold": v.threshold, "open": v.open}


def writer_from_env(s3, table: FridgeTable, bucket: str) -> "TraceWriter | NullTraceWriter":
    """Tracing is on unless DEBUG_TRACES is `false`."""
    if (os.environ.get("DEBUG_TRACES") or "").strip().lower() == "false":
        return NullTraceWriter()
    return TraceWriter(s3, table, bucket)


class NullTraceWriter:
    """Tracing off: writes nothing."""

    def door(self, state: dict, trace: DoorTrace) -> None:
        pass

    def nova(self, state, run_ms, record, references, still_keys) -> None:
        pass


def _request_content(
    request: dict, n_references: int, ref_keys: list[str], still_keys: list[str]
) -> list[dict]:
    """The request's content blocks, images replaced by what they were and where they are."""
    content, images = [], 0
    for block in request["messages"][0]["content"]:
        if "text" in block:
            content.append({"type": "text", "text": block["text"]})
        elif "cachePoint" in block:
            content.append({"type": "cache_point"})
        elif "image" in block:
            images += 1
            if images <= n_references:
                content.append(
                    {"type": "image", "role": "reference", "n": images, "key": ref_keys[images - 1]}
                )
            else:
                n = images - n_references
                key = still_keys[n - 1] if n <= len(still_keys) else None
                content.append({"type": "image", "role": "still", "n": n, "key": key})
    return content


class TraceWriter:
    def __init__(self, s3, table: FridgeTable, bucket: str):
        self.s3 = s3
        self.table = table
        self.bucket = bucket
        self._ref_keys: dict[int, list[str]] = {}  # by run_ms: references written once per run

    def _put(self, key: str, body: bytes, content_type: str) -> None:
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=body, ContentType=content_type)

    def _failed(self, state: dict, part: str, e: Exception) -> None:
        log_event(
            "debug_trace_failed",
            logging.WARNING,
            account_id=state.get("account_id"),
            device_id=state.get("device_id"),
            part=part,
            error=type(e).__name__,
        )

    def door(self, state: dict, trace: DoorTrace) -> None:
        """Raw stills, then door.json, then the summary item. Never raises."""
        try:
            self._door_files(state, trace)
        except Exception as e:  # a trace must never break the pipeline
            self._failed(state, "door", e)
        try:
            self._door_summary(state, trace)
        except Exception as e:
            self._failed(state, "summary", e)

    def _door_files(self, state: dict, trace: DoorTrace) -> None:
        window = state["window"]
        prefix = debug_prefix(state["account_id"], state["device_id"], window["start_ms"])
        results = trace.results()
        raw = [s for s in trace.stills if s.data is not None]
        with ThreadPoolExecutor(max_workers=WRITE_WORKERS) as pool:
            list(pool.map(lambda s: self._put(f"{prefix}raw-{s.n}.jpg", s.data, "image/jpeg"), raw))
        stills = []
        for s in trace.stills:
            result = results.get(s.n)
            stills.append(
                {
                    "n": s.n,
                    "at_ms": s.at_ms,
                    "key": f"{prefix}raw-{s.n}.jpg" if s.data is not None else None,
                    "missing_status": s.status if s.data is None else None,
                    "zones": [_zone_json(v) for v in trace.values.get(s.n, [])],
                    "best_zone": result.zone if result else None,
                    "open": result.is_open if result else None,
                }
            )
        doc = {
            "window": {
                "start_ms": window["start_ms"],
                "end_ms": window["end_ms"],
                "ring_event_id": window.get("ring_event_id"),
            },
            "outcome": trace.outcome,
            "door_sk": trace.door_sk,
            "opened_at": trace.opened_at,
            "closed_at": trace.closed_at,
            "rule": self._rule(state, trace.check, prefix),
            "rules": trace.check.source,
            "alignment": trace.alignment,
            "stills": stills,
            "open_span": trace.open_span,
            "picked": trace.picked,
            "stored_keys": trace.stored_keys,
        }
        self._put(f"{prefix}door.json", json.dumps(doc).encode(), "application/json")

    def _rule(self, state: dict, check: DoorCheck, prefix: str) -> dict:
        setup = check.source in ("setup", "tuned")
        zones = []
        for n, rule in enumerate(check.rules, 1):
            baseline_key = None
            if setup and rule.baseline is not None:
                baseline_key = f"{prefix}baseline-{n}.png"
                self._put(baseline_key, baseline_png(rule.baseline), "image/png")
            zones.append(
                {
                    "zone": n,
                    "box": _box_json(rule.box),
                    "feature": rule.feature,
                    "direction": rule.direction,
                    "threshold": rule.threshold,
                    "margin": rule.margin if setup else None,
                    "baseline_key": baseline_key,
                }
            )
        references = []
        if setup:
            account_id, device_id = state["account_id"], state["device_id"]
            for ref in door_calibration.list_references(self.table, account_id, device_id):
                ref_id = ref.sk.removeprefix(door_calibration.ref_prefix(device_id))
                key = f"{prefix}door-ref-{ref_id}.jpg"
                self._put(key, ref.image, "image/jpeg")
                references.append(
                    {
                        "id": ref_id,
                        "status": ref.status,
                        "box": _box_json(ref.box),
                        "created_at": ref.created_at,
                        "key": key,
                    }
                )
        return {
            "source": check.source,
            "ran_at": check.ran_at if setup else None,
            "zones": zones,
            "references": references,
        }

    def _door_summary(self, state: dict, trace: DoorTrace) -> None:
        window = state["window"]
        results = list(trace.results().values())
        best = None
        if results:
            b = trace.check.best(results)
            best = {
                "value": round(b.value, 4),
                "zone": b.zone,
                "feature": b.feature,
                "threshold": b.threshold,
            }
        self.table.put(
            {
                "pk": account_pk(state["account_id"]),
                "sk": trace_sk(state["device_id"], window["start_ms"]),
                "device_id": state["device_id"],
                "ring_event_id": window.get("ring_event_id"),
                "start_ms": window["start_ms"],
                "end_ms": window["end_ms"],
                "outcome": trace.outcome,
                "zones_source": trace.check.source,
                "best": best,
                "stills_requested": len(trace.stills),
                "stills_downloaded": sum(1 for d in trace.stills if d.data is not None),
                "door_sk": trace.door_sk,
                "nova_calls": [],
                "ttl": window["start_ms"] // 1000 + TRACE_DAYS * 86400,
            }
        )

    def nova(
        self,
        state: dict,
        run_ms: int,
        record: CallRecord,
        references: Sequence[tuple[str, bytes]],
        still_keys: list[str],
    ) -> None:
        """nova-<run_ms>-<attempt>.json (plus the run's reference images), then the summary."""
        try:
            start_ms = state["window"]["start_ms"]
            prefix = debug_prefix(state["account_id"], state["device_id"], start_ms)
        except Exception as e:  # not a traced motion: nothing to attach the call to
            self._failed(state, "nova", e)
            return
        key = f"{prefix}nova-{run_ms}-{record.attempt}.json"
        numbers = {
            "input_tokens": record.tokens.input,
            "output_tokens": record.tokens.output,
            "cache_read_tokens": record.tokens.cache_read,
            "cache_write_tokens": record.tokens.cache_write,
            "usd": record.usd,
            "latency_ms": record.latency_ms,
            "wall_ms": record.wall_ms,
            "error_code": record.error_code,
        }
        try:
            ref_keys = self._references(prefix, run_ms, references)
            request = record.request
            doc = {
                "attempt": record.attempt,
                "run_ms": run_ms,
                "model_id": request["modelId"],
                "outcome": record.outcome,
                "request": {
                    "content": _request_content(request, len(references), ref_keys, still_keys),
                    "inferenceConfig": request.get("inferenceConfig"),
                    "toolConfig": request.get("toolConfig"),
                },
                "response": None
                if record.response is None
                else {k: record.response[k] for k in RESPONSE_FIELDS if k in record.response},
                **numbers,
            }
            self._put(key, json.dumps(doc, default=str).encode(), "application/json")
        except Exception as e:  # a trace must never break the pipeline
            self._failed(state, "nova", e)
        try:
            entry = {"attempt": record.attempt, "run_ms": run_ms, "outcome": record.outcome}
            self.table.append(
                account_pk(state["account_id"]),
                trace_sk(state["device_id"], start_ms),
                "nova_calls",
                [{**entry, **numbers, "key": key}],
            )
        except Exception as e:
            self._failed(state, "summary", e)

    def _references(
        self, prefix: str, run_ms: int, references: Sequence[tuple[str, bytes]]
    ) -> list[str]:
        if run_ms not in self._ref_keys:
            keys = []
            for n, (_, data) in enumerate(references, start=1):
                ref_key = f"{prefix}nova-{run_ms}-ref-{n}.jpg"
                self._put(ref_key, data, "image/jpeg")
                keys.append(ref_key)
            self._ref_keys[run_ms] = keys
        return self._ref_keys[run_ms]


NOVA_FILE = re.compile(r"nova-(\d+)-(\d+)\.json$")


def load(s3, bucket: str, account_id: str, item: dict) -> tuple[dict, list[dict]] | None:
    """A motion's door.json and its Nova call traces (oldest first), or None once expired."""
    prefix = debug_prefix(account_id, item["device_id"], int(item["start_ms"]))
    try:
        door = json.loads(s3.get_object(Bucket=bucket, Key=f"{prefix}door.json")["Body"].read())
    except s3.exceptions.NoSuchKey:
        return None
    found = []
    pages = s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=f"{prefix}nova-")
    for page in pages:
        for obj in page.get("Contents", []):
            match = NOVA_FILE.search(obj["Key"])
            if match:
                found.append(((int(match[1]), int(match[2])), obj["Key"]))
    calls = [
        json.loads(s3.get_object(Bucket=bucket, Key=key)["Body"].read()) for _, key in sorted(found)
    ]
    return door, calls


def _linked(entry: dict, sign, key: str = "key", url: str = "url") -> dict:
    out = {k: v for k, v in entry.items() if k != key}
    out[url] = sign(entry[key]) if entry.get(key) else None
    return out


def with_links(doc: dict, sign) -> dict:
    """A door.json or Nova call trace with every S3 key swapped for a download link."""
    out = dict(doc)
    if "stills" in doc:  # door.json
        out["stills"] = [_linked(s, sign) for s in doc["stills"]]
        rule = doc["rule"]
        out["rule"] = {
            **rule,
            "zones": [_linked(z, sign, "baseline_key", "baseline_url") for z in rule["zones"]],
            "references": [_linked(r, sign) for r in rule["references"]],
        }
        out.pop("stored_keys", None)
        out["stored_urls"] = [sign(k) for k in doc.get("stored_keys", [])]
    if "request" in doc:  # Nova call trace
        content = [
            _linked(b, sign) if b["type"] == "image" else b for b in doc["request"]["content"]
        ]
        out["request"] = {**doc["request"], "content": content}
    return out
