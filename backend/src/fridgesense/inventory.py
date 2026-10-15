"""Workflow tasks after the door check: Nova analysis and saving changes to the inventory."""

import logging

from fridgesense.analysis import BedrockRejected, NovaAnalyzer
from fridgesense.logs import log_event
from fridgesense.table import FridgeTable, TransactionConflict, account_pk


def in_stock_names(table: FridgeTable, account_id: str) -> list[str]:
    items = table.query(account_id, "ITEM#")
    return sorted(i["sk"].removeprefix("ITEM#") for i in items if i.get("quantity", 0) > 0)


def analyze_task(analyzer: NovaAnalyzer, s3, table: FridgeTable, bucket: str, state: dict) -> dict:
    account_id, door_sk = state["account_id"], state["door_sk"]
    stills = [s3.get_object(Bucket=bucket, Key=k)["Body"].read() for k in state["still_keys"]]
    context = {"account_id": account_id, "door_sk": door_sk}
    result = None
    try:
        result = analyzer.analyze(stills, in_stock_names(table, account_id), context)
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
                pending.append(record)

    writes = []
    for key, d in deltas.items():
        current = table.get(pk, f"ITEM#{key}")
        if current is None and d["delta"] <= 0:
            continue  # removing something we never saw: nothing to track
        quantity = max(0, (current or {}).get("quantity", 0) + d["delta"])
        writes.append(
            {
                "Put": {
                    "Item": {
                        "pk": pk,
                        "sk": f"ITEM#{key}",
                        "name": (current or {}).get("name", d["name"]),
                        "category": (current or {}).get("category", d["category"]),
                        "quantity": quantity,
                        "first_seen_at": (current or {}).get("first_seen_at", when),
                        "last_changed_at": when,
                    }
                }
            }
        )
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
