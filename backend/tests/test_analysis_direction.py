"""fridge-change-analysis: Direction decided from hand evidence."""

import copy
import json
import logging

import boto3
from botocore.stub import Stubber

from fridgesense.analysis import NovaAnalyzer, parse_response
from tests.conftest import jpeg, load_fixture


def respond(*items):
    resp = copy.deepcopy(load_fixture("nova/converse_tool_use.json"))
    resp["output"]["message"]["content"][0]["toolUse"]["input"] = {
        "observations": "Hands moved things.",
        "items": [
            {
                "item": name,
                "category": "other",
                "quantity": 1,
                "confidence": conf,
                "going_in": going_in,
                "coming_out": coming_out,
            }
            for name, going_in, coming_out, conf in items
        ],
    }
    return resp


def names(changes):
    return [c.item for c in changes]


# Seen going in
def test_seen_going_in():
    changes = parse_response(respond(("milk", True, False, 0.9)))
    assert names(changes.added) == ["milk"] and changes.removed == []


# Seen coming out
def test_seen_coming_out():
    changes = parse_response(respond(("eggs", False, True, 0.9)))
    assert names(changes.removed) == ["eggs"] and changes.added == []


# Item only seen on a shelf
def test_item_only_seen_on_a_shelf():
    changes = parse_response(respond(("bread", False, False, 0.9)))
    assert changes.added == [] and changes.removed == []
    assert [(d.item, d.reason) for d in changes.dropped] == [("bread", "no_hand_evidence")]


# Taken out and put back
def test_taken_out_and_put_back():
    changes = parse_response(respond(("soda can", True, True, 0.9)))
    assert changes.added == [] and changes.removed == []
    assert [(d.item, d.reason) for d in changes.dropped] == [("soda can", "in_and_out")]


def test_drops_logged_with_the_door_event(caplog):
    client = boto3.client("bedrock-runtime", region_name="us-east-1")
    caplog.set_level(logging.INFO)
    with Stubber(client) as stub:
        stub.add_response("converse", load_fixture("nova/converse_items_dropped.json"))
        NovaAnalyzer(client).analyze([jpeg(0.5)] * 4, [], {"door_sk": "DOOR#x"})
    lines = [
        json.loads(r.getMessage()) for r in caplog.records if "change_dropped" in r.getMessage()
    ]
    assert [(x["item"], x["reason"], x["door_sk"]) for x in lines] == [
        ("milk", "no_hand_evidence", "DOOR#x"),
        ("soda can", "in_and_out", "DOOR#x"),
    ]


# Every item dropped
def test_every_item_dropped_is_not_retried():
    client = boto3.client("bedrock-runtime", region_name="us-east-1")
    with Stubber(client) as stub:
        stub.add_response("converse", load_fixture("nova/converse_items_dropped.json"))
        result = NovaAnalyzer(client).analyze([jpeg(0.5)] * 4, [])
        stub.assert_no_pending_responses()
    assert result.changes.added == [] and result.changes.removed == []
    assert len(result.changes.dropped) == 2


# Low confidence with evidence
def test_low_confidence_with_evidence_is_kept():
    changes = parse_response(respond(("yogurt", True, False, 0.5)))
    assert [(c.item, c.confidence) for c in changes.added] == [("yogurt", 0.5)]
