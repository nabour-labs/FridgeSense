"""Step Functions task Lambda: one entry point, the step chosen by `task` in the input."""

import logging
import os
import time

import boto3
from botocore.config import Config

from fridgesense import deps, door_events, inventory
from fridgesense.analysis import NovaAnalyzer
from fridgesense.faces import DEFAULT_PRICE, FaceBlurrer
from fridgesense.table import FridgeTable

sleep = time.sleep


def bedrock_client():
    # One HTTP attempt: retries belong to the state machine, where they are visible and
    # bounded. Two Nova requests of at most 5 + 30 s each fit the 90 s task timeout.
    return boto3.client(
        "bedrock-runtime",
        config=Config(
            retries={"total_max_attempts": 1, "mode": "standard"},
            connect_timeout=5,
            read_timeout=30,
        ),
    )


def rekognition_client():
    return boto3.client(
        "rekognition",
        config=Config(retries={"max_attempts": 2}, connect_timeout=5, read_timeout=10),
    )


def _blurrer() -> FaceBlurrer:
    price = float(os.environ.get("FACE_DETECT_PRICE") or DEFAULT_PRICE)
    return FaceBlurrer(rekognition_client(), price)


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
            os.environ.get("DOOR_ZONES"), os.environ.get("DOOR_THRESHOLD")
        )
        return door_events.fetch_stills(
            deps.ring_client(),
            deps.http_client(),
            boto3.client("s3"),
            FridgeTable(),
            _bucket(),
            check,
            _blurrer(),
            state,
            sleep,
            crop=door_events.parse_crop(os.environ.get("STILL_CROP")),
            interval_ms=door_events.parse_interval(os.environ.get("STILL_INTERVAL_MS")),
        )
    if task == "analyze":
        analyzer = NovaAnalyzer.from_env(bedrock_client())
        return inventory.analyze_task(analyzer, boto3.client("s3"), FridgeTable(), _bucket(), state)
    if task == "save":
        return inventory.save_task(FridgeTable(), state)
    if task == "mark_failed":
        return inventory.mark_failed_task(FridgeTable(), state)
    raise ValueError(f"unknown task: {task!r}")
