import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "../App";
import { Offline } from "../api/client";
import type { AskResult } from "../api/types";
import { fakeApi, signedIn } from "../test-utils";

const MILK = "Yes, you have 1 milk, changed 2 minutes ago.";

class FakeUtterance {
  constructor(readonly text: string) {}
}

let synth: { speak: ReturnType<typeof vi.fn>; cancel: ReturnType<typeof vi.fn> };

beforeEach(() => {
  synth = { speak: vi.fn(), cancel: vi.fn() };
  vi.stubGlobal("speechSynthesis", synth);
  vi.stubGlobal("SpeechSynthesisUtterance", FakeUtterance);
  useFakeAudio(); // jsdom can't play or pause media
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function answer(text: string): AskResult {
  return { intent: "find_item", answer: text, data: null, source: "keywords", audio: null };
}

function renderAsk(ask = vi.fn(async (q: string) => answer(`Answer to ${q}`)), role?: "viewer") {
  signedIn(role);
  location.hash = "#ask";
  const api = fakeApi({ ask });
  render(<App api={api} />);
  return api;
}

const spoken = () => synth.speak.mock.calls.map(([u]) => (u as FakeUtterance).text);

// Five tabs
test("the bottom navigation has five tabs and #ask opens the Ask screen", () => {
  renderAsk();
  const nav = screen.getByRole("navigation", { name: "Screens" });
  expect(within(nav).getAllByRole("link").map((a) => a.textContent)).toEqual([
    "Fridge",
    "Activity",
    "Review",
    "Stats",
    "Ask",
  ]);
  expect(screen.getByRole("heading", { level: 1, name: "Ask" })).toBeInTheDocument();
  expect(screen.getByRole("textbox", { name: "Question" })).toBeInTheDocument();
});

// Typed question
test("a typed question is sent, answered, cleared and spoken", async () => {
  const ask = vi.fn(async () => answer(MILK));
  renderAsk(ask);
  const box = screen.getByRole("textbox", { name: "Question" });
  await userEvent.type(box, "do I have milk?");
  await userEvent.click(screen.getByRole("button", { name: "Send" }));
  expect(await screen.findByText(MILK)).toBeInTheDocument();
  expect(ask).toHaveBeenCalledTimes(1);
  expect(ask).toHaveBeenCalledWith("do I have milk?");
  expect(screen.getByText("do I have milk?")).toBeInTheDocument();
  expect(box).toHaveValue("");
  expect(spoken()).toEqual([MILK]);
});

// Example question
test("tapping an example asks it", async () => {
  const ask = renderAsk().ask;
  await userEvent.click(screen.getByRole("button", { name: "What's in my fridge?" }));
  expect(await screen.findByText("Answer to What's in my fridge?")).toBeInTheDocument();
  expect(ask).toHaveBeenCalledWith("What's in my fridge?");
});

// Five examples
test("five example questions, in order", async () => {
  const ask = renderAsk().ask;
  expect(screen.getAllByRole("button", { name: /\?$/ }).map((b) => b.textContent)).toEqual([
    "Do I have milk?",
    "What's in my fridge?",
    "What should I eat first?",
    "What do I need to buy?",
    "When was the fridge last opened?",
  ]);
  await userEvent.click(screen.getByRole("button", { name: "What should I eat first?" }));
  expect(await screen.findByText("Answer to What should I eat first?")).toBeInTheDocument();
  expect(ask).toHaveBeenCalledWith("What should I eat first?");
});

// Newest first
test("the newest question and answer are shown first", async () => {
  renderAsk();
  const box = screen.getByRole("textbox", { name: "Question" });
  await userEvent.type(box, "first{Enter}");
  await screen.findByText("Answer to first");
  await userEvent.type(box, "second{Enter}");
  await screen.findByText("Answer to second");
  const list = screen.getByRole("list", { name: "Answers" });
  const answers = within(list).getAllByRole("listitem").map((li) => li.textContent);
  expect(answers[0]).toContain("Answer to second");
  expect(answers[1]).toContain("Answer to first");
});

// Blank question
test("a blank question sends nothing", async () => {
  const ask = renderAsk().ask;
  await userEvent.click(screen.getByRole("button", { name: "Send" }));
  await userEvent.type(screen.getByRole("textbox", { name: "Question" }), "   {Enter}");
  expect(ask).not.toHaveBeenCalled();
});

// No speech synthesis
test("answers still show without speech synthesis", async () => {
  vi.unstubAllGlobals();
  vi.stubGlobal("speechSynthesis", undefined);
  useFakeAudio();
  renderAsk(vi.fn(async () => answer(MILK)));
  await userEvent.click(screen.getByRole("button", { name: "Do I have milk?" }));
  expect(await screen.findByText(MILK)).toBeInTheDocument();
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
});

// Viewer asks
test("the demo viewer can ask", async () => {
  renderAsk(vi.fn(async () => answer(MILK)), "viewer");
  await userEvent.click(screen.getByRole("button", { name: "Do I have milk?" }));
  expect(await screen.findByText(MILK)).toBeInTheDocument();
  expect(screen.queryByText("Read-only demo")).not.toBeInTheDocument();
});

// Request fails
test("a failed request shows the offline banner and keeps the question", async () => {
  renderAsk(vi.fn(async () => Promise.reject(new Offline("down"))));
  const box = screen.getByRole("textbox", { name: "Question" });
  await userEvent.type(box, "do I have milk?{Enter}");
  expect(await screen.findByText(/Can't reach FridgeSense/)).toBeInTheDocument();
  expect(box).toHaveValue("do I have milk?");
  const list = screen.getByRole("list", { name: "Answers" });
  expect(within(list).queryAllByRole("listitem")).toHaveLength(0);
  expect(synth.speak).not.toHaveBeenCalled();
});

class FakeRecognition {
  static last: FakeRecognition | null = null;
  lang = "";
  interimResults = true;
  maxAlternatives = 0;
  onresult: ((e: unknown) => void) | null = null;
  onerror: ((e: unknown) => void) | null = null;
  onend: (() => void) | null = null;
  start = vi.fn();
  stop = vi.fn(() => this.end());
  abort = vi.fn();
  constructor() {
    FakeRecognition.last = this;
  }
  hear(transcript: string) {
    act(() => {
      const result = Object.assign([{ transcript, confidence: 0.9 }], { isFinal: true });
      this.onresult?.({ resultIndex: 0, results: [result] });
    });
  }
  fail(error: string) {
    act(() => this.onerror?.({ error }));
  }
  end() {
    act(() => this.onend?.());
  }
}

function withRecognition(name = "SpeechRecognition") {
  FakeRecognition.last = null;
  vi.stubGlobal(name, FakeRecognition);
}

const mic = () => screen.getByRole("button", { name: /speak|stop listening/i });

// Spoken question
test("a spoken question is sent once, answered and spoken", async () => {
  withRecognition();
  const ask = vi.fn(async () => answer(MILK));
  renderAsk(ask);
  await userEvent.click(mic());
  const rec = FakeRecognition.last!;
  expect(rec.start).toHaveBeenCalledTimes(1);
  expect(rec.lang).toBe("en-US");
  expect(rec.interimResults).toBe(false);
  expect(rec.maxAlternatives).toBe(1);
  expect(screen.getByText("Listening…")).toBeInTheDocument();
  rec.hear("do I have milk");
  rec.end();
  expect(await screen.findByText(MILK)).toBeInTheDocument();
  expect(ask).toHaveBeenCalledTimes(1);
  expect(ask).toHaveBeenCalledWith("do I have milk");
  expect(screen.queryByText("Listening…")).not.toBeInTheDocument();
  expect(spoken()).toEqual([MILK]);
});

test("the webkit-prefixed recognition is used too", () => {
  withRecognition("webkitSpeechRecognition");
  renderAsk();
  expect(mic()).toBeInTheDocument();
});

// No speech recognition
test("no mic button without speech recognition", async () => {
  renderAsk();
  expect(screen.queryByRole("button", { name: /speak/i })).not.toBeInTheDocument();
  await userEvent.type(screen.getByRole("textbox", { name: "Question" }), "milk?{Enter}");
  expect(await screen.findByText("Answer to milk?")).toBeInTheDocument();
});

// Nothing heard
test.each(["no-speech", "not-allowed", "aborted"])("recognition error %s sends nothing", async (error) => {
  withRecognition();
  const ask = renderAsk().ask;
  await userEvent.click(mic());
  FakeRecognition.last!.fail(error);
  FakeRecognition.last!.end();
  expect(screen.getByText("Didn't catch that. Try again or type your question.")).toBeInTheDocument();
  expect(screen.queryByText("Listening…")).not.toBeInTheDocument();
  expect(ask).not.toHaveBeenCalled();
});

test("ending without a final transcript sends nothing", async () => {
  withRecognition();
  const ask = renderAsk().ask;
  await userEvent.click(mic());
  FakeRecognition.last!.end();
  expect(screen.getByText("Didn't catch that. Try again or type your question.")).toBeInTheDocument();
  expect(ask).not.toHaveBeenCalled();
});

// Stop listening
test("tapping the mic while listening stops without sending", async () => {
  withRecognition();
  const ask = renderAsk().ask;
  await userEvent.click(mic());
  await userEvent.click(screen.getByRole("button", { name: "Stop listening" }));
  expect(FakeRecognition.last!.stop).toHaveBeenCalledTimes(1);
  expect(screen.queryByText("Listening…")).not.toBeInTheDocument();
  expect(ask).not.toHaveBeenCalled();
});

// Leave while listening
test("leaving the Ask screen while listening stops recognition and sends nothing", async () => {
  withRecognition();
  const ask = renderAsk().ask;
  await userEvent.click(mic());
  const rec = FakeRecognition.last!;
  await userEvent.click(screen.getByRole("link", { name: "Fridge" }));
  expect(rec.abort.mock.calls.length + rec.stop.mock.calls.length).toBeGreaterThan(0);
  rec.hear("do I have milk");
  rec.end();
  await act(async () => {});
  expect(ask).not.toHaveBeenCalled();
});

// Leave while speaking
test("leaving the Ask screen stops any answer being read aloud", async () => {
  renderAsk();
  synth.cancel.mockClear();
  await userEvent.click(screen.getByRole("link", { name: "Fridge" }));
  expect(synth.cancel).toHaveBeenCalled();
});

// The voice: Polly audio from the API, played through an <audio> element.
const AUDIO = "SUQzZmFrZQ==";

class FakeAudio {
  static instances: FakeAudio[] = [];
  static playResult: () => Promise<void> = () => Promise.resolve();
  src = "";
  play = vi.fn(() => FakeAudio.playResult());
  pause = vi.fn();
  constructor() {
    FakeAudio.instances.push(this);
  }
}

function useFakeAudio(play: () => Promise<void> = () => Promise.resolve()) {
  FakeAudio.instances = [];
  FakeAudio.playResult = play;
  vi.stubGlobal("Audio", FakeAudio);
}

function agentAnswer(text: string, tools: string[], audio: string | null = AUDIO): AskResult {
  return { intent: "agent", answer: text, data: { tools }, source: "agent", audio };
}

const played = () => FakeAudio.instances.flatMap((a) => (a.play.mock.calls.length ? [a.src] : []));

// Thinking
test("Thinking… shows while the answer is on its way", async () => {
  useFakeAudio();
  let reply!: (r: AskResult) => void;
  renderAsk(vi.fn(() => new Promise<AskResult>((resolve) => (reply = resolve))));
  await userEvent.click(screen.getByRole("button", { name: "Do I have milk?" }));
  expect(screen.getByText("Thinking…")).toBeInTheDocument();
  await act(async () => reply(answer(MILK)));
  expect(screen.getByText(MILK)).toBeInTheDocument();
  expect(screen.queryByText("Thinking…")).not.toBeInTheDocument();
});

// Plays the voice audio
test("the answer's audio is played instead of speech synthesis", async () => {
  useFakeAudio();
  renderAsk(vi.fn(async () => ({ ...answer(MILK), audio: AUDIO })));
  await userEvent.click(screen.getByRole("button", { name: "Do I have milk?" }));
  expect(await screen.findByText(MILK)).toBeInTheDocument();
  expect(played()).toEqual([`data:audio/mpeg;base64,${AUDIO}`]);
  expect(synth.speak).not.toHaveBeenCalled();
});

// Audio can't play
test("speech synthesis reads the answer when the audio can't play", async () => {
  useFakeAudio(() => Promise.reject(new Error("NotAllowedError")));
  renderAsk(vi.fn(async () => ({ ...answer(MILK), audio: AUDIO })));
  await userEvent.click(screen.getByRole("button", { name: "Do I have milk?" }));
  expect(await screen.findByText(MILK)).toBeInTheDocument();
  await act(async () => {});
  expect(spoken()).toEqual([MILK]);
});

// Tools checked
test("an assistant answer shows the tools it checked", async () => {
  useFakeAudio();
  const text = "You could make an omelette.";
  renderAsk(vi.fn(async () => agentAnswer(text, ["get_inventory", "find_item"])));
  await userEvent.click(screen.getByRole("button", { name: "What's in my fridge?" }));
  expect(await screen.findByText(text)).toBeInTheDocument();
  expect(screen.getByText("Checked: get_inventory, find_item")).toBeInTheDocument();
});

test("an assistant answer that checked nothing has no tools line", async () => {
  useFakeAudio();
  renderAsk(vi.fn(async () => agentAnswer("Hello!", [])));
  await userEvent.click(screen.getByRole("button", { name: "Do I have milk?" }));
  expect(await screen.findByText("Hello!")).toBeInTheDocument();
  expect(screen.queryByText(/^Checked:/)).not.toBeInTheDocument();
});

// Keyword answer has no tools line
test("a keyword answer has no tools line", async () => {
  useFakeAudio();
  renderAsk(vi.fn(async () => answer(MILK)));
  await userEvent.click(screen.getByRole("button", { name: "Do I have milk?" }));
  expect(await screen.findByText(MILK)).toBeInTheDocument();
  expect(screen.queryByText(/^Checked:/)).not.toBeInTheDocument();
});

// Leaving stops the voice
test("leaving the Ask screen pauses the answer's audio", async () => {
  useFakeAudio();
  renderAsk(vi.fn(async () => ({ ...answer(MILK), audio: AUDIO })));
  await userEvent.click(screen.getByRole("button", { name: "Do I have milk?" }));
  expect(await screen.findByText(MILK)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("link", { name: "Fridge" }));
  expect(FakeAudio.instances.some((a) => a.pause.mock.calls.length > 0)).toBe(true);
});
