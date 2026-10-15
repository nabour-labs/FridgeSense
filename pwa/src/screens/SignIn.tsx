import { Snowflake } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Offline, Unauthorized } from "../api/client";
import type { Session } from "../api/types";
import type { Api } from "../AppContext";

export function SignIn({ api, onSignedIn }: { api: Api; onSignedIn: (s: Session) => void }) {
  const [passcode, setPasscode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onSignedIn(await api.signIn(passcode));
    } catch (err) {
      setError(
        err instanceof Unauthorized
          ? "Wrong passcode"
          : err instanceof Offline
            ? "Can't reach FridgeSense. Check your connection."
            : "Something went wrong. Try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="relative flex min-h-dvh items-center justify-center overflow-hidden px-4 py-10">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-80 bg-gradient-to-b from-brand-200/70 to-transparent dark:from-brand-900/40"
      />
      <form
        onSubmit={submit}
        className="relative w-full max-w-sm animate-fade-up rounded-3xl bg-white p-7 shadow-xl shadow-brand-900/5 ring-1 ring-slate-200 dark:bg-slate-900 dark:ring-slate-800"
      >
        <div className="mb-6 flex items-center gap-3">
          <span className="grid size-12 place-items-center rounded-2xl bg-gradient-to-br from-brand-400 to-brand-700 text-white shadow-md shadow-brand-700/30">
            <Snowflake aria-hidden className="size-6" />
          </span>
          <div>
            <h1 className="text-xl font-bold tracking-tight">FridgeSense</h1>
            <p className="text-sm text-slate-500 dark:text-slate-400">What's in your fridge, live.</p>
          </div>
        </div>
        <label htmlFor="passcode" className="mb-1.5 block text-sm font-medium">
          Passcode
        </label>
        <input
          id="passcode"
          type="password"
          autoComplete="current-password"
          value={passcode}
          onChange={(e) => setPasscode(e.target.value)}
          className="h-12 w-full rounded-xl border border-slate-300 bg-white px-3.5 text-base outline-none focus:border-brand-500 focus:ring-4 focus:ring-brand-500/15 dark:border-slate-700 dark:bg-slate-950"
          required
          autoFocus
        />
        {error && (
          <p role="alert" className="mt-2 text-sm font-medium text-rose-600 dark:text-rose-400">
            {error}
          </p>
        )}
        <button
          type="submit"
          disabled={busy}
          className="mt-5 h-12 w-full rounded-xl bg-brand-600 font-semibold text-white shadow-sm shadow-brand-700/30 transition hover:bg-brand-700 active:scale-[0.98] disabled:opacity-60"
        >
          Sign in
        </button>
      </form>
    </main>
  );
}
