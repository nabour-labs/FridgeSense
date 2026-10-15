"""fridge-mcp: forgiving item-name matching for spoken questions."""

import pytest

from fridgesense.fridge_answers import name_matches, normalize_query


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("eggs", "egg"),
        ("Egg", "egg"),
        ("  Whole   Milk ", "whole milk"),
        ("glass", "glass"),
        ("boxes", "box"),
        ("dishes", "dish"),
        ("peaches", "peach"),
        ("tomatoes", "tomato"),
        ("soda cans", "soda can"),
        ("milk", "milk"),
    ],
)
def test_normalize_query(text, expected):
    assert normalize_query(text) == expected


@pytest.mark.parametrize(
    ("query", "name", "match"),
    [
        ("eggs", "egg", True),
        ("egg", "eggs", True),
        ("milk", "whole milk", True),
        ("Milk", "oat milk", True),
        ("milk", "milkshake", False),
        ("soda", "soda can", True),
        ("can", "soda can", True),
        ("glass", "glass noodles", True),
        ("cheese", "cream cheese", True),
        ("cream", "cream cheese", True),
        ("caviar", "milk", False),
        ("", "milk", False),
    ],
)
def test_name_matches(query, name, match):
    assert name_matches(query, name) is match
