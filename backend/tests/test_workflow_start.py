"""door-event-detection: One workflow run per motion event."""

import json

import boto3
import pytest
from botocore.stub import Stubber

from fridgesense.webhook import LoggingMotionHandler, MotionEvent
from fridgesense.workflow import StepFunctionsMotionHandler, default_motion_handler, run_name

ARN = "arn:aws:states:us-east-1:123456789012:stateMachine:fridgesense-door-events"
EVENT = MotionEvent(
    account_id="ava1.ring.account.A1",
    device_id="ava1.ring.device.D1",
    timestamp_ms=1786715596787,
    sub_type="motion",
    request_id="R1",
)
EXPECTED_INPUT = {
    "account_id": "ava1.ring.account.A1",
    "device_id": "ava1.ring.device.D1",
    "timestamp_ms": 1786715596787,
    "request_id": "R1",
}


@pytest.fixture
def sfn():
    client = boto3.client("stepfunctions", region_name="us-east-1")
    with Stubber(client) as stub:
        yield client, stub


def test_run_name_is_safe_and_contains_timestamp():
    name = run_name("ava1.ring.device.D1", 1786715596787)
    assert name == "ava1-ring-device-D1-1786715596787"
    long_name = run_name("x" * 200, 1786715596787)
    assert len(long_name) <= 80 and long_name.endswith("-1786715596787")


# Motion event starts a run
def test_motion_event_starts_a_run(sfn):
    client, stub = sfn
    stub.add_response(
        "start_execution",
        {"executionArn": f"{ARN}:x", "startDate": "2026-08-14T13:53:17Z"},
        {
            "stateMachineArn": ARN,
            "name": "ava1-ring-device-D1-1786715596787",
            "input": json.dumps(EXPECTED_INPUT),
        },
    )
    StepFunctionsMotionHandler(client, ARN).handle(EVENT)
    stub.assert_no_pending_responses()


# Same event handed over twice
def test_same_event_handed_over_twice(sfn):
    client, stub = sfn
    stub.add_client_error("start_execution", "ExecutionAlreadyExists", http_status_code=400)
    StepFunctionsMotionHandler(client, ARN).handle(EVENT)  # does not raise
    stub.assert_no_pending_responses()


def test_other_start_errors_propagate(sfn):
    client, stub = sfn
    stub.add_client_error("start_execution", "AccessDeniedException", http_status_code=400)
    with pytest.raises(Exception, match="AccessDenied"):
        StepFunctionsMotionHandler(client, ARN).handle(EVENT)


def test_handler_chosen_from_environment(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.delenv("STATE_MACHINE_ARN", raising=False)
    assert isinstance(default_motion_handler(), LoggingMotionHandler)
    monkeypatch.setenv("STATE_MACHINE_ARN", ARN)
    handler = default_motion_handler()
    assert isinstance(handler, StepFunctionsMotionHandler)
    assert handler.state_machine_arn == ARN
