"""Pipeline AWS clients: Bedrock calls are bounded so two Nova attempts fit the task timeout."""

from fridgesense.handlers import pipeline


# Client sends one attempt
def test_bedrock_client_sends_one_attempt_with_bounded_timeouts(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    config = pipeline.bedrock_client().meta.config
    assert config.retries["total_max_attempts"] == 1
    assert config.read_timeout == 30
    assert config.connect_timeout == 5
