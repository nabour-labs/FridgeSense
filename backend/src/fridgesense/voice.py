"""Spoken answers: text to MP3 with Amazon Polly, returned base64 for the JSON response."""

import base64
import logging
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError

from fridgesense.logs import log_event

DEFAULT_VOICE = "Joanna"


def speak(text: str, client: Any, voice: str = DEFAULT_VOICE) -> str | None:
    """`text` as base64 MP3 in a neural voice, or None when Polly fails (the app then speaks
    the text with the browser's own voice)."""
    try:
        resp = client.synthesize_speech(
            Text=text, Engine="neural", VoiceId=voice, OutputFormat="mp3", SampleRate="24000"
        )
        audio = resp["AudioStream"].read()
    except ClientError as e:
        log_event("voice_failed", logging.WARNING, error_code=e.response["Error"]["Code"])
        return None
    except BotoCoreError as e:
        log_event("voice_failed", logging.WARNING, error_code=type(e).__name__)
        return None
    return base64.b64encode(audio).decode()
