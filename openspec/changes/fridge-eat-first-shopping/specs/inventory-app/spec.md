## MODIFIED Requirements

### Requirement: Ask screen
The app SHALL have a fifth tab, "Ask" (hash `#ask`), with a text box, a send button and five example questions:
- "Do I have milk?"
- "What's in my fridge?"
- "What should I eat first?"
- "What do I need to buy?"
- "When was the fridge last opened?"

Sending a question, or tapping an example, SHALL post it to `/api/ask`. While waiting, the screen shows "Thinking…". The screen then shows the question and the answer, newest first, and reads the answer aloud: it plays the response's `audio` (MP3) when there is one, and otherwise uses speech synthesis when the browser supports it. When `source` is `"agent"` and tools were called, the answer has a small line "Checked: <tool names, comma-separated>". The Ask screen SHALL work the same for owner and viewer roles.

#### Scenario: Typed question
- **WHEN** the user opens `#ask`, types "do I have milk?" and presses send, and the API answers "Yes, you have 1 milk, changed 2 minutes ago." with `audio` `null`
- **THEN** one `ask("do I have milk?")` request is sent, the question and the answer are shown, the text box is cleared, and speech synthesis is asked to speak the answer

#### Scenario: Example question
- **WHEN** the user taps "What's in my fridge?"
- **THEN** that question is posted and its answer is shown

#### Scenario: Five examples
- **WHEN** the user opens `#ask`
- **THEN** the five example questions are shown as buttons in the order above, and tapping "What should I eat first?" posts that question

#### Scenario: Newest first
- **WHEN** the user asks two questions in a row
- **THEN** the second question and its answer appear above the first

#### Scenario: Blank question
- **WHEN** the text box is empty or only spaces and the user presses send
- **THEN** no request is sent

#### Scenario: No speech synthesis
- **WHEN** the browser has no `speechSynthesis`, the response has no `audio`, and a question is answered
- **THEN** the answer is shown and no error appears

#### Scenario: Viewer asks
- **WHEN** the role is `viewer` and the user asks "Do I have milk?"
- **THEN** the answer is shown and no "Read-only demo" notice appears

#### Scenario: Request fails
- **WHEN** the ask request fails because FridgeSense can't be reached
- **THEN** the app shows its offline banner, the question stays in the text box, and no answer is added

#### Scenario: Five tabs
- **WHEN** the signed-in app is shown
- **THEN** the bottom navigation has Fridge, Activity, Review, Stats and Ask, and opening `#ask` shows the Ask screen with the title "Ask"

#### Scenario: Thinking
- **WHEN** a question has been sent and the API has not answered yet
- **THEN** "Thinking…" is shown, and it is gone once the answer appears

#### Scenario: Plays the voice audio
- **WHEN** the API answers with `audio` `"SUQzZmFrZQ=="`
- **THEN** an audio element plays `data:audio/mpeg;base64,SUQzZmFrZQ==` and speech synthesis is not used

#### Scenario: Audio can't play
- **WHEN** the API answers with `audio` but playing it is rejected (for example by the browser's autoplay policy)
- **THEN** speech synthesis is asked to speak the answer instead

#### Scenario: Tools checked
- **WHEN** the API answers with `source` `"agent"` and `data` `{"tools": ["get_inventory", "find_item"]}`
- **THEN** the answer shows "Checked: get_inventory, find_item"

#### Scenario: Keyword answer has no tools line
- **WHEN** the API answers with `source` `"keywords"`
- **THEN** no "Checked:" line is shown

#### Scenario: Leaving stops the voice
- **WHEN** an answer's audio is playing and the user switches to another tab
- **THEN** the audio is paused
