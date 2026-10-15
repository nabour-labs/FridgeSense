"""fridge-change-analysis: the analyze and mark_failed workflow tasks."""

import boto3
import pytest
from botocore.stub import ANY, Stubber

from fridgesense import analysis_config
from fridgesense.analysis import BedrockRetryable, NovaAnalyzer
from fridgesense.inventory import analyze_task, mark_failed_task
from fridgesense.table import FridgeTable, account_pk
from tests.conftest import BUCKET, jpeg, load_fixture

ACCOUNT = "ava1.ring.account.A1"
DOOR_SK = "DOOR#2026-08-14T13:53:16.000Z#ava1.ring.device.D1"
KEYS = [f"accounts/{ACCOUNT}/devices/D1/events/1/still-{n}.jpg" for n in range(1, 5)]
STATE = {"account_id": ACCOUNT, "door_sk": DOOR_SK, "still_keys": KEYS, "outcome": "door_open"}


@pytest.fixture
def setup(aws):
    s3 = boto3.client("s3")
    for k in KEYS:
        s3.put_object(Bucket=BUCKET, Key=k, Body=jpeg(0.8))
    table = FridgeTable()
    table.put({"pk": account_pk(ACCOUNT), "sk": DOOR_SK, "status": "analyzing"})
    table.put({"pk": account_pk(ACCOUNT), "sk": "ITEM#milk", "name": "Milk", "quantity": 1})
    table.put({"pk": account_pk(ACCOUNT), "sk": "ITEM#jam", "name": "jam", "quantity": 0})
    client = boto3.client("bedrock-runtime", region_name="us-east-1")
    with Stubber(client) as stub:
        yield table, client, stub


def run(setup):
    table, client, _ = setup
    return analyze_task(NovaAnalyzer(client), boto3.client("s3"), table, BUCKET, STATE)


def door(table):
    return table.get(account_pk(ACCOUNT), DOOR_SK)


def test_analyze_task_returns_changes_and_records_cost(setup):
    table, _, stub = setup
    stub.add_response(
        "converse",
        load_fixture("nova/converse_tool_use.json"),
        {
            "modelId": ANY,
            "messages": ANY,
            "inferenceConfig": ANY,
            "toolConfig": ANY,
        },
    )
    out = run(setup)
    assert out["analysis"] == {
        "added": [{"item": "milk", "category": "dairy", "quantity": 1, "confidence": 0.92}],
        "removed": [{"item": "eggs", "category": "dairy", "quantity": 2, "confidence": 0.71}],
    }
    assert door(table)["nova_usd"] == 0.000653


def test_inventory_names_in_stock_are_sent(setup):
    _, client, stub = setup
    seen = {}

    def capture(params, **kwargs):
        seen.update(params)

    client.meta.events.register("provide-client-params.bedrock-runtime.Converse", capture)
    stub.add_response("converse", load_fixture("nova/converse_tool_use.json"))
    run(setup)
    final_text = seen["messages"][0]["content"][-1]["text"]
    assert "[milk]" in final_text  # jam has quantity 0


# Throttled once: the task raises so the workflow can retry it; then it succeeds
def test_throttled_once(setup):
    table, _, stub = setup
    stub.add_client_error("converse", "ThrottlingException", http_status_code=429)
    with pytest.raises(BedrockRetryable):
        run(setup)
    assert door(table)["status"] == "analyzing"
    stub.add_response("converse", load_fixture("nova/converse_tool_use.json"))
    assert run(setup)["analysis"]["added"][0]["item"] == "milk"


# Request rejected
@pytest.mark.parametrize("code", ["ValidationException", "AccessDeniedException"])
def test_request_rejected_marks_failed(setup, code):
    table, _, stub = setup
    stub.add_client_error("converse", code, http_status_code=400)
    out = run(setup)
    assert out["outcome"] == "analysis_failed"
    assert door(table)["status"] == "analysis_failed"


# Invalid answer twice
def test_invalid_answer_twice_marks_failed(setup):
    table, _, stub = setup
    stub.add_response("converse", load_fixture("nova/converse_end_turn.json"))
    stub.add_response("converse", load_fixture("nova/converse_end_turn.json"))
    out = run(setup)
    assert out["outcome"] == "analysis_failed"
    assert door(table)["status"] == "analysis_failed"
    assert door(table)["nova_usd"] == pytest.approx(2 * 0.000468, abs=1e-6)


# Cost of a retried analysis
def test_cost_of_retried_analysis_summed_on_door_event(setup):
    table, _, stub = setup
    stub.add_response("converse", load_fixture("nova/converse_end_turn.json"))
    stub.add_response("converse", load_fixture("nova/converse_tool_use.json"))
    run(setup)
    assert door(table)["nova_usd"] == round(0.000468 + 0.000653, 6)


def test_mark_failed_task(setup):
    table, _, _ = setup
    out = mark_failed_task(table, {**STATE, "error": {"Error": "BedrockRetryable"}})
    assert out["outcome"] == "analysis_failed"
    assert door(table)["status"] == "analysis_failed"


def captured_request(setup) -> dict:
    _, client, stub = setup
    seen = {}

    def capture(params, **kwargs):
        seen.update(params)

    client.meta.events.register("provide-client-params.bedrock-runtime.Converse", capture)
    stub.add_response("converse", load_fixture("nova/converse_tool_use.json"))
    run(setup)
    client.meta.events.unregister("provide-client-params.bedrock-runtime.Converse", capture)
    return seen


def texts(request: dict) -> list[str]:
    return [c["text"] for c in request["messages"][0]["content"] if "text" in c]


# Saved config reaches the request
def test_saved_config_reaches_the_request(setup):
    table = setup[0]
    milk_bag = jpeg(0.3)
    analysis_config.add_reference(table, ACCOUNT, "milk bag", milk_bag, now_ms=1)
    analysis_config.save_instructions(table, ACCOUNT, "Count yogurt cups individually.", now_ms=1)
    request = captured_request(setup)
    content = request["messages"][0]["content"]
    assert texts(request)[1] == "Reference 1: milk bag"
    assert content[2]["image"]["source"]["bytes"] == milk_bag
    assert "Owner's instructions: Count yogurt cups individually." in texts(request)[-1]


# Config changed between openings
def test_deleted_reference_absent_next_time(setup):
    table = setup[0]
    milk = analysis_config.add_reference(table, ACCOUNT, "milk bag", jpeg(0.3), now_ms=1)
    analysis_config.add_reference(table, ACCOUNT, "soda can", jpeg(0.4), now_ms=2)
    assert "Reference 1: milk bag" in texts(captured_request(setup))
    analysis_config.delete_reference(table, ACCOUNT, milk.sk)
    after = texts(captured_request(setup))
    assert "Reference 1: soda can" in after
    assert not any("milk bag" in t for t in after)


# No config
def test_no_config_sends_no_references(setup):
    request = captured_request(setup)
    assert texts(request)[0] == "Image 1 of 4"
    assert "Owner's instructions" not in texts(request)[-1]
