# fridge-ask Specification

## Purpose
Turns a free-text fridge question, typed or spoken, into one of the fridge answers (find an item, inventory, activity, last opening) and a short sentence that reads well aloud. It uses keyword matching only, with no language model.

## Requirements

### Requirement: Questions map to one intent
Matching SHALL ignore case, punctuation and extra spaces, and SHALL try intents in this order, using the first that applies: `last_opened`, `fridge_activity`, `find_item`, `get_inventory`. A question that matches none, or is empty, SHALL get intent `unknown`.

#### Scenario: Activity wins over find
- **WHEN** the question is "How many times did we open the fridge today?"
- **THEN** the intent is `fridge_activity`, not `find_item`

#### Scenario: Last opening wins over activity
- **WHEN** the question is "When was the fridge last opened?"
- **THEN** the intent is `last_opened`

#### Scenario: Case and punctuation ignored
- **WHEN** the question is "  DO I HAVE   MILK??? "
- **THEN** the intent is `find_item` with item `milk`

#### Scenario: Nothing matches
- **WHEN** the question is "Play some jazz" or ""
- **THEN** the intent is `unknown`

### Requirement: Last opening questions
A question containing "last" together with a form of "open" ("open", "opened", "opening"), or containing "what changed", SHALL get intent `last_opened`.

#### Scenario: Last opened
- **WHEN** the question is "When did someone last open the fridge?" or "What changed?"
- **THEN** the intent is `last_opened`

### Requirement: Activity questions
A question with a form of "open" together with "how many times", "how often", "today" or "this week" SHALL get intent `fridge_activity`. The period SHALL be `week` when the question contains "week", and `today` otherwise.

#### Scenario: Today
- **WHEN** the question is "How often was the fridge opened?"
- **THEN** the intent is `fridge_activity` with period `today`

#### Scenario: This week
- **WHEN** the question is "How many times did we open the fridge this week?"
- **THEN** the intent is `fridge_activity` with period `week`

### Requirement: Item questions
A question that starts with "do I have", "do we have", "have I got", "is there", "are there", "any" or "got any", or one shaped like "how many <item> …", SHALL get intent `find_item`. The item is what remains after removing that lead-in, the articles "any", "some", "a", "an", "the" and "more", and the trailing words "left", "still", "in the fridge", "in my fridge", "do I have", "do we have" and "are there".

#### Scenario: Do I have milk
- **WHEN** the question is "Do I have any milk left?"
- **THEN** the intent is `find_item` with item `milk`

#### Scenario: How many
- **WHEN** the question is "How many eggs are there in the fridge?"
- **THEN** the intent is `find_item` with item `eggs`

#### Scenario: Multi-word item
- **WHEN** the question is "Is there orange juice?"
- **THEN** the intent is `find_item` with item `orange juice`

#### Scenario: Lead-in with no item
- **WHEN** the question is "Do I have"
- **THEN** the intent is `unknown`

### Requirement: Inventory questions
A question that starts with "what" or "list", or contains "inventory", SHALL get intent `get_inventory`. An item question whose item is a category name, or one of these aliases, SHALL also get `get_inventory` for that category: fruit, vegetables, veggies → produce; fish → seafood; drinks → beverage; bread → bakery; sauces → condiment. A category name or alias anywhere in an inventory question sets the category, and plurals count ("snacks" → snack).

#### Scenario: Whole fridge
- **WHEN** the question is "What's in my fridge?"
- **THEN** the intent is `get_inventory` with no category

#### Scenario: Category in a what question
- **WHEN** the question is "What dairy do I have?"
- **THEN** the intent is `get_inventory` with category `dairy`

#### Scenario: Category asked as an item
- **WHEN** the question is "Do I have any drinks?"
- **THEN** the intent is `get_inventory` with category `beverage`

### Requirement: Spoken answer for an item
For `find_item`, the answer SHALL be built from the find-item result:
- **In the fridge:** "Yes, you have <count> <name>, changed <ago>." for one match. With several matches in stock: "Yes, you have <count> <name> and <count> <name>." (names follow the plural rule below), listing them in the result's order.
- **Out:** "You're out of <item>." when everything matching has count 0.
- **Never seen:** "I haven't seen any <item> in the fridge." when nothing matches.

