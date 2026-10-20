import { Mic, Send, Square } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useApp } from "../AppContext";
import type { AskResult } from "../api/types";
import { finalTranscript, newRecognizer, playAnswer, recognizerClass, type Recognizer } from "../voice";

const EXAMPLES = [
  "Do I have milk?",
  "What's in my fridge?",
  "What should I eat first?",
  "What do I need to buy?",
  "When was the fridge last opened?",
];

interface Exchange {
  id: number;
  question: string;
  answer: string;
  /** The MCP tools the assistant checked, for assistant answers. */
  tools?: string[];
}

const NOT_HEARD = "Didn't catch that. Try again or type your question.";

function toolsOf(result: AskResult): string[] | undefined {
  const tools = result.source === "agent" ? result.data?.tools : undefined;
  return Array.isArray(tools) && tools.length ? tools.map(String) : undefined;
}

let nextId = 0;

export function Ask() {
  const { api, report, online } = useApp();
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [history, setHistory] = useState<Exchange[]>([]);
  const [listening, setListening] = useState(false);
  const [hint, setHint] = useState<string | null>(null);
  const recognizer = useRef<Recognizer | null>(null);
  // One <audio> element, created on the first tap so that the tap unlocks playback (iOS).
  const voice = useRef<HTMLAudioElement | null>(null);
  const Recognition = recognizerClass();

  // Leaving the screen (tab switch, sign-out) ends listening and speaking, and sends nothing:
  // clearing the ref first makes onend drop whatever was heard.
  useEffect(
    () => () => {
      const rec = recognizer.current;
      recognizer.current = null;
      if (rec) {
        if (rec.abort) rec.abort();
        else rec.stop();
      }
      if (typeof speechSynthesis !== "undefined") speechSynthesis.cancel();
      voice.current?.pause();
    },
    [],
  );

  function listen() {
    if (!Recognition) return;
    if (recognizer.current) {
      const current = recognizer.current;
      recognizer.current = null;
      setListening(false);
      current.stop();
      return;
    }
    const rec = newRecognizer(Recognition);
    let heard: string | null = null;
    rec.onresult = (e) => {
      if (heard === null) heard = finalTranscript(e);
    };
    rec.onerror = () => {
      heard = null;
    };
    rec.onend = () => {
      // Stopped by a tap on the mic: nothing to send and nothing to explain.
      if (recognizer.current !== rec) return;
      recognizer.current = null;
      setListening(false);
      if (heard) void ask(heard);
      else setHint(NOT_HEARD);
    };
    recognizer.current = rec;
    setHint(null);
    setListening(true);
    rec.start();
  }

  async function ask(question: string) {
    const q = question.trim();
    if (!q || busy) return;
    setHint(null);
    setBusy(true);
    if (!voice.current && typeof Audio !== "undefined") voice.current = new Audio();
    try {
      const result = await api.ask(q);
      online();
      const { answer } = result;
      setHistory((h) => [{ id: nextId++, question: q, answer, tools: toolsOf(result) }, ...h]);
      setDraft("");
      playAnswer(voice.current, answer, result.audio);
    } catch (err) {
      report(err);
    } finally {
      setBusy(false);
    }
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    void ask(draft);
  }

  return (
    <div className="space-y-4">
      <form onSubmit={submit} className="flex items-center gap-2">
        <input
          aria-label="Question"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Ask about your fridge"
          enterKeyHint="send"
          className="min-h-12 min-w-0 flex-1 rounded-2xl border border-slate-200 bg-white px-4 text-base outline-none focus:border-brand-500 dark:border-slate-700 dark:bg-slate-900"
        />
        {Recognition && (
          <button
            type="button"
            aria-label={listening ? "Stop listening" : "Speak"}
            aria-pressed={listening}
            onClick={listen}
            className={`grid size-12 shrink-0 place-items-center rounded-2xl ${
              listening ? "bg-warm-600 text-white" : "bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-200"
            }`}
          >
            {listening ? <Square aria-hidden className="size-5" /> : <Mic aria-hidden className="size-5" />}
          </button>
        )}
        <button
          type="submit"
          aria-label="Send"
          disabled={busy}
          className="grid size-12 shrink-0 place-items-center rounded-2xl bg-brand-600 text-white disabled:opacity-50"
        >
          <Send aria-hidden className="size-5" />
        </button>
      </form>

      {listening && <p className="text-sm font-medium text-warm-600 dark:text-warm-400">Listening…</p>}
      {busy && <p className="text-sm font-medium text-brand-700 dark:text-brand-300">Thinking…</p>}
      {hint && <p className="text-sm text-slate-500 dark:text-slate-400">{hint}</p>}

      <div className="flex flex-wrap gap-2">
        {EXAMPLES.map((q) => (
          <button
            key={q}
            type="button"
            onClick={() => void ask(q)}
            disabled={busy}
            className="rounded-full bg-brand-50 px-3 py-1.5 text-sm font-medium text-brand-700 disabled:opacity-50 dark:bg-brand-950 dark:text-brand-300"
          >
            {q}
          </button>
        ))}
      </div>

      <ul aria-label="Answers" className="space-y-3">
        {history.map((x) => (
          <li key={x.id} className="rounded-3xl bg-white p-4 shadow-sm dark:bg-slate-900">
            <p className="text-sm text-slate-500 dark:text-slate-400">{x.question}</p>
            <p className="mt-1 text-lg font-medium">{x.answer}</p>
            {x.tools && (
              <p className="mt-2 break-words text-xs text-slate-500 dark:text-slate-400">
                Checked: {x.tools.join(", ")}
              </p>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
