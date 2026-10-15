## MODIFIED Requirements

### Requirement: Questions map to one intent
Matching SHALL ignore case, punctuation and extra spaces, and SHALL try intents in this order, using the first that applies: `oldest_items`, `low_stock`, `last_opened`, `fridge_activity`, `find_item`, `get_inventory`. A question that matches none, or is empty, SHALL get intent `unknown`.

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

## ADDED Requirements

### Requirement: Eat-first questions
A question containing "eat first", "use first", "use up", "oldest", "going bad", "go bad" or "expir" SHALL get intent `oldest_items`.

#### Scenario: Eat first
- **WHEN** the question is "What should I eat first?", "What's going bad?" or "Anything expiring soon?"
- **THEN** the intent is `oldest_items`

### Requirement: Shopping questions
A question containing "need to buy", "should i buy", "shopping list", "grocery list", "running low", "what ran out", "what have i run out of" or "what am i out of" SHALL get intent `low_stock`. A question about one item that only shares words with these cues, such as "Am I out of milk?", SHALL NOT get intent `low_stock`.

#### Scenario: Shopping list
- **WHEN** the question is "What do I need to buy?", "Make me a shopping list" or "What's running low?"
- **THEN** the intent is `low_stock`

#### Scenario: One item is not a shopping question
- **WHEN** the question is "Am I out of milk?" or "Do we have any eggs left?"
- **THEN** the intent is not `low_stock` ("Do we have any eggs left?" stays `find_item` with item `eggs`)

### Requirement: Spoken answer for eat-first
For `oldest_items`, the answer SHALL be "Use these first: <list>." naming up to 3 items in the result's order as "<count> <name> from <when>", where <when> is "today" (0 days), "yesterday" (1 day) or "<n> days ago". With no items it SHALL be "Nothing in the fridge needs using up."

#### Scenario: Three oldest
- **WHEN** the result lists milk (1, 9 days), apple (3, 6 days), leftovers (1, 0 days) and eggs (6, 2 days)
- **THEN** the answer is "Use these first: 1 milk from 9 days ago, 3 apples from 6 days ago and 1 leftovers from today."

#### Scenario: Yesterday
- **WHEN** the result lists only yogurt (2, 1 day)
- **THEN** the answer is "Use these first: 2 yogurts from yesterday."

#### Scenario: Nothing to use up
- **WHEN** the result has no items
- **THEN** the answer is "Nothing in the fridge needs using up."

### Requirement: Spoken answer for shopping
For `low_stock`, the answer SHALL be "You're out of <names>." when anything ran out, followed by "Running low: <list>." when anything is low, where <list> names "<count> <name>". Up to 5 names are said in each part, ending with "and <rest> more" beyond that. With nothing in either list it SHALL be "Nothing has run out or is running low."

#### Scenario: Out and low
- **WHEN** `ran_out` is milk and butter, and `running_low` is eggs (2)
- **THEN** the answer is "You're out of milk and butter. Running low: 2 eggs."

#### Scenario: Only low
- **WHEN** `ran_out` is empty and `running_low` is apples (3)
- **THEN** the answer is "Running low: 3 apples."

#### Scenario: Nothing to buy
- **WHEN** both lists are empty
- **THEN** the answer is "Nothing has run out or is running low."
