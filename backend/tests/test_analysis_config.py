"""analysis-config: validation, storage and loading of reference images and instructions."""

import base64

import pytest

from fridgesense import analysis_config as cfg
from fridgesense.table import FridgeTable

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 100
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
A, B = "ava1.ring.account.A1", "ava1.ring.account.B2"


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


# Bad annotation
@pytest.mark.parametrize("value", [None, "", "   ", "x" * 301, 5])
def test_bad_annotation(value):
    with pytest.raises(cfg.Invalid) as e:
        cfg.validate_annotation(value)
    assert e.value.message == "annotation must be 1 to 300 characters"


@pytest.mark.parametrize(
    "value, expected", [("a", "a"), ("x" * 300, "x" * 300), ("  soda can  ", "soda can")]
)
def test_good_annotation(value, expected):
    assert cfg.validate_annotation(value) == expected


# Not a JPEG or too large
@pytest.mark.parametrize(
    "value",
    [None, 5, "not base64!!", b64(PNG), b64(b"\xff\xd8\xff" + b"\x00" * (cfg.MAX_IMAGE_BYTES - 2))],
)
def test_bad_image(value):
    with pytest.raises(cfg.Invalid) as e:
        cfg.decode_image(value)
    assert e.value.message == "image must be a JPEG of at most 200 KB"


def test_image_at_the_size_limit():
    data = b"\xff\xd8\xff" + b"\x00" * (cfg.MAX_IMAGE_BYTES - 3)
    assert len(data) == 200_000
    assert cfg.decode_image(b64(data)) == data


# Save instructions / Clear instructions / Instructions too long or wrong type
def test_instructions_trimmed_and_cleared():
    assert (
        cfg.validate_instructions("  Count yogurt cups individually.  ")
        == "Count yogurt cups individually."
    )
    assert cfg.validate_instructions("") == ""
    assert cfg.validate_instructions("x" * 1000) == "x" * 1000


@pytest.mark.parametrize("value", ["x" * 1001, 5, None])
def test_bad_instructions(value):
    with pytest.raises(cfg.Invalid) as e:
        cfg.validate_instructions(value)
    assert e.value.message == "instructions must be text of at most 1000 characters"


@pytest.fixture
def table(aws):
    return FridgeTable()


def add(table, account, annotation, now_ms):
    return cfg.add_reference(table, account, annotation, JPEG + annotation.encode(), now_ms=now_ms)


# Nothing configured
def test_nothing_configured(table):
    loaded = cfg.load(table, A)
    assert loaded.instructions == "" and loaded.references == []


# Config with references: oldest first
def test_references_load_oldest_first_with_instructions(table):
    add(table, A, "milk bag", now_ms=1_000)
    add(table, A, "soda can", now_ms=2_000)
    cfg.save_instructions(table, A, "Count yogurt cups individually.", now_ms=3_000)
    loaded = cfg.load(table, A)
    assert [r.annotation for r in loaded.references] == ["milk bag", "soda can"]
    assert loaded.references[0].image == JPEG + b"milk bag"
    assert loaded.references[0].created_at == "1970-01-01T00:00:01.000Z"
    assert loaded.references[0].sk.startswith("REF#")
    assert loaded.instructions == "Count yogurt cups individually."


# Clear instructions
def test_clear_instructions(table):
    cfg.save_instructions(table, A, "x", now_ms=1)
    cfg.save_instructions(table, A, "", now_ms=2)
    assert cfg.load(table, A).instructions == ""


# Seventh reference
def test_seventh_reference_refused(table):
    for n in range(6):
        add(table, A, f"item {n}", now_ms=n)
    with pytest.raises(cfg.TooMany):
        add(table, A, "one more", now_ms=99)
    assert [r.annotation for r in cfg.load(table, A).references] == [f"item {n}" for n in range(6)]


# Delete a reference / Unknown reference
def test_delete_reference(table):
    milk = add(table, A, "milk bag", now_ms=1)
    add(table, A, "soda can", now_ms=2)
    assert cfg.delete_reference(table, A, milk.sk) is True
    assert [r.annotation for r in cfg.load(table, A).references] == ["soda can"]
    assert cfg.delete_reference(table, A, milk.sk) is False
    assert cfg.delete_reference(table, A, "REF#nope") is False


# Config kept per account
def test_config_kept_per_account(table):
    add(table, A, "milk bag", now_ms=1)
    cfg.save_instructions(table, A, "A only", now_ms=1)
    loaded = cfg.load(table, B)
    assert loaded.references == [] and loaded.instructions == ""
    milk = cfg.load(table, A).references[0]
    assert cfg.delete_reference(table, B, milk.sk) is False
    assert len(cfg.load(table, A).references) == 1


# Edit the annotation / Replace the image / Edit an unknown reference
def test_update_reference(table):
    milk = add(table, A, "milk bag", now_ms=1)
    add(table, A, "soda can", now_ms=2)
    assert cfg.update_reference(table, A, milk.sk, "chocolate milk", None, now_ms=3) is True
    first = cfg.load(table, A).references[0]
    assert (first.sk, first.annotation, first.image, first.created_at) == (
        milk.sk,
        "chocolate milk",
        milk.image,
        milk.created_at,
    )
    assert cfg.update_reference(table, A, milk.sk, None, JPEG + b"new", now_ms=4) is True
    first = cfg.load(table, A).references[0]
    assert (first.annotation, first.image) == ("chocolate milk", JPEG + b"new")
    assert [r.annotation for r in cfg.load(table, A).references] == ["chocolate milk", "soda can"]
    assert cfg.update_reference(table, A, "REF#nope", "x", None, now_ms=5) is False
    assert cfg.update_reference(table, B, milk.sk, "x", None, now_ms=5) is False
    assert cfg.update_reference(table, A, "CONFIG#instructions", "x", None, now_ms=5) is False
