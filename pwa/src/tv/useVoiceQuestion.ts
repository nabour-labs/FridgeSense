import { useEffect, useRef, useState } from "react";
import type { Api } from "../AppContext";
import { finalTranscript, newRecognizer, playAnswer, recognizerClass, type Recognizer } from "../voice";

/** How long an answer (or a "try again") stays on the TV. */
export const ANSWER_MS = 20_000;

export type VoiceState =
  | { kind: "idle" }
  | { kind: "listening" }
  | { kind: "thinking"; question: string }
  | { kind: "answered"; question: string; answer: string }
  | { kind: "error"; message: string; question?: string };

export const NOT_HEARD = "Didn't catch that. Try again.";
export const ASK_FAILED = "Couldn't get an answer. Try again.";

/**
 * One spoken question at a time for the TV: press to listen, press again to stop. What is heard
 * goes to POST /api/ask; the answer is played (Polly audio, else speech synthesis) and shown for
 * ANSWER_MS. `available` is false where the browser has no speech recognition.
 */
export function useVoiceQuestion(api: Api) {
  const Recognition = recognizerClass();
  const [state, setState] = useState<VoiceState>({ kind: "idle" });
  const recognizer = useRef<Recognizer | null>(null);
  // Created on the first press, so the press unlocks playback.
  const voice = useRef<HTMLAudioElement | null>(null);
  // Bumped by each new question, so a late answer to an older one is dropped.
  const asked = useRef(0);

  // Answers and "try again" hide after a while.
  useEffect(() => {
    if (state.kind !== "answered" && state.kind !== "error") return;
    const timer = setTimeout(() => setState({ kind: "idle" }), ANSWER_MS);
    return () => clearTimeout(timer);
  }, [state]);

  // Leaving the dashboard ends listening and speaking, and sends nothing.
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

  async function ask(question: string) {
    const id = ++asked.current;
    setState({ kind: "thinking", question });
    try {
      const result = await api.ask(question);
      if (id !== asked.current) return;
      setState({ kind: "answered", question, answer: result.answer });
      playAnswer(voice.current, result.answer, result.audio);
    } catch {
      if (id === asked.current) setState({ kind: "error", message: ASK_FAILED, question });
    }
  }

  function press() {
    if (!Recognition) return;
    if (recognizer.current) {
      // Stopped by a press: nothing to send and nothing to explain.
      const current = recognizer.current;
      recognizer.current = null;
      setState({ kind: "idle" });
      current.stop();
      return;
    }
    if (!voice.current && typeof Audio !== "undefined") voice.current = new Audio();
    asked.current++;
    const rec = newRecognizer(Recognition);
    let heard: string | null = null;
    rec.onresult = (e) => {
      if (heard === null) heard = finalTranscript(e);
    };
    rec.onerror = () => {
      heard = null;
    };
    rec.onend = () => {
      if (recognizer.current !== rec) return;
      recognizer.current = null;
      if (heard) void ask(heard);
      else setState({ kind: "error", message: NOT_HEARD });
    };
    recognizer.current = rec;
    setState({ kind: "listening" });
    rec.start();
  }

  return { available: Boolean(Recognition), state, press };
}
