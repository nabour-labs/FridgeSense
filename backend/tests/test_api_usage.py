"""llm-usage-tracking: reading one day's LLM usage totals over HTTP."""

import pytest

from fridgesense.handlers import api
from fridgesense.store import load_app_config
from fridgesense.table import FridgeTable, account_pk
from tests.api_helpers import ACCOUNT, NOW, call, configure, link_account, sign_in

ZERO = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "usd": 0}


@pytest.fixture
def tokens(aws, monkeypatch):
    monkeypatch.setattr(api, "now", lambda: NOW)
    link_account()
    configure(demo_passcode="look-only", user_passcode="come-in")
    load_app_config(refresh=True)
    return {"owner": sign_in(), "viewer": sign_in("look-only"), "user": sign_in("come-in")}


@pytest.fixture
def owner(tokens):
    return tokens["owner"]


def store(account_id: str, day: str, **amounts):
    FridgeTable().add_many(account_pk(account_id), f"USAGE#{day}", amounts)


def usage(token, query):
    return call("GET", "/api/debug/usage", token=token, query=query)


# Day with calls
def test_day_with_calls(owner):
    store(
        ACCOUNT,
        "2026-10-20",
        calls=2,
        input_tokens=2380,
        cache_read_tokens=2000,
        cache_write_tokens=0,
        output_tokens=136,
        usd=0.001324,
        analysis_calls=1,
        analysis_usd=0.000818,
    )
    assert usage(owner, {"day": "2026-10-20"}) == (
        200,
        {
            "day": "2026-10-20",
            "calls": 2,
            "input_tokens": 4380,
            "output_tokens": 136,
            "total_tokens": 4516,
            "usd": 0.001324,
        },
    )


# Day without calls
def test_day_without_calls(owner):
    assert usage(owner, {"day": "2026-10-19"}) == (200, {"day": "2026-10-19", **ZERO})


# Another account's totals are not read
def test_other_account_not_read(owner):
    store("acc-2", "2026-10-20", calls=1, input_tokens=100, output_tokens=10, usd=0.0001)
    assert usage(owner, {"day": "2026-10-20"}) == (200, {"day": "2026-10-20", **ZERO})


# Bad day
@pytest.mark.parametrize("query", [{}, {"day": "yesterday"}, {"day": "2026-13-01"}])
def test_bad_day(owner, query):
    assert usage(owner, query)[0] == 400


# Not the owner
def test_viewer_refused(tokens):
    assert usage(tokens["viewer"], {"day": "2026-10-20"}) == (403, {"error": "read-only"})


def test_user_refused(tokens):
    assert usage(tokens["user"], {"day": "2026-10-20"}) == (403, {"error": "admin only"})


def test_needs_a_token(tokens):
    assert usage(None, {"day": "2026-10-20"})[0] == 401
