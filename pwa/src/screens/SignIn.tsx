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
    <main className="flex min-h-dvh items-center justify-center px-4 py-10">
      <form
        onSubmit={submit}
        className="w-full max-w-sm rounded-3xl bg-white p-7 shadow-sm ring-1 ring-slate-200 dark:bg-slate-900 dark:ring-slate-800"
      >
        <div className="mb-6 flex items-center gap-3">
          <span className="grid size-11 place-items-center rounded-2xl bg-sky-100 text-sky-700 dark:bg-sky-950 dark:text-sky-300">
            <Snowflake aria-hidden className="size-6" />
          </span>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">FridgeSense</h1>
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
          className="h-12 w-full rounded-xl border border-slate-300 bg-white px-3.5 text-base outline-none focus:border-sky-500 focus:ring-4 focus:ring-sky-500/15 dark:border-slate-700 dark:bg-slate-950"
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
          className="mt-5 h-12 w-full rounded-xl bg-sky-600 font-semibold text-white transition hover:bg-sky-700 disabled:opacity-60"
        >
          Sign in
        </button>
      </form>
    </main>
  );
}
