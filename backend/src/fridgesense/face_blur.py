"""The owner's face-blur setting: on unless saved off, and on whenever it can't be read."""

import logging
from collections.abc import Callable

from botocore.exceptions import BotoCoreError, ClientError

from fridgesense.door_events import iso_utc
from fridgesense.faces import NoBlur
from fridgesense.logs import log_event
from fridgesense.table import FridgeTable, account_pk

SETTING_SK = "CONFIG#face_blur"


def load(table: FridgeTable, account_id: str) -> bool:
    """True unless the account saved the setting off; a failed read counts as on."""
    try:
        saved = table.get(account_pk(account_id), SETTING_SK)
    except ClientError as e:
        error = e.response["Error"]["Code"]
    except BotoCoreError as e:
        error = type(e).__name__
    else:
        return saved is None or saved.get("enabled") is not False
    log_event("face_blur_setting_failed", logging.WARNING, account_id=account_id, error=error)
    return True


def save(table: FridgeTable, account_id: str, enabled: bool, now_ms: int) -> None:
    table.put(
        {
            "pk": account_pk(account_id),
            "sk": SETTING_SK,
            "enabled": enabled,
            "updated_at": iso_utc(now_ms),
        }
    )


def blurrer_for(enabled: bool, make_real: Callable):
    """The real blurrer while blurring is on, else a pass-through."""
    return make_real() if enabled else NoBlur()


def blurrer(table: FridgeTable, account_id: str, make_real: Callable):
    return blurrer_for(load(table, account_id), make_real)
