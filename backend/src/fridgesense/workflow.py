"""Starting the door-event workflow (Step Functions) from a motion event."""

import json
import os
import re

import boto3
from botocore.exceptions import ClientError

from fridgesense.logs import log_event
from fridgesense.webhook import LoggingMotionHandler, MotionEvent, MotionHandler

_UNSAFE = re.compile(r"[^A-Za-z0-9_-]")


def run_name(device_id: str, timestamp_ms: int) -> str:
    """One name per device and motion time; Step Functions refuses a repeat."""
    return f"{_UNSAFE.sub('-', device_id)[-50:]}-{timestamp_ms}"


class StepFunctionsMotionHandler:
    def __init__(self, client, state_machine_arn: str):
        self.client = client
        self.state_machine_arn = state_machine_arn

    def handle(self, event: MotionEvent) -> None:
        name = run_name(event.device_id, event.timestamp_ms)
        payload = {
            "account_id": event.account_id,
            "device_id": event.device_id,
            "timestamp_ms": event.timestamp_ms,
            "request_id": event.request_id,
        }
        try:
            self.client.start_execution(
                stateMachineArn=self.state_machine_arn, name=name, input=json.dumps(payload)
            )
        except ClientError as e:
            if e.response["Error"]["Code"] != "ExecutionAlreadyExists":
                raise
            log_event("workflow_already_started", run=name)
            return
        log_event("workflow_started", run=name, account_id=event.account_id)


def default_motion_handler() -> MotionHandler:
    arn = os.environ.get("STATE_MACHINE_ARN")
    if not arn:
        return LoggingMotionHandler()
    return StepFunctionsMotionHandler(boto3.client("stepfunctions"), arn)
