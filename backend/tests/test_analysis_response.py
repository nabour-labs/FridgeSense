"""fridge-change-analysis: answer validation, Bedrock errors and cost."""

import copy
import json
import logging

import boto3
import pytest
from botocore.stub import Stubber

from fridgesense.analysis import (
    BedrockRejected,
    BedrockRetryable,
    NovaAnalyzer,
    cost_usd,
    parse_response,
)
from tests.conftest import jpeg, load_fixture

STILLS = [jpeg(0.5)] * 4


@pytest.fixture
def bedrock():
    client = boto3.client("bedrock-runtime", region_name="us-east-1")
    with Stubber(client) as stub:
        yield client, stub


def tool_response(tool_input, usage=(1180, 96)):
    resp = copy.deepcopy(load_fixture("nova/converse_tool_use.json"))
    resp["output"]["message"]["content"][0]["toolUse"]["input"] = tool_input
    resp["usage"] = {
        "inputTokens": usage[0],
        "outputTokens": usage[1],
        "totalTokens": sum(usage),
    }
    return resp


def as_tuples(changes):
    return [(c.item, c.category, c.quantity, c.confidence) for c in changes]


# Valid answer
def test_valid_answer():
    changes = parse_response(load_fixture("nova/converse_tool_use.json"))
    assert as_tuples(changes.added) == [("milk", "dairy", 1, 0.92)]
    assert as_tuples(changes.removed) == [("eggs", "dairy", 2, 0.71)]


# Text before the tool call
def test_text_before_the_tool_call():
    changes = parse_response(load_fixture("nova/converse_text_then_tool.json"))
    assert as_tuples(changes.added) == [("milk", "dairy", 1, 0.92)]


# Values out of range
def test_values_out_of_range():
    resp = tool_response(
        {
            "added": [
                {"item": "cookies", "category": "snacks & treats", "quantity": 0, "confidence": 1.4}
            ],
            "removed": [{"item": "jam", "category": "condiment", "quantity": -2, "confidence": -1}],
        }
    )
    changes = parse_response(resp)
    assert as_tuples(changes.added) == [("cookies", "other", 1, 1.0)]
    assert as_tuples(changes.removed) == [("jam", "condiment", 1, 0.0)]


@pytest.mark.parametrize(
    "tool_input",
    [
        {"added": []},
        {"removed": []},
        {
            "added": [{"item": "  ", "category": "dairy", "quantity": 1, "confidence": 0.9}],
            "removed": [],
        },
        {"added": "milk", "removed": []},
    ],
    ids=["no-removed", "no-added", "empty-item", "added-not-list"],
)
def test_incomplete_answers_are_invalid(tool_input):
    assert parse_response(tool_response(tool_input)) is None


def test_end_turn_is_invalid():
    assert parse_response(load_fixture("nova/converse_end_turn.json")) is None


# Invalid answer retried once
def test_invalid_answer_retried_once(bedrock):
    client, stub = bedrock
    stub.add_response("converse", load_fixture("nova/converse_end_turn.json"))
    stub.add_response("converse", load_fixture("nova/converse_tool_use.json"))
    result = NovaAnalyzer(client).analyze(STILLS, [])
    stub.assert_no_pending_responses()
    assert as_tuples(result.changes.added) == [("milk", "dairy", 1, 0.92)]
    assert len(result.usage) == 2


# Invalid answer twice
def test_invalid_answer_twice(bedrock):
    client, stub = bedrock
    stub.add_response("converse", load_fixture("nova/converse_end_turn.json"))
    stub.add_response("converse", tool_response({"added": []}))
    result = NovaAnalyzer(client).analyze(STILLS, [])
    stub.assert_no_pending_responses()
    assert result.changes is None


# Throttled once (the task raises BedrockRetryable; the workflow retries the task)
@pytest.mark.parametrize(
    "code",
    [
        "ThrottlingException",
        "ModelTimeoutException",
        "ServiceUnavailableException",
        "InternalServerException",
    ],
)
def test_transient_errors_are_retryable(bedrock, code):
    client, stub = bedrock
    stub.add_client_error("converse", code, http_status_code=503)
    with pytest.raises(BedrockRetryable):
        NovaAnalyzer(client).analyze(STILLS, [])


# Request rejected
@pytest.mark.parametrize("code", ["ValidationException", "AccessDeniedException"])
def test_request_rejected(bedrock, code):
    client, stub = bedrock
    stub.add_client_error("converse", code, http_status_code=400)
    with pytest.raises(BedrockRejected):
        NovaAnalyzer(client).analyze(STILLS, [])
    stub.assert_no_pending_responses()  # exactly one call, no retry


# Cost of one analysis
def test_cost_of_one_analysis(bedrock, caplog):
    caplog.set_level(logging.INFO)
    assert cost_usd(1180, 96, 0.00033, 0.00275) == 0.000653
    assert cost_usd(1000, 50, 0.00033, 0.00275) == 0.000468  # 0.0004675 rounds half up
    client, stub = bedrock
    stub.add_response("converse", load_fixture("nova/converse_tool_use.json"))
    result = NovaAnalyzer(client).analyze(STILLS, [], context={"door_sk": "DOOR#x"})
    assert result.usd == 0.000653
    [line] = [json.loads(r.getMessage()) for r in caplog.records if "nova_cost" in r.getMessage()]
    assert line == {
        "event": "nova_cost",
        "model_id": "us.amazon.nova-2-lite-v1:0",
        "input_tokens": 1180,
        "output_tokens": 96,
        "usd": 0.000653,
        "door_sk": "DOOR#x",
    }


# Cost of a retried analysis
def test_cost_of_a_retried_analysis(bedrock, caplog):
    caplog.set_level(logging.INFO)
    client, stub = bedrock
    stub.add_response("converse", load_fixture("nova/converse_end_turn.json"))  # 1000 in, 50 out
    stub.add_response("converse", load_fixture("nova/converse_tool_use.json"))  # 1180 in, 96 out
    result = NovaAnalyzer(client).analyze(STILLS, [])
    lines = [r for r in caplog.records if "nova_cost" in r.getMessage()]
    assert len(lines) == 2
    assert result.usd == round(cost_usd(1000, 50, 0.00033, 0.00275) + 0.000653, 6)


def test_prices_and_model_from_environment(monkeypatch):
    monkeypatch.setenv("NOVA_MODEL_ID", "amazon.nova-lite-v1:0")
    monkeypatch.setenv("NOVA_PRICE_IN", "0.00006")
    monkeypatch.setenv("NOVA_PRICE_OUT", "0.00024")
    analyzer = NovaAnalyzer.from_env(boto3.client("bedrock-runtime", region_name="us-east-1"))
    assert (analyzer.model_id, analyzer.price_in, analyzer.price_out) == (
        "amazon.nova-lite-v1:0",
        0.00006,
        0.00024,
    )
