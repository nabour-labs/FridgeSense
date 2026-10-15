"""fridge-ask: free-text fridge questions map to one intent."""

import pytest

from fridgesense.ask import parse


# Activity wins over find
def test_activity_wins_over_find():
    assert parse("How many times did we open the fridge today?").name == "fridge_activity"


# Last opening wins over activity
def test_last_opening_wins_over_activity():
    assert parse("When was the fridge last opened?").name == "last_opened"


# Case and punctuation ignored
def test_case_and_punctuation_ignored():
    intent = parse("  DO I HAVE   MILK??? ")
    assert (intent.name, intent.item) == ("find_item", "milk")


# Nothing matches
@pytest.mark.parametrize("question", ["Play some jazz", ""])
def test_nothing_matches(question):
    assert parse(question).name == "unknown"


# Last opened
@pytest.mark.parametrize("question", ["When did someone last open the fridge?", "What changed?"])
def test_last_opened(question):
    assert parse(question).name == "last_opened"


# Today
def test_activity_today():
    intent = parse("How often was the fridge opened?")
    assert (intent.name, intent.period) == ("fridge_activity", "today")


# This week
def test_activity_this_week():
    intent = parse("How many times did we open the fridge this week?")
    assert (intent.name, intent.period) == ("fridge_activity", "week")


# Do I have milk
def test_do_i_have_milk():
    intent = parse("Do I have any milk left?")
    assert (intent.name, intent.item) == ("find_item", "milk")


# How many
def test_how_many():
    intent = parse("How many eggs are there in the fridge?")
    assert (intent.name, intent.item) == ("find_item", "eggs")


# Multi-word item
def test_multi_word_item():
    intent = parse("Is there orange juice?")
    assert (intent.name, intent.item) == ("find_item", "orange juice")


# Lead-in with no item
def test_lead_in_with_no_item():
    assert parse("Do I have").name == "unknown"


@pytest.mark.parametrize(
    ("question", "item"),
    [
        ("Do we have some butter?", "butter"),
        ("Have I got cheese?", "cheese"),
        ("Are there apples?", "apples"),
        ("Any yogurt?", "yogurt"),
        ("Got any eggs still?", "eggs"),
        ("How many soda cans do I have?", "soda cans"),
        ("Is there milk still in my fridge?", "milk"),
    ],
)
def test_item_lead_ins_and_filler(question, item):
    intent = parse(question)
    assert (intent.name, intent.item) == ("find_item", item)


# Whole fridge
@pytest.mark.parametrize("question", ["What's in my fridge?", "List everything", "Show inventory"])
def test_whole_fridge(question):
    intent = parse(question)
    assert (intent.name, intent.category) == ("get_inventory", None)


# Category in a what question
def test_category_in_a_what_question():
    intent = parse("What dairy do I have?")
    assert (intent.name, intent.category) == ("get_inventory", "dairy")


# Category asked as an item
def test_category_asked_as_an_item():
    intent = parse("Do I have any drinks?")
    assert (intent.name, intent.category) == ("get_inventory", "beverage")


@pytest.mark.parametrize(
    ("question", "category"),
    [
        ("What fruit do I have?", "produce"),
        ("What vegetables are there?", "produce"),
        ("Any veggies?", "produce"),
        ("Do we have fish?", "seafood"),
        ("Is there bread?", "bakery"),
        ("What sauces are in the fridge?", "condiment"),
        ("What snacks do I have?", "snack"),
        ("Any leftovers?", "leftovers"),
        ("What frozen stuff is there?", "frozen"),
        ("List the meat", "meat"),
    ],
)
def test_category_aliases_and_plurals(question, category):
    intent = parse(question)
    assert (intent.name, intent.category) == ("get_inventory", category)


# Eat first
@pytest.mark.parametrize(
    "question", ["What should I eat first?", "What's going bad?", "Anything expiring soon?"]
)
def test_eat_first(question):
    assert parse(question).name == "oldest_items"


# Shopping list
@pytest.mark.parametrize(
    "question", ["What do I need to buy?", "Make me a shopping list", "What's running low?"]
)
def test_shopping_list(question):
    assert parse(question).name == "low_stock"


# One item is not a shopping question
def test_one_item_is_not_a_shopping_question():
    assert parse("Am I out of milk?").name != "low_stock"
    intent = parse("Do we have any eggs left?")
    assert (intent.name, intent.item) == ("find_item", "eggs")