#### Scenario: One match
- **WHEN** milk has count 1, changed 2 minutes ago, and the question is "Do I have milk?"
- **THEN** the answer is "Yes, you have 1 milk, changed 2 minutes ago."

#### Scenario: Several matches
- **WHEN** "milk" matches oat milk (2) and milk (1)
- **THEN** the answer is "Yes, you have 2 oat milks and 1 milk."

#### Scenario: Ran out
- **WHEN** butter has count 0 and the question is "Do I have butter?"
- **THEN** the answer is "You're out of butter."

#### Scenario: Never seen
- **WHEN** nothing matches "pickles"
- **THEN** the answer is "I haven't seen any pickles in the fridge."

### Requirement: Spoken answer for the inventory
For `get_inventory`, the answer SHALL be "You have <n> items: <list>." The list names up to 5 items as "<count> <name>" in the result's order. When there are more than 5, it ends with "and <rest> more". With one item it SHALL say "1 item". When nothing is in stock it SHALL say "Your fridge looks empty.", or "You have no <category> right now." when a category was asked.

#### Scenario: Short inventory
- **WHEN** the result lists eggs (12) and milk (1)
- **THEN** the answer is "You have 2 items: 12 eggs and 1 milk."

#### Scenario: Long inventory
- **WHEN** the result lists 9 items
- **THEN** the answer names the first 5 and ends "and 4 more."

#### Scenario: Empty category
- **WHEN** the category is `seafood` and nothing is listed
- **THEN** the answer is "You have no seafood right now."

### Requirement: Spoken answer for activity
For `fridge_activity`, the answer SHALL be "The fridge was opened <n> times <period>, for <avg> seconds on average." Here <period> is "today" or "this week", and one opening says "1 time". With no openings it SHALL be "The fridge hasn't been opened <period>."

#### Scenario: Openings today
- **WHEN** the result is 3 opens, 10 seconds on average, period today
- **THEN** the answer is "The fridge was opened 3 times today, for 10 seconds on average."

#### Scenario: No openings this week
- **WHEN** the result is 0 opens for period week
- **THEN** the answer is "The fridge hasn't been opened this week."

### Requirement: Spoken answer for the last opening
For `last_opened`, the answer SHALL be "The fridge was last opened <ago>.", followed by "Added <list>." and "Removed <list>." when there are such changes. When `unsure_count` is above 0 it SHALL end with "<n> change(s) to check in the app." With no door events it SHALL be "The fridge hasn't been opened yet."

#### Scenario: Milk just went in
- **WHEN** the last opening was 2 minutes ago and added 1 milk, with nothing removed and nothing unsure
- **THEN** the answer is "The fridge was last opened 2 minutes ago. Added 1 milk."

#### Scenario: Unsure change
- **WHEN** the last opening 45 minutes ago removed 1 butter and has 1 unsure change
- **THEN** the answer is "The fridge was last opened 45 minutes ago. Removed 1 butter. 1 change to check in the app."

#### Scenario: Never opened
- **WHEN** there are no door events
- **THEN** the answer is "The fridge hasn't been opened yet."

### Requirement: Readable counts and times
Item names in answers SHALL be lower case. A count other than 1 SHALL add "s" to a name that doesn't already end in "s" ("6 soda cans", "12 eggs"). <ago> SHALL be:
- "just now" under 1 minute
- "1 minute ago" or "<n> minutes ago" under 60 minutes
- "<n> hour(s) ago" under 24 hours
- "<n> day(s) ago" after that

#### Scenario: Plural names
- **WHEN** soda can has count 6 and eggs has count 12
- **THEN** the answer says "6 soda cans" and "12 eggs"

#### Scenario: Time phrases
- **WHEN** an item changed 0, 1, 59, 90 and 3000 minutes ago
- **THEN** <ago> is "just now", "1 minute ago", "59 minutes ago", "1 hour ago" and "2 days ago"

### Requirement: Unknown questions get a hint
For intent `unknown`, the answer SHALL be "Try asking: do I have milk, what's in my fridge, or when was the fridge last opened?" and no data SHALL be read.

#### Scenario: Hint
- **WHEN** the question is "Play some jazz"
- **THEN** the answer is the hint sentence and the table is not queried
