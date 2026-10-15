"""Workflow tasks after the door check: Nova analysis and saving changes to the inventory."""

import logging
import time

from fridgesense import analysis_config
from fridgesense.analysis import BedrockRejected, NovaAnalyzer
from fridgesense.door_events import iso_utc
from fridgesense.logs import log_event
from fridgesense.table import FridgeTable, TransactionConflict, account_pk


def in_stock_names(table: FridgeTable, account_id: str) -> list[str]:
    items = table.query(account_id, "ITEM#")
    return sorted(i["sk"].removeprefix("ITEM#") for i in items if i.get("quantity", 0) > 0)


def analyze_task(analyzer: NovaAnalyzer, s3, table: FridgeTable, bucket: str, state: dict) -> dict:
    account_id, door_sk = state["account_id"], state["door_sk"]
    stills = [s3.get_object(Bucket=bucket, Key=k)["Body"].read() for k in state["still_keys"]]
    context = {"account_id": account_id, "door_sk": door_sk}
    config = analysis_config.load(table, account_id)
    references = [(r.annotation, r.image) for r in config.references]
    result = None
    try:
        result = analyzer.analyze(
            stills,
            in_stock_names(table, account_id),
            context,
            references=references,
            instructions=config.instructions,
        )
    except BedrockRejected as e:
        log_event("analysis_failed", logging.ERROR, reason=str(e), **context)
    finally:
        # Record what was spent, including on attempts the workflow will retry.
        if result is not None and result.usage:
            table.add(account_pk(account_id), door_sk, "nova_usd", result.usd)
    if result is None or result.changes is None:
        if result is not None:
            log_event("analysis_failed", logging.ERROR, reason="invalid answer", **context)
        _set_status(table, account_id, door_sk, "analysis_failed")
        return {**state, "outcome": "analysis_failed"}
    return {**state, "analysis": result.changes.model_dump()}


def mark_failed_task(table: FridgeTable, state: dict) -> dict:
    log_event(
        "analysis_failed",
        logging.ERROR,
        reason=str(state.get("error", {}).get("Error", "unknown")),
        account_id=state["account_id"],
        door_sk=state["door_sk"],
    )
    _set_status(table, state["account_id"], state["door_sk"], "analysis_failed")
    return {**state, "outcome": "analysis_failed"}


def _set_status(table: FridgeTable, account_id: str, door_sk: str, status: str) -> None:
    table.update(account_pk(account_id), door_sk, {"status": status})


CONFIDENCE_CUTOFF = 0.7


def normalize_name(item: str) -> tuple[str, str]:
    """(inventory key, display name): spaces collapsed; the key is also lower case."""
    display = " ".join(item.split())
    return display.lower(), display


def quantity_put(
    current: dict | None,
    pk: str,
    key: str,
    display: str,
    category: str,
    delta: int,
    when: str,
) -> dict | None:
    """The item after adding `delta`: never below 0, and nothing for removing an unknown item."""
    if current is None and delta <= 0:
        return None
    current = current or {}
    quantity = max(0, current.get("quantity", 0) + delta)
    return {
        "pk": pk,
        "sk": f"ITEM#{key}",
        "name": current.get("name", display),
        "category": current.get("category", category),
        "quantity": quantity,
        "first_seen_at": current.get("first_seen_at", when),
        "last_changed_at": when,
        **stock_age(current, quantity, when),
    }


def stock_age(current: dict, quantity: int, when: str) -> dict:
    """`stocked_at` and `peak_quantity` after a change: reset on restock, dropped at 0."""
    if quantity <= 0:
        return {}
    if current.get("quantity", 0) <= 0:
        return {"stocked_at": when, "peak_quantity": quantity}
    return {
        "stocked_at": current.get("stocked_at") or current.get("first_seen_at", when),
        "peak_quantity": max(current.get("peak_quantity", current["quantity"]), quantity),
    }


def save_task(table: FridgeTable, state: dict) -> dict:
    """Apply one door event's changes to the inventory, exactly once."""
    account_id, door_sk = state["account_id"], state["door_sk"]
    pk = account_pk(account_id)
    door = table.get(pk, door_sk)
    if door is None or door.get("status") != "analyzing":
        return {**state, "outcome": "already_saved"}
    when = door.get("closed_at") or door.get("opened_at")

    changes, deltas, pending = [], {}, []
    for direction in ("added", "removed"):
        for c in state["analysis"][direction]:
            key, display = normalize_name(c["item"])
            applied = c["confidence"] >= CONFIDENCE_CUTOFF
            record = {
                "item": key,
                "name": display,
                "category": c["category"],
                "direction": direction,
                "quantity": c["quantity"],
                "confidence": c["confidence"],
                "applied": applied,
            }
            changes.append(record)
            if applied:
                d = deltas.setdefault(key, {"delta": 0, "name": display, "category": c["category"]})
                d["delta"] += c["quantity"] if direction == "added" else -c["quantity"]
            else:
                pending.append({**record, "change_index": len(changes) - 1})

    writes = []
    for key, d in deltas.items():
        current = table.get(pk, f"ITEM#{key}")
        item = quantity_put(current, pk, key, d["name"], d["category"], d["delta"], when)
        if item is not None:
            writes.append({"Put": {"Item": item}})
    for n, p in enumerate(pending, start=1):
        writes.append(
            {
                "Put": {
                    "Item": {
                        "pk": pk,
                        "sk": f"PENDING#{door.get('opened_at')}#{n}",
                        "door_sk": door_sk,
                        **{k: p[k] for k in ("item", "category", "direction", "quantity")},
                        "confidence": p["confidence"],
                        "change_index": p["change_index"],
                    }
                }
            }
        )
    door_update = {
        "Update": {
            "Key": {"pk": pk, "sk": door_sk},
            "UpdateExpression": "SET #s = :done, #c = :changes, #p = :pending",
            "ConditionExpression": "#s = :analyzing",
            "ExpressionAttributeNames": {"#s": "status", "#c": "changes", "#p": "pending_count"},
            "ExpressionAttributeValues": {
                ":done": "done",
                ":analyzing": "analyzing",
                ":changes": changes,
                ":pending": len(pending),
            },
        }
    }
    try:
        table.transact([door_update, *writes])
    except TransactionConflict as e:
        if e.reasons and e.reasons[0] == "ConditionalCheckFailed":
            return {**state, "outcome": "already_saved"}
        raise
    log_event(
        "door_event_saved",
        account_id=account_id,
        door_sk=door_sk,
        applied=len(changes) - len(pending),
        pending=len(pending),
    )
    return {
        **state,
        "outcome": "saved",
        "applied": len(changes) - len(pending),
        "pending": len(pending),
    }


