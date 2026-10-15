import { ChartColumn, History, ListChecks, Mic, Refrigerator, WifiOff } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiClient, ApiError, Offline, ReadOnly, Unauthorized } from "./api/client";
import { AppContext, type Api, type Tab } from "./AppContext";
import { Activity } from "./screens/Activity";
import { Ask } from "./screens/Ask";
import { Fridge } from "./screens/Fridge";
import { Review } from "./screens/Review";
import { Stats } from "./screens/Stats";
import { SignIn } from "./screens/SignIn";
import { clearSession, loadSession, saveSession, type StoredSession } from "./session";

const TABS: { id: Tab; label: string; Icon: typeof Refrigerator }[] = [
  { id: "fridge", label: "Fridge", Icon: Refrigerator },
  { id: "activity", label: "Activity", Icon: History },
  { id: "review", label: "Review", Icon: ListChecks },
  { id: "stats", label: "Stats", Icon: ChartColumn },
  { id: "ask", label: "Ask", Icon: Mic },
];

function tabFromHash(): Tab {
  const id = location.hash.replace("#", "");
  return TABS.some((t) => t.id === id) ? (id as Tab) : "fridge";
}

export default function App({ api: injected }: { api?: Api }) {
  const [session, setSession] = useState<StoredSession | null>(loadSession);
  const api = useMemo<Api>(
    () => injected ?? new ApiClient(() => loadSession()?.token ?? null),
    [injected],
  );
  const [tab, setTab] = useState<Tab>(tabFromHash);
  const [offline, setOffline] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    const onHash = () => setTab(tabFromHash());
    addEventListener("hashchange", onHash);
    return () => removeEventListener("hashchange", onHash);
  }, []);

  // Ask for the passcode again once the session expires, without waiting for a 401.
  useEffect(() => {
    if (!session) return;
    const check = () => {
      if (!loadSession()) setSession(null);
    };
    const t = setInterval(check, 30_000);
    document.addEventListener("visibilitychange", check);
    return () => {
      clearInterval(t);
      document.removeEventListener("visibilitychange", check);
    };
  }, [session]);

  useEffect(() => {
    if (!notice) return;
    const t = setTimeout(() => setNotice(null), 3000);
    return () => clearTimeout(t);
  }, [notice]);

  const report = useCallback((error: unknown) => {
    if (error instanceof Unauthorized) {
      clearSession();
      setSession(null);
    } else if (error instanceof Offline) {
      setOffline(true);
    } else if (error instanceof ReadOnly) {
      setNotice("Read-only demo");
    } else if (error instanceof ApiError && error.status === 409) {
      // No camera linked yet: an expected state, the screens show "No Data".
    } else {
      console.error(error);
      setNotice("Something went wrong");
    }
  }, []);
  const online = useCallback(() => setOffline(false), []);
  const go = useCallback((next: Tab) => {
    location.hash = next;
    setTab(next);
  }, []);

  if (!session) {
    return (
      <SignIn
        api={api}
        onSignedIn={(s) => {
          const stored = { token: s.token, role: s.role, expiresAt: Date.parse(s.expires_at) };
          saveSession(stored);
          setSession(stored);
        }}
      />
    );
  }

  const current = TABS.find((t) => t.id === tab)!;
  return (
    <AppContext.Provider value={{ api, role: session.role, report, online, go }}>
      <div className="mx-auto flex min-h-dvh max-w-xl flex-col">
        <header className="sticky top-0 z-10 flex items-center justify-between gap-3 bg-slate-50/90 px-4 pb-3 pt-[max(1rem,env(safe-area-inset-top))] backdrop-blur dark:bg-slate-950/90">
          <h1 className="text-[1.75rem] font-bold tracking-tight">{current.label}</h1>
          {session.role === "viewer" && (
            <span className="rounded-full bg-violet-100 px-3 py-1 text-xs font-semibold text-violet-700 ring-1 ring-violet-200 dark:bg-violet-950 dark:text-violet-300 dark:ring-violet-900">
              Demo · read-only
            </span>
          )}
        </header>
        {offline && (
          <p className="mx-4 mb-3 flex animate-fade-in items-center gap-2 rounded-xl bg-warm-50 px-3 py-2 text-sm text-warm-800 ring-1 ring-warm-200 dark:bg-warm-950/60 dark:text-warm-200 dark:ring-warm-900">
            <WifiOff aria-hidden className="size-4 shrink-0" />
            Can't reach FridgeSense. Showing the last data.
          </p>
        )}
        <main key={tab} className="flex-1 animate-fade-up px-4 pb-28">
          {tab === "fridge" && <Fridge />}
          {tab === "activity" && <Activity />}
          {tab === "review" && <Review />}
          {tab === "stats" && <Stats />}
          {tab === "ask" && <Ask />}
        </main>
        {notice && (
          <p
            role="status"
            className="fixed inset-x-0 bottom-24 z-20 mx-auto w-fit animate-fade-up rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white shadow-lg dark:bg-white dark:text-slate-900"
          >
            {notice}
          </p>
        )}
        <nav
          aria-label="Screens"
          className="fixed inset-x-0 bottom-0 z-10 border-t border-slate-200/80 bg-white/85 pb-[env(safe-area-inset-bottom)] backdrop-blur-xl dark:border-slate-800/80 dark:bg-slate-900/85"
        >
          <ul className="mx-auto grid max-w-xl grid-cols-5 px-2">
            {TABS.map(({ id, label, Icon }) => (
              <li key={id}>
                <a
                  href={`#${id}`}
                  onClick={() => setTab(id)}
                  aria-current={tab === id ? "page" : undefined}
                  className={`group flex min-h-16 flex-col items-center justify-center gap-1 text-xs font-semibold transition active:scale-95 ${
                    tab === id ? "text-brand-700 dark:text-brand-300" : "text-slate-500 dark:text-slate-400"
                  }`}
                >
                  <span
                    className={`grid h-8 w-14 place-items-center rounded-full transition-colors ${
                      tab === id ? "bg-brand-100 dark:bg-brand-900/60" : "group-hover:bg-slate-100 dark:group-hover:bg-slate-800"
                    }`}
                  >
                    <Icon aria-hidden className="size-5" strokeWidth={tab === id ? 2.4 : 2} />
                  </span>
                  {label}
                </a>
              </li>
            ))}
          </ul>
        </nav>
      </div>
    </AppContext.Provider>
  );
}
