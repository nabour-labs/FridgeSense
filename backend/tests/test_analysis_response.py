"""fridge-change-analysis: answer validation, Bedrock errors and cost."""

import copy
import json
import logging

import boto3
import pytest
from botocore.exceptions import ConnectTimeoutError, ReadTimeoutError
from botocore.stub import Stubber

from fridgesense.analysis import (
    BedrockRejected,
    BedrockRetryable,
    NovaAnalyzer,
    cost_usd,
    parse_response,
)
from fridgesense.usage import Prices, Tokens
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


def cached_response(**usage):
    """The valid tool answer with these Converse usage fields."""
    resp = copy.deepcopy(load_fixture("nova/converse_tool_use.json"))
    resp["usage"] = {**usage, "totalTokens": sum(usage.values())}
    return resp


def nova_cost_lines(caplog):
    return [json.loads(r.getMessage()) for r in caplog.records if "nova_cost" in r.getMessage()]


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


# Read timeout is retryable
@pytest.mark.parametrize(
    "error, code",
    [
        (ReadTimeoutError(endpoint_url="https://bedrock"), "ReadTimeout"),
        (ConnectTimeoutError(endpoint_url="https://bedrock"), "ConnectTimeout"),
    ],
)
def test_client_timeout_is_retryable(error, code, caplog):
    class TimingOut:
        def converse(self, **_):
            raise error

    caplog.set_level(logging.INFO)
    with pytest.raises(BedrockRetryable) as raised:
        NovaAnalyzer(TimingOut()).analyze(STILLS, [])
    assert str(raised.value) == code
    [line] = [json.loads(r.getMessage()) for r in caplog.records if "nova_error" in r.getMessage()]
    assert line["error_code"] == code  # "code" is redacted (OAuth codes)


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
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
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


# No cache fields in usage
def test_no_cache_fields_in_usage(bedrock, caplog):
    caplog.set_level(logging.INFO)
    client, stub = bedrock
    stub.add_response("converse", cached_response(inputTokens=1180, outputTokens=96))
    result = NovaAnalyzer(client).analyze(STILLS, [])
    [line] = nova_cost_lines(caplog)
    assert (line["cache_read_tokens"], line["cache_write_tokens"], line["usd"]) == (0, 0, 0.000653)
    assert result.usd == 0.000653


# Cache read priced at the cache-read rate
def test_cache_read_priced_at_the_cache_read_rate(bedrock, caplog):
    caplog.set_level(logging.INFO)
    client, stub = bedrock
    stub.add_response(
        "converse",
        cached_response(
            inputTokens=1180, cacheReadInputTokens=2000, cacheWriteInputTokens=0, outputTokens=96
        ),
    )
    result = NovaAnalyzer(client).analyze(STILLS, [])
    [line] = nova_cost_lines(caplog)
    assert line["input_tokens"] == 1180
    assert line["cache_read_tokens"] == 2000
    assert line["cache_write_tokens"] == 0
    assert line["usd"] == 0.000818
    assert result.usd == 0.000818


# Cache write priced at the cache-write rate
def test_cache_write_priced_at_the_cache_write_rate(bedrock, caplog):
    caplog.set_level(logging.INFO)
    client, stub = bedrock
    stub.add_response(
        "converse",
        cached_response(
            inputTokens=200, cacheReadInputTokens=0, cacheWriteInputTokens=1500, outputTokens=96
        ),
    )
    NovaAnalyzer(client).analyze(STILLS, [])
    [line] = nova_cost_lines(caplog)
    assert (line["cache_write_tokens"], line["usd"]) == (1500, 0.00033)


# Cache prices from configuration
def test_cache_prices_from_configuration(monkeypatch):
    monkeypatch.setenv("NOVA_PRICE_CACHE_READ", "0.0001")
    monkeypatch.setenv("NOVA_PRICE_CACHE_WRITE", "0.0005")
    analyzer = NovaAnalyzer.from_env(boto3.client("bedrock-runtime", region_name="us-east-1"))
    assert (analyzer.prices.cache_read, analyzer.prices.cache_write) == (0.0001, 0.0005)


# Retried analysis (llm-usage-tracking): one usage record per response
def test_on_usage_called_once_per_response(bedrock):
    client, stub = bedrock
    stub.add_response("converse", load_fixture("nova/converse_end_turn.json"))  # 1000 in, 50 out
    stub.add_response("converse", load_fixture("nova/converse_tool_use.json"))  # 1180 in, 96 out
    calls = []
    NovaAnalyzer(client).analyze(STILLS, [], on_usage=lambda t, usd: calls.append((t, usd)))
    assert calls == [
        (Tokens(input=1000, output=50), cost_usd(1000, 50, 0.00033, 0.00275)),
        (Tokens(input=1180, output=96), 0.000653),
    ]


# Call that raises an error (llm-usage-tracking): nothing recorded
def test_on_usage_not_called_when_the_call_fails(bedrock):
    client, stub = bedrock
    stub.add_client_error("converse", "ThrottlingException", http_status_code=429)
    calls = []
    with pytest.raises(BedrockRetryable):
        NovaAnalyzer(client).analyze(STILLS, [], on_usage=lambda t, usd: calls.append(t))
    assert calls == []


def test_analyzer_prices_default(bedrock):
    client, _ = bedrock
    assert NovaAnalyzer(client).prices == Prices()