class PendingNotFound(Exception):
    """No such pending change (or it was confirmed or rejected meanwhile)."""


def _pending(table: FridgeTable, pk: str, pending_sk: str) -> dict:
    if not pending_sk.startswith("PENDING#"):
        raise PendingNotFound(pending_sk)
    pending = table.get(pk, pending_sk)
    if pending is None:
        raise PendingNotFound(pending_sk)
    return pending


def _resolve(table: FridgeTable, pk: str, pending_sk: str, door_update: dict | None, writes: list):
    """Delete the pending item (it must still exist) together with the other writes."""
    ops = [
        {
            "Delete": {
                "Key": {"pk": pk, "sk": pending_sk},
                "ConditionExpression": "attribute_exists(sk)",
            }
        },
        *writes,
    ]
    if door_update:
        ops.append(door_update)
    try:
        table.transact(ops)
    except TransactionConflict as e:
        if e.reasons and e.reasons[0] == "ConditionalCheckFailed":
            raise PendingNotFound(pending_sk) from None
        raise


def _door_change_update(pk: str, pending: dict, sets: dict) -> dict | None:
    """Update the pending change's entry on its door event and lower pending_count."""
    index = pending.get("change_index")
    if index is None or "door_sk" not in pending:
        return None
    names = {"#c": "changes", "#p": "pending_count"}
    values = {":one": 1}
    parts = []
    for n, (field_name, value) in enumerate(sets.items()):
        names[f"#f{n}"] = field_name
        values[f":v{n}"] = value
        parts.append(f"#c[{int(index)}].#f{n} = :v{n}")
    return {
        "Update": {
            "Key": {"pk": pk, "sk": pending["door_sk"]},
            "UpdateExpression": "SET " + ", ".join(parts) + ", #p = #p - :one",
            "ExpressionAttributeNames": names,
            "ExpressionAttributeValues": values,
        }
    }


def confirm_pending(
    table: FridgeTable,
    account_id: str,
    pending_sk: str,
    item: str | None = None,
    quantity: int | None = None,
    now: str | None = None,
) -> None:
    """Apply a pending change to the inventory, optionally with a corrected name or count."""
    pk = account_pk(account_id)
    pending = _pending(table, pk, pending_sk)
    key, display = normalize_name(item or pending["item"])
    qty = int(quantity if quantity is not None else pending["quantity"])
    if qty < 1:
        raise ValueError("quantity must be at least 1")
    delta = qty if pending["direction"] == "added" else -qty
    when = now or _now_iso()
    current = table.get(pk, f"ITEM#{key}")
    put = quantity_put(current, pk, key, display, pending["category"], delta, when)
    door_update = _door_change_update(
        pk, pending, {"applied": True, "item": key, "name": display, "quantity": qty}
    )
    _resolve(table, pk, pending_sk, door_update, [{"Put": {"Item": put}}] if put else [])
    log_event("pending_confirmed", account_id=account_id, item=key, quantity=qty)


def reject_pending(table: FridgeTable, account_id: str, pending_sk: str) -> None:
    """Discard a pending change without touching the inventory."""
    pk = account_pk(account_id)
    pending = _pending(table, pk, pending_sk)
    _resolve(table, pk, pending_sk, _door_change_update(pk, pending, {"rejected": True}), [])
    log_event("pending_rejected", account_id=account_id, item=pending["item"])


def set_quantity(
    table: FridgeTable, account_id: str, item: str, quantity: int, now: str | None = None
) -> None:
    """Set an item's count by hand, creating it (category other) if needed."""
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 0:
        raise ValueError("quantity must be a whole number of 0 or more")
    pk = account_pk(account_id)
    key, display = normalize_name(item)
    when = now or _now_iso()
    current = table.get(pk, f"ITEM#{key}") or {}
    table.put(
        {
            "pk": pk,
            "sk": f"ITEM#{key}",
            "name": current.get("name", display),
            "category": current.get("category", "other"),
            "quantity": quantity,
            "first_seen_at": current.get("first_seen_at", when),
            "last_changed_at": when,
            **stock_age(current, quantity, when),
        }
    )
    log_event("quantity_set", account_id=account_id, item=key, quantity=quantity)


def _now_iso() -> str:
    return iso_utc(int(time.time() * 1000))
