"""The BlurClip workflow step: blur faces in a door opening's raw clip, then publish it.

Fail closed: the door event only ever links a blurred clip. On any error the raw clip and any
partial output are deleted, `clip_not_stored` is logged, and the error is re-raised so the
workflow's catch (DropRawClip) sees it too.
"""

import json
import logging
import os
import tempfile
from decimal import Decimal
from pathlib import Path
from time import monotonic

import boto3
from botocore.exceptions import ClientError

from clipblur.blur import blur_clip, centerface

logger = logging.getLogger("clipblur")
logger.setLevel(logging.INFO)

TMP_DIR = Path(tempfile.gettempdir())
ARM_GB_SECOND_USD = 0.0000133334
make_detector = centerface


def log_event(event: str, level: int = logging.INFO, **fields) -> None:
    logger.log(level, json.dumps({"event": event, **fields}, default=str))


def publish(table, state: dict, clip_key: str) -> bool:
    """Link the blurred clip on the door event; False if the event no longer exists."""
    try:
        table.update_item(
            Key={"pk": f"ACCOUNT#{state['account_id']}", "sk": state["door_sk"]},
            UpdateExpression="SET clip_key = :k, clip_span = :s, clip_blurred = :b",
            ConditionExpression="attribute_exists(pk)",
            ExpressionAttributeValues={
                ":k": clip_key,
                ":s": [Decimal(str(x)) for x in state["clip"]["clip_span"]],
                ":b": True,
            },
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise
    return True


def handler(event: dict, context) -> dict:
    started = monotonic()
    bucket = os.environ["STILLS_BUCKET"]
    raw_key = event["clip"]["raw_key"]
    clip_key = raw_key.removesuffix("clip-raw.mp4") + "clip.mp4"
    device_id = event["device_id"]
    s3 = boto3.client("s3")
    table = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])
    src = TMP_DIR / "clip-raw.mp4"
    dst = TMP_DIR / "clip.mp4"

    def drop(*keys: str) -> None:
        for key in keys:
            s3.delete_object(Bucket=bucket, Key=key)

    try:
        s3.download_file(bucket, raw_key, str(src))
        stats = blur_clip(src, dst, make_detector_for(src))
        s3.upload_file(str(dst), bucket, clip_key, ExtraArgs={"ContentType": "video/mp4"})
        if not publish(table, event, clip_key):
            log_event("clip_not_stored", device_id=device_id, reason="event_deleted")
            drop(clip_key, raw_key)
            return {**event, "clip_blurred": False}
        drop(raw_key)
    except Exception as e:
        log_event(
            "clip_not_stored",
            logging.WARNING,
            device_id=device_id,
            reason="blur_failed",
            error=type(e).__name__,
        )
        try:
            drop(clip_key, raw_key)
        except Exception:  # the 1-day lifecycle rule removes the raw clip anyway
            log_event("clip_cleanup_failed", logging.WARNING, device_id=device_id)
        raise
    finally:
        src.unlink(missing_ok=True)
        dst.unlink(missing_ok=True)

    billed_ms = round((monotonic() - started) * 1000)
    memory_mb = context.memory_limit_in_mb
    log_event(
        "clip_blurred",
        device_id=device_id,
        frames=stats.frames,
        frames_with_faces=stats.frames_with_faces,
        duration_ms=billed_ms,
    )
    log_event(
        "clip_blur_cost",
        device_id=device_id,
        billed_ms=billed_ms,
        memory_mb=memory_mb,
        usd=round(billed_ms / 1000 * memory_mb / 1024 * ARM_GB_SECOND_USD, 6),
    )
    return {**event, "clip_blurred": True}


def make_detector_for(src: Path):
    """The face detector sized for this clip's frames."""
    import av

    with av.open(str(src)) as c:
        ctx = c.streams.video[0].codec_context
        return make_detector(ctx.width, ctx.height)
