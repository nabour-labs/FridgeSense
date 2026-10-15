import { ArrowDownRight, ArrowUpRight, ChevronLeft, ChevronRight, Clock, DoorClosed } from "lucide-react";
import { useCallback, useState } from "react";
import type { Change, DoorEvent } from "../api/types";
import { useApp } from "../AppContext";
import { EmptyState } from "../components/EmptyState";
import { Sheet } from "../components/Sheet";
import { changeLabel, clock, dayLabel } from "../format";
import { usePolling } from "../usePolling";

export function Activity() {
  const { api, report, online } = useApp();
  const [events, setEvents] = useState<DoorEvent[] | null>(null);
  const [viewing, setViewing] = useState<{ stills: string[]; index: number } | null>(null);

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
      <EmptyState
        Icon={DoorClosed}
        title="No door openings in the last 7 days."
        hint="Each time the fridge opens, it shows up here."
      />
    );
  }

  const days = new Map<string, DoorEvent[]>();
  for (const e of events) days.set(dayLabel(e.opened_at), [...(days.get(dayLabel(e.opened_at)) ?? []), e]);

  return (
    <div className="space-y-6">
      {[...days].map(([day, dayEvents]) => (
        <section key={day} aria-label={day}>
          <h2 className="mb-2 px-1 text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
            {day}
          </h2>
          <ol className="space-y-3">
            {dayEvents.map((e) => (
              <li key={e.id}>
                <EventCard event={e} onStill={(index) => setViewing({ stills: e.stills, index })} />
              </li>
            ))}
          </ol>
        </section>
      ))}
      {viewing && (
        <StillViewer
          stills={viewing.stills}
          index={viewing.index}
          onIndex={(index) => setViewing({ ...viewing, index })}
          onClose={() => setViewing(null)}
        />
      )}
    </div>
  );
}

function stillTitle(index: number, count: number) {
  return `Still ${index + 1} of ${count}`;
}

function EventCard({ event, onStill }: { event: DoorEvent; onStill: (index: number) => void }) {
  const shown = event.changes.filter((c) => !c.rejected);
  const quiet = "text-sm text-slate-500 dark:text-slate-400";
  return (
    <article className="rounded-2xl bg-white p-4 shadow-sm shadow-slate-900/5 ring-1 ring-slate-200 dark:bg-slate-900 dark:shadow-none dark:ring-slate-800">
      <header className="flex items-center justify-between text-sm">
        <span className="text-lg font-bold tabular-nums tracking-tight">{clock(event.opened_at)}</span>
        <span className="flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600 dark:bg-slate-800 dark:text-slate-300">
          <Clock aria-hidden className="size-3.5" />
          <span>{event.duration_s} s</span>
        </span>
      </header>
      <div className="mt-2.5">
        {event.status === "analysis_failed" ? (
          <p className={quiet}>Couldn't tell what changed</p>
        ) : event.status === "analyzing" ? (
          <p className={`${quiet} animate-pulse`}>Looking at what changed…</p>
        ) : shown.length === 0 ? (
          <p className={quiet}>Nothing in or out</p>
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
      {event.stills.length > 0 && <Stills stills={event.stills} onStill={onStill} />}
    </article>
  );
}

/** The first still large, up to three more stacked beside it; "+N" on the last when there are more. */
function Stills({ stills, onStill }: { stills: string[]; onStill: (index: number) => void }) {
  const shown = stills.slice(0, 4);
  const extra = stills.length - shown.length;
  const rest = shown.length - 1;
  return (
    <div
      data-stills
      className={`mt-3 grid gap-1.5 overflow-hidden rounded-xl ${rest > 0 ? "grid-cols-3" : "grid-cols-1"}`}
      style={rest > 0 ? { gridTemplateRows: `repeat(${rest}, minmax(0, 1fr))` } : undefined}
    >
      {shown.map((url, i) => {
        const featured = i === 0;
        return (
          <button
            key={url}
            type="button"
            aria-label={stillTitle(i, stills.length)}
            data-featured={featured || undefined}
            onClick={() => onStill(i)}
            className={`relative overflow-hidden bg-slate-100 transition active:scale-[0.98] dark:bg-slate-800 ${
              featured ? `aspect-video ${rest > 0 ? "col-span-2" : ""}` : ""
            }`}
            style={featured && rest > 0 ? { gridRow: `span ${rest}` } : undefined}
          >
            <img src={url} alt="" loading="lazy" className="absolute inset-0 size-full object-cover" />
            {i === shown.length - 1 && extra > 0 && (
              <span className="absolute inset-0 grid place-items-center bg-slate-950/55 text-sm font-bold text-white">
                +{extra}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

function StillViewer({
  stills,
  index,
  onIndex,
  onClose,
}: {
  stills: string[];
  index: number;
  onIndex: (index: number) => void;
  onClose: () => void;
}) {
  const title = stillTitle(index, stills.length);
  const nav =
    "grid size-11 place-items-center rounded-full bg-slate-100 text-slate-700 transition hover:bg-slate-200 active:scale-95 disabled:opacity-30 dark:bg-slate-800 dark:text-slate-200";
  return (
    <Sheet title={title} onClose={onClose}>
      <img
        key={stills[index]}
        src={stills[index]}
        alt={title}
        className="aspect-video w-full animate-fade-in rounded-2xl bg-slate-100 object-cover dark:bg-slate-800"
      />
      <div className="mt-4 flex items-center justify-between">
        <button
          type="button"
          aria-label="Previous still"
          disabled={index === 0}
          onClick={() => onIndex(index - 1)}
          className={nav}
        >
          <ChevronLeft aria-hidden className="size-5" />
        </button>
        <div aria-hidden className="flex gap-1.5">
          {stills.map((url, i) => (
            <span
              key={url}
              className={`h-1.5 rounded-full transition-all ${
                i === index ? "w-5 bg-brand-500" : "w-1.5 bg-slate-300 dark:bg-slate-700"
              }`}
            />
          ))}
        </div>
        <button
          type="button"
          aria-label="Next still"
          disabled={index === stills.length - 1}
          onClick={() => onIndex(index + 1)}
          className={nav}
        >
          <ChevronRight aria-hidden className="size-5" />
        </button>
      </div>
    </Sheet>
  );
}

function ChangeChip({ change }: { change: Change }) {
  const added = change.direction === "added";
  const pending = !change.applied && !change.rejected;
  const Arrow = added ? ArrowUpRight : ArrowDownRight;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full py-1 pr-3 pl-1.5 text-sm font-semibold ring-1 ${
        added
          ? "bg-emerald-50 text-emerald-800 ring-emerald-200 dark:bg-emerald-950/60 dark:text-emerald-200 dark:ring-emerald-900"
          : "bg-rose-50 text-rose-800 ring-rose-200 dark:bg-rose-950/60 dark:text-rose-200 dark:ring-rose-900"
      }`}
    >
      <span
        aria-hidden
        className={`grid size-5 place-items-center rounded-full text-white ${added ? "bg-emerald-500" : "bg-rose-500"}`}
      >
        <Arrow className="size-3.5" strokeWidth={2.75} />
      </span>
      <span>{changeLabel(change)}</span>
      {pending && (
        <span className="rounded-full bg-warm-200/80 px-1.5 text-[11px] text-warm-900 dark:bg-warm-900 dark:text-warm-100">
          to confirm
        </span>
      )}
    </span>
  );
}
