import { Clock } from "lucide-react";
import { useCallback, useState } from "react";
import type { Change, DoorEvent } from "../api/types";
import { useApp } from "../AppContext";
import { Sheet } from "../components/Sheet";
import { changeLabel, clock, dayLabel } from "../format";
import { usePolling } from "../usePolling";

export function Activity() {
  const { api, report, online } = useApp();
  const [events, setEvents] = useState<DoorEvent[] | null>(null);
  const [still, setStill] = useState<{ url: string; title: string } | null>(null);

  const load = useCallback(() => {
    api.events(7).then((r) => {
      setEvents(r.events);
      online();
    }, report);
  }, [api, report, online]);
  usePolling(load, 10_000);

  if (!events) return <div aria-hidden className="h-40 animate-pulse rounded-3xl bg-slate-200/70 dark:bg-slate-800" />;
  if (events.length === 0) {
    return (
      <p className="rounded-3xl border border-dashed border-slate-300 px-6 py-12 text-center text-slate-500 dark:border-slate-700 dark:text-slate-400">
        No door openings in the last 7 days.
      </p>
    );
  }

  const days = new Map<string, DoorEvent[]>();
  for (const e of events) days.set(dayLabel(e.opened_at), [...(days.get(dayLabel(e.opened_at)) ?? []), e]);

  return (
    <div className="space-y-6">
      {[...days].map(([day, dayEvents]) => (
        <section key={day} aria-label={day}>
          <h2 className="mb-2 px-1 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
            {day}
          </h2>
          <ol className="space-y-3">
            {dayEvents.map((e) => (
              <li key={e.id}>
                <EventCard event={e} onStill={(url, title) => setStill({ url, title })} />
              </li>
            ))}
          </ol>
        </section>
      ))}
      {still && (
        <Sheet title={still.title} onClose={() => setStill(null)}>
          <img src={still.url} alt={still.title} className="w-full rounded-2xl bg-slate-100 dark:bg-slate-800" />
        </Sheet>
      )}
    </div>
  );
}

function EventCard({ event, onStill }: { event: DoorEvent; onStill: (url: string, title: string) => void }) {
  const shown = event.changes.filter((c) => !c.rejected);
  return (
    <article className="rounded-2xl bg-white p-4 ring-1 ring-slate-200 dark:bg-slate-900 dark:ring-slate-800">
      <header className="flex items-center justify-between text-sm">
        <span className="text-base font-semibold tabular-nums">{clock(event.opened_at)}</span>
        <span className="flex items-center gap-1 text-slate-500 dark:text-slate-400">
          <Clock aria-hidden className="size-3.5" />
          <span>{event.duration_s} s</span>
        </span>
      </header>
      <div className="mt-2">
        {event.status === "analysis_failed" ? (
          <p className="text-sm text-slate-500 dark:text-slate-400">Couldn't tell what changed</p>
        ) : event.status === "analyzing" ? (
          <p className="text-sm text-slate-500 dark:text-slate-400">Looking at what changed…</p>
        ) : shown.length === 0 ? (
          <p className="text-sm text-slate-500 dark:text-slate-400">Nothing in or out</p>
        ) : (
          <ul className="flex flex-wrap gap-2">
            {shown.map((c, i) => (
              <li key={i}>
                <ChangeChip change={c} />
              </li>
            ))}
          </ul>
        )}
      </div>
      {event.stills.length > 0 && (
        <div className="mt-3 grid grid-cols-4 gap-2">
          {event.stills.map((url, i) => {
            const title = `Still ${i + 1} of ${event.stills.length}`;
            return (
              <button
                key={url}
                aria-label={title}
                onClick={() => onStill(url, title)}
                className="aspect-video overflow-hidden rounded-lg bg-slate-100 ring-1 ring-slate-200 dark:bg-slate-800 dark:ring-slate-700"
              >
                <img src={url} alt="" loading="lazy" className="size-full object-cover" />
              </button>
            );
          })}
        </div>
      )}
    </article>
  );
}

function ChangeChip({ change }: { change: Change }) {
  const added = change.direction === "added";
  const pending = !change.applied && !change.rejected;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-medium ${
        added
          ? "bg-emerald-50 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-200"
          : "bg-rose-50 text-rose-800 dark:bg-rose-950/60 dark:text-rose-200"
      }`}
    >
      <span>{changeLabel(change)}</span>
      {pending && (
        <span className="rounded-full bg-amber-200/70 px-1.5 text-[11px] text-amber-900 dark:bg-amber-900 dark:text-amber-100">
          to confirm
        </span>
      )}
    </span>
  );
}
