# Proposal

## Why

The demo line ends with "Alexa, do I have milk?". Reaching the MCP server from Alexa+ still depends on Amazon's MCP Toolkit, which may be gated for hackathon entrants, and judges can't use Jayson's Echo. The rules allow a simulated Alexa+ experience. A voice page in the PWA keeps the demo working either way, and lets judges try it with the demo passcode.

Tracks: **Alexa+** (the simulated voice experience, built on the same answers as the MCP tools) and **Ring** (the answers come from what the Ring camera saw).

## What Changes

- **A new `POST /api/ask` route** on the existing app API. It takes `{"question": "<text>"}` and returns `{"intent", "answer", "data"}`:
  - `answer` is one short sentence meant to be read aloud.
  - `data` is the structured result of the matching fridge answer.
  - It is read-only, so demo (viewer) tokens can use it.
- **Keyword intent matching, with no LLM.** It sends the question to one of the four existing answers the MCP tools use: find an item, what's in the fridge (optionally one category), fridge activity (today or this week), or last opening. Each question costs nothing and answers fast.
- **Spoken sentences** built from those answers. For example: "Yes, you have 1 milk, changed 2 minutes ago." When nothing matches, the reply is a helpful hint rather than an error.
- **An "Ask" screen** in the PWA, as a fifth tab:
  - A mic button transcribes speech in the browser with the Web Speech API.
  - A text box always works, and is the only input when the browser has no speech recognition.
  - The page shows the question and answer, and reads the answer aloud with speech synthesis.

## Capabilities

### New Capabilities

- `fridge-ask`: turning a free-text fridge question into one of the fridge answers and a short spoken sentence.

### Modified Capabilities

- `inventory-api`: adds the `POST /api/ask` requirement.
- `inventory-app`: adds the Ask screen requirement.

## Out of scope

- **An LLM or Bedrock call per question.** Keyword matching is enough for the demo questions and costs nothing. An LLM fallback for unmatched questions is a stretch goal.
- **Wake words, always-on listening and server-side speech-to-text** (Amazon Transcribe). The browser does the transcription.
- **Write commands by voice**, such as "I used the last egg".
- **Languages other than English**, and conversation context across follow-up questions.
- **Changes to the MCP server.** Its tools and outputs stay as they are.
- **Naming the page after Alexa.** The product name never includes "Alexa"; the page is called "Ask".

## Impact

- **Backend:** a new module `backend/src/fridgesense/ask.py` (intent matching and sentences) reusing `fridge_answers.py`, and a new route in `handlers/api.py`. No new dependencies.
- **PWA:** a new `screens/Ask.tsx`, an `ask()` method on `ApiClient`, an `"ask"` tab, and the bottom nav going from 4 to 5 columns. No new dependencies; it uses the browser's `SpeechRecognition` / `webkitSpeechRecognition` and `speechSynthesis`.
- **AWS:** no new resources. The existing `ANY /api/{proxy+}` route and API Lambda carry the new route. The API Lambda gains a `TIME_ZONE` env var, the same CDK `timeZone` value the MCP Lambda uses, so this needs a `cdk deploy`. Each question costs a few DynamoDB reads.
- **Infra:** `infra/lib/app-site.ts` and `fridgesense-stack.ts` (the `timeZone` prop).
- **Browsers:** speech input works in Chrome and Safari, including iOS Safari. Firefox gets the text box only.
