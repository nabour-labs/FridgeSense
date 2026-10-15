"""Workflow tasks after the door check: Nova analysis and saving changes to the inventory."""

import logging

from fridgesense.analysis import BedrockRejected, NovaAnalyzer
from fridgesense.logs import log_event
from fridgesense.table import FridgeTable, account_pk


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
