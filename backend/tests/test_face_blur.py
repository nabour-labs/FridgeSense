"""face-blur-setting: the stored on/off setting and the pass-through blurrer."""

import json
import logging

from botocore.stub import Stubber

from fridgesense import face_blur
from fridgesense.faces import NoBlur
from fridgesense.table import FridgeTable

A, B = "ava1.ring.account.A1", "ava1.ring.account.B2"


def logged(caplog, event: str) -> list[dict]:
    return [json.loads(r.getMessage()) for r in caplog.records if f'"{event}"' in r.getMessage()]


# Default is on
def test_default_is_on(aws):
    assert face_blur.load(FridgeTable(), A) is True


# Saved off
def test_saved_off(aws):
    table = FridgeTable()
    face_blur.save(table, A, False, now_ms=1786715596000)
    assert face_blur.load(table, A) is False
    face_blur.save(table, A, True, now_ms=1786715597000)
    assert face_blur.load(table, A) is True


# Kept per account
def test_kept_per_account(aws):
    table = FridgeTable()
    face_blur.save(table, A, False, now_ms=1786715596000)
    assert face_blur.load(table, B) is True


# Unreadable setting counts as on
def test_unreadable_setting_counts_as_on(aws, caplog):
    caplog.set_level(logging.INFO)
    table = FridgeTable()
    face_blur.save(table, A, False, now_ms=1786715596000)
    with Stubber(table.client) as stub:
        stub.add_client_error(
            "get_item", service_error_code="ProvisionedThroughputExceededException"
        )
        assert face_blur.load(table, A) is True
    [line] = logged(caplog, "face_blur_setting_failed")
    assert line["error"] == "ProvisionedThroughputExceededException"
    assert line["account_id"] == A


def test_no_blur_returns_its_input():
    assert NoBlur().blur(b"\xff\xd8\xffjpeg", {"still": 1}) == b"\xff\xd8\xffjpeg"


def test_blurrer_follows_the_setting(aws):
    table = FridgeTable()
    real = object()
    assert face_blur.blurrer(table, A, lambda: real) is real
    face_blur.save(table, A, False, now_ms=1786715596000)
    assert isinstance(face_blur.blurrer(table, A, lambda: real), NoBlur)
    assert face_blur.blurrer_for(False, lambda: real).__class__ is NoBlur
    assert face_blur.blurrer_for(True, lambda: real) is real
