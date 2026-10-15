import { Mic, Send, Square } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useApp } from "../AppContext";

const EXAMPLES = ["Do I have milk?", "What's in my fridge?", "When was the fridge last opened?"];

interface Exchange {
  id: number;
  question: string;
  answer: string;
}

function speak(text: string) {
  if (typeof speechSynthesis === "undefined") return;
  speechSynthesis.cancel();
  speechSynthesis.speak(new SpeechSynthesisUtterance(text));
}

type RecognizedResult = ArrayLike<{ transcript: string }> & { isFinal: boolean };

// The Web Speech API's recognizer, as far as this screen uses it (not in every TS DOM lib).
interface Recognizer {
  lang: string;
  interimResults: boolean;
  maxAlternatives: number;
  onresult: ((e: { resultIndex: number; results: ArrayLike<RecognizedResult> }) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort?(): void;
}

type RecognizerClass = new () => Recognizer;

function recognizerClass(): RecognizerClass | undefined {
  const w = window as unknown as Record<string, RecognizerClass | undefined>;
  return w.SpeechRecognition ?? w.webkitSpeechRecognition;
}

const NOT_HEARD = "Didn't catch that. Try again or type your question.";

let nextId = 0;

export function Ask() {
  const { api, report, online } = useApp();
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [history, setHistory] = useState<Exchange[]>([]);
  const [listening, setListening] = useState(false);
  const [hint, setHint] = useState<string | null>(null);
  const recognizer = useRef<Recognizer | null>(null);
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
    const rec = new Recognition();
    rec.lang = "en-US";
    rec.interimResults = false;
    rec.maxAlternatives = 1;
    let heard: string | null = null;
    rec.onresult = (e) => {
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const result = e.results[i];
        if (result.isFinal && heard === null) heard = result[0].transcript.trim() || null;
      }
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
    try {
      const { answer } = await api.ask(q);
      online();
      setHistory((h) => [{ id: nextId++, question: q, answer }, ...h]);
      setDraft("");
      speak(answer);
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
          </li>
        ))}
      </ul>
    </div>
  );
}
