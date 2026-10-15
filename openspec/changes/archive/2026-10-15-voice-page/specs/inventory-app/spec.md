# Spec Delta

## ADDED Requirements

### Requirement: Ask screen
The app SHALL have a fifth tab, "Ask" (hash `#ask`), with a text box, a send button and three example questions:
- "Do I have milk?"
- "What's in my fridge?"
- "When was the fridge last opened?"

Sending a question, or tapping an example, SHALL post it to `/api/ask`. The screen then shows the question and the answer, newest first, and reads the answer aloud when the browser supports speech synthesis. The Ask screen SHALL work the same for owner and viewer roles.

#### Scenario: Typed question
- **WHEN** the user opens `#ask`, types "do I have milk?" and presses send, and the API answers "Yes, you have 1 milk, changed 2 minutes ago."
- **THEN** one `ask("do I have milk?")` request is sent, the question and the answer are shown, the text box is cleared, and speech synthesis is asked to speak the answer

#### Scenario: Example question
- **WHEN** the user taps "What's in my fridge?"
- **THEN** that question is posted and its answer is shown

#### Scenario: Newest first
- **WHEN** the user asks two questions in a row
- **THEN** the second question and its answer appear above the first

#### Scenario: Blank question
- **WHEN** the text box is empty or only spaces and the user presses send
- **THEN** no request is sent

#### Scenario: No speech synthesis
- **WHEN** the browser has no `speechSynthesis` and a question is answered
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

### Requirement: Speak a question
When the browser supports speech recognition (`SpeechRecognition` or `webkitSpeechRecognition`), the Ask screen SHALL show a mic button. Tapping it starts listening in English (`en-US`), with a visible "Listening…" state. The first final transcript SHALL be posted as the question. Tapping the button again while listening SHALL stop listening without sending anything. Without speech recognition, the mic button SHALL NOT be shown.

#### Scenario: Spoken question
- **WHEN** speech recognition is available, the user taps the mic, and recognition returns the final transcript "do I have milk"
- **THEN** "Listening…" is shown while recognition runs, `ask("do I have milk")` is sent once, and its answer is shown and spoken

#### Scenario: No speech recognition
- **WHEN** neither `SpeechRecognition` nor `webkitSpeechRecognition` exists
- **THEN** no mic button is shown and the text box still works

#### Scenario: Nothing heard
- **WHEN** recognition ends with an error (`no-speech`, `not-allowed` or `aborted`), or ends with no final transcript
- **THEN** the screen shows "Didn't catch that. Try again or type your question.", leaves "Listening…", and sends no request

#### Scenario: Stop listening
- **WHEN** the user taps the mic while it is listening
- **THEN** recognition is stopped and no request is sent
