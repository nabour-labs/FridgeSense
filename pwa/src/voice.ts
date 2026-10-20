// Speech in and out, shared by the Ask screen and the TV dashboard.

type RecognizedResult = ArrayLike<{ transcript: string }> & { isFinal: boolean };

// The Web Speech API's recognizer, as far as the app uses it (not in every TS DOM lib).
export interface Recognizer {
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

export type RecognizerClass = new () => Recognizer;

/** The browser's speech recognizer, or undefined where there is none. */
export function recognizerClass(): RecognizerClass | undefined {
  const w = window as unknown as Record<string, RecognizerClass | undefined>;
  return w.SpeechRecognition ?? w.webkitSpeechRecognition;
}

/** A new recognizer set up for one question: US English, final results only. */
export function newRecognizer(Recognition: RecognizerClass): Recognizer {
  const rec = new Recognition();
  rec.lang = "en-US";
  rec.interimResults = false;
  rec.maxAlternatives = 1;
  return rec;
}

/** The first final transcript in a result event, trimmed; null when there is none yet. */
export function finalTranscript(e: { resultIndex: number; results: ArrayLike<RecognizedResult> }): string | null {
  for (let i = e.resultIndex; i < e.results.length; i++) {
    const result = e.results[i];
    if (result.isFinal) return result[0].transcript.trim() || null;
  }
  return null;
}

/** Read text aloud with the browser's speech synthesis, where there is one. */
export function speak(text: string) {
  if (typeof speechSynthesis === "undefined") return;
  speechSynthesis.cancel();
  speechSynthesis.speak(new SpeechSynthesisUtterance(text));
}

/** Play an answer's voice audio (base64 mp3) in `el`; speech synthesis reads it when there is none or it won't play. */
export function playAnswer(el: HTMLAudioElement | null, answer: string, audio: string | null) {
  if (!audio || !el) return speak(answer);
  if (typeof speechSynthesis !== "undefined") speechSynthesis.cancel();
  el.src = `data:audio/mpeg;base64,${audio}`;
  try {
    Promise.resolve(el.play()).catch(() => speak(answer));
  } catch {
    speak(answer);
  }
}
