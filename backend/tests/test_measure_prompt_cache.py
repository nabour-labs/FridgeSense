"""The prompt caching measurement script's pure helpers (the script itself calls Bedrock)."""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "scripts" / "measure_prompt_cache.py"


@pytest.fixture(scope="module")
def script():
    spec = importlib.util.spec_from_file_location("measure_prompt_cache", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_summarize_reads_every_count(script):
    row = script.summarize(
        {
            "inputTokens": 300,
            "cacheReadInputTokens": 1200,
            "cacheWriteInputTokens": 5,
            "outputTokens": 30,
        },
        {"latencyMs": 640},
    )
    assert row == {
        "input": 300,
        "cache_read": 1200,
        "cache_write": 5,
        "output": 30,
        "latency_ms": 640,
    }


def test_summarize_counts_absent_fields_as_zero(script):
    assert script.summarize({}, None) == {
        "input": 0,
        "cache_read": 0,
        "cache_write": 0,
        "output": 0,
        "latency_ms": 0,
    }
