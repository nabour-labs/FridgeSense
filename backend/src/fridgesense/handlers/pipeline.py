"""Step Functions task Lambda: one entry point, the step chosen by `task` in the input."""

import logging
import os
import time

import boto3
from botocore.config import Config

from fridgesense import deps, door_events, inventory
from fridgesense.analysis import NovaAnalyzer
from fridgesense.table import FridgeTable

sleep = time.sleep


def bedrock_client():
    # Retries belong to the state machine, where they are visible and bounded.
    return boto3.client(
        "bedrock-runtime", config=Config(retries={"max_attempts": 1}, read_timeout=60)
    )


def _bucket() -> str:
    return os.environ["STILLS_BUCKET"]


def handler(event, context):
    logging.getLogger().setLevel(logging.INFO)
    # The state machine sends {"task", "input"}; direct calls may send the state flat.
    state = event["input"] if "input" in event else {k: v for k, v in event.items() if k != "task"}
    task = event.get("task")
    if task == "find_window":
        return door_events.find_window(deps.ring_client(), state)
    if task == "fetch_stills":
        check = door_events.DoorCheck.from_config(
            os.environ.get("DOOR_BOX"), os.environ.get("DOOR_THRESHOLD")
        )
        return door_events.fetch_stills(
            deps.ring_client(),
            deps.http_client(),
            boto3.client("s3"),
            FridgeTable(),
            _bucket(),
            check,
            state,
            sleep,
        )
    if task == "analyze":
        analyzer = NovaAnalyzer.from_env(bedrock_client())
        return inventory.analyze_task(analyzer, boto3.client("s3"), FridgeTable(), _bucket(), state)
    if task == "save":
        return inventory.save_task(FridgeTable(), state)
    if task == "mark_failed":
        return inventory.mark_failed_task(FridgeTable(), state)
    raise ValueError(f"unknown task: {task!r}")
