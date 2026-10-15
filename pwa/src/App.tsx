import { ChartColumn, History, ListChecks, Refrigerator, WifiOff } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiClient, Offline, ReadOnly, Unauthorized } from "./api/client";
import { AppContext, type Api, type Tab } from "./AppContext";
import { Activity } from "./screens/Activity";
import { Fridge } from "./screens/Fridge";
import { SignIn } from "./screens/SignIn";
import { clearSession, loadSession, saveSession, type StoredSession } from "./session";

const TABS: { id: Tab; label: string; Icon: typeof Refrigerator }[] = [
  { id: "fridge", label: "Fridge", Icon: Refrigerator },
  { id: "activity", label: "Activity", Icon: History },
  { id: "review", label: "Review", Icon: ListChecks },
  { id: "stats", label: "Stats", Icon: ChartColumn },
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
          const stored = { token: s.token, role: s.role };
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
          <h1 className="text-2xl font-semibold tracking-tight">{current.label}</h1>
          {session.role === "viewer" && (
            <span className="rounded-full bg-violet-100 px-3 py-1 text-xs font-semibold text-violet-700 dark:bg-violet-950 dark:text-violet-300">
              Demo · read-only
            </span>
          )}
        </header>
        {offline && (
          <p className="mx-4 mb-3 flex items-center gap-2 rounded-xl bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:bg-amber-950/60 dark:text-amber-200">
            <WifiOff aria-hidden className="size-4 shrink-0" />
            Can't reach FridgeSense. Showing the last data.
          </p>
        )}
        <main className="flex-1 px-4 pb-28">{tab === "fridge" && <Fridge />}
          {tab === "activity" && <Activity />}</main>
        {notice && (
          <p
            role="status"
            className="fixed inset-x-0 bottom-24 mx-auto w-fit rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white shadow-lg dark:bg-white dark:text-slate-900"
          >
            {notice}
          </p>
        )}
        <nav
          aria-label="Screens"
          className="fixed inset-x-0 bottom-0 border-t border-slate-200 bg-white/95 pb-[env(safe-area-inset-bottom)] backdrop-blur dark:border-slate-800 dark:bg-slate-900/95"
        >
          <ul className="mx-auto grid max-w-xl grid-cols-4">
            {TABS.map(({ id, label, Icon }) => (
              <li key={id}>
                <a
                  href={`#${id}`}
                  onClick={() => setTab(id)}
                  aria-current={tab === id ? "page" : undefined}
                  className={`flex min-h-14 flex-col items-center justify-center gap-0.5 text-xs font-medium ${
                    tab === id ? "text-sky-600 dark:text-sky-400" : "text-slate-500 dark:text-slate-400"
                  }`}
                >
                  <Icon aria-hidden className="size-5" />
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
