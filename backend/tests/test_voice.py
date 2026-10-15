"""inventory-api: answers spoken with Amazon Polly (botocore Stubber, no live calls)."""

import io
import json
import logging

import boto3
import pytest
from botocore.response import StreamingBody
from botocore.stub import Stubber

from fridgesense import voice

MP3 = b"ID3fake"


@pytest.fixture
def polly():
    client = boto3.client(
        "polly",
        region_name="us-east-1",
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
    )
    with Stubber(client) as stub:
        yield client, stub


# Audio returned
def test_audio_returned(polly):
    client, stub = polly
    stub.add_response(
        "synthesize_speech",
        {"AudioStream": StreamingBody(io.BytesIO(MP3), len(MP3)), "ContentType": "audio/mpeg"},
        {
            "Text": "You're out of butter.",
            "Engine": "neural",
            "VoiceId": "Joanna",
            "OutputFormat": "mp3",
            "SampleRate": "24000",
        },
    )
    assert voice.speak("You're out of butter.", client) == "SUQzZmFrZQ=="
    stub.assert_no_pending_responses()


def test_voice_setting(polly):
    client, stub = polly
    stub.add_response(
        "synthesize_speech",
        {"AudioStream": StreamingBody(io.BytesIO(MP3), len(MP3))},
        {
            "Text": "Hi.",
            "Engine": "neural",
            "VoiceId": "Matthew",
            "OutputFormat": "mp3",
            "SampleRate": "24000",
        },
    )
    assert voice.speak("Hi.", client, voice="Matthew") == "SUQzZmFrZQ=="


# Polly fails
@pytest.mark.parametrize("code", ["ServiceFailureException", "AccessDeniedException"])
def test_polly_fails(polly, caplog, code):
    caplog.set_level(logging.INFO, logger="fridgesense")
    client, stub = polly
    stub.add_client_error("synthesize_speech", service_error_code=code, http_status_code=500)
    assert voice.speak("You're out of butter.", client) is None
    logged = [json.loads(r.getMessage()) for r in caplog.records]
    assert any(e["event"] == "voice_failed" and e["error_code"] == code for e in logged)
