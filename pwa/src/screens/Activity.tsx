import { ArrowDownRight, ArrowUpRight, Bug, ChevronLeft, ChevronRight, Clock, DoorClosed, Trash2, Video } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type MutableRefObject } from "react";
import type { Change, DoorEvent } from "../api/types";
import { canEdit, isAdmin, useApp } from "../AppContext";
import { EmptyState } from "../components/EmptyState";
import { LiveStream } from "../components/LiveStream";
import { NoData } from "../components/NoData";
import { Sheet } from "../components/Sheet";
import { changeLabel, clock, dayLabel } from "../format";
import { useLoad } from "../useLoad";

/** Presigned still links last 15 min; reuse them for 10 so a poll doesn't reload every image. */
const STILL_LINKS_REUSED_MS = 10 * 60_000;
const PAGE_SIZE = 10;

type StillLinks = Map<string, { stills: string[]; at: number }>;

function startOfDay(d: Date, plusDays = 0): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate() + plusDays);
}

/** "2026-10-15" in local time, the value of a date input. */
function dateValue(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function Activity() {
  const stillLinks = useRef<StillLinks>(new Map());
  const [day, setDay] = useState(() => startOfDay(new Date()));
  /** The cursor of each page so far; the last one is the page shown. */
  const [cursors, setCursors] = useState<(string | undefined)[]>([undefined]);
  const picker = useRef<HTMLInputElement>(null);
  const [watching, setWatching] = useState(false);
  const today = dateValue(new Date());
  /** Set when the user changes page, so the new page opens at its top once it has loaded. */
  const jumpUp = useRef(false);
  const showPage = (next: (string | undefined)[]) => {
    jumpUp.current = true;
    setCursors(next);
  };

  const pickDay = (value: string) => {
    const [y, m, d] = value.split("-").map(Number);
    if (!y || !m || !d || value > today) return;
    setDay(new Date(y, m - 1, d));
    setCursors([undefined]);
  };

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <input
          ref={picker}
          type="date"
          aria-label="Day"
          value={dateValue(day)}
          max={today}
          onChange={(e) => pickDay(e.target.value)}
          className="h-11 min-w-0 flex-1 scroll-mt-24 rounded-xl border border-slate-300 bg-white px-3 font-semibold outline-none [color-scheme:light] focus:border-brand-500 focus:ring-4 focus:ring-brand-500/15 dark:border-slate-700 dark:bg-slate-950 dark:[color-scheme:dark]"
        />
        <button
          onClick={() => setWatching(true)}
          className="flex h-11 shrink-0 items-center gap-2 rounded-xl bg-brand-600 px-4 font-semibold text-white transition hover:bg-brand-700 active:scale-[0.98]"
        >
          <Video aria-hidden className="size-5" />
          Livestream
        </button>
      </div>
      {watching && <LiveStream onClose={() => setWatching(false)} />}
      <EventPage
        key={`${dateValue(day)}/${cursors.at(-1) ?? ""}`}
        day={day}
        cursor={cursors.at(-1)}
        page={cursors.length}
        stillLinks={stillLinks}
        onOlder={(next) => showPage([...cursors, next])}
        onNewer={() => showPage(cursors.slice(0, -1))}
        onShown={() => {
          if (jumpUp.current) picker.current?.scrollIntoView?.({ block: "nearest" });
          jumpUp.current = false;
        }}
      />
    </div>
  );
}

function EventPage({
  day,
  cursor,
  page,
  stillLinks,
  onOlder,
  onNewer,
  onShown,
}: {
  day: Date;
  cursor: string | undefined;
  page: number;
  stillLinks: MutableRefObject<StillLinks>;
  onOlder: (next: string) => void;
  onNewer: () => void;
  /** The page's first load is on screen. */
  onShown: () => void;
}) {
  const { api, role, report } = useApp();
  const { data, setData, failed } = useLoad(
    useCallback(
      () =>
        api.eventsOn(day, startOfDay(day, 1), PAGE_SIZE, cursor).then((r) => ({
          next: r.next,
          events: r.events.map((e) => {
            const now = Date.now();
            const kept = stillLinks.current.get(e.id);
            if (kept && kept.stills.length === e.stills.length && now - kept.at < STILL_LINKS_REUSED_MS) {
              return { ...e, stills: kept.stills };
            }
            stillLinks.current.set(e.id, { stills: e.stills, at: now });
            return e;
          }),
        })),
      [api, day, cursor, stillLinks],
    ),
    10_000,
  );
  const [viewing, setViewing] = useState<{ stills: string[]; index: number } | null>(null);
  const [deleting, setDeleting] = useState<DoorEvent | null>(null);
  const [busy, setBusy] = useState(false);
  const shown = data !== null;
  useEffect(() => {
    if (shown) onShown();
  }, [shown]); // onShown changes every render; only the first load counts

  if (!data) {
    if (failed) return <NoData />;
    return <div aria-hidden data-testid="loading" className="h-40 animate-pulse rounded-3xl bg-slate-200/70 dark:bg-slate-800" />;
  }

  const remove = (id: string) => {
    setBusy(true);
    api
      .deleteEvent(id)
      .then(() => setData((d) => d && { ...d, events: d.events.filter((e) => e.id !== id) }), report)
      .finally(() => {
        setBusy(false);
        setDeleting(null);
      });
  };

  const { events, next } = data;
  const days = new Map<string, DoorEvent[]>();
  for (const e of events) days.set(dayLabel(e.opened_at), [...(days.get(dayLabel(e.opened_at)) ?? []), e]);
  const pagerButton =
    "flex h-11 items-center gap-1 rounded-full bg-slate-100 px-4 text-sm font-semibold text-slate-700 transition hover:bg-slate-200 active:scale-95 disabled:opacity-30 dark:bg-slate-800 dark:text-slate-200";

  return (
    <div className="space-y-6">
      {events.length === 0 && (
        <EmptyState
          Icon={DoorClosed}
          title="No door openings on this day."
          hint="Each time the fridge opens, it shows up here."
        />
      )}
      {[...days].map(([label, dayEvents]) => (
        <section key={label} aria-label={label}>
          <h2 className="mb-2 px-1 text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
            {label}
          </h2>
          <ol className="space-y-3">
            {dayEvents.map((e) => (
              <li key={e.id}>
                <EventCard
                  event={e}
                  onStill={(index) => setViewing({ stills: e.stills, index })}
                  onDelete={canEdit(role) ? () => setDeleting(e) : undefined}
                  debug={isAdmin(role)}
                />
              </li>
            ))}
          </ol>
        </section>
      ))}
      {(events.length > 0 || page > 1) && (
        <nav aria-label="Pages" className="flex items-center justify-between">
          <button type="button" disabled={page === 1} onClick={onNewer} className={pagerButton}>
            <ChevronLeft aria-hidden className="size-4" />
            Newer
          </button>
          <span className="text-sm font-semibold text-slate-500 dark:text-slate-400">Page {page}</span>
          <button type="button" disabled={!next} onClick={() => next && onOlder(next)} className={pagerButton}>
            Older
            <ChevronRight aria-hidden className="size-4" />
          </button>
        </nav>
      )}
      {viewing && (
        <StillViewer
          stills={viewing.stills}
          index={viewing.index}
          onIndex={(index) => setViewing({ ...viewing, index })}
          onClose={() => setViewing(null)}
        />
      )}
      {deleting && (
        <Sheet title="Delete this door opening?" onClose={() => setDeleting(null)}>
          <p className="text-sm text-slate-600 dark:text-slate-300">
            The {clock(deleting.opened_at)} opening and its unconfirmed changes go away. Fridge quantities stay as
            they are.
          </p>
          <div className="mt-5 grid grid-cols-2 gap-3">
            <button
              type="button"
              onClick={() => setDeleting(null)}
              className="h-12 rounded-xl bg-slate-100 font-semibold text-slate-700 transition hover:bg-slate-200 active:scale-[0.98] dark:bg-slate-800 dark:text-slate-200"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => remove(deleting.id)}
              className="h-12 rounded-xl bg-red-600 font-semibold text-white transition hover:bg-red-700 active:scale-[0.98] disabled:opacity-50"
            >
              Delete
            </button>
          </div>
        </Sheet>
      )}
    </div>
  );
}

function stillTitle(index: number, count: number) {
  return `Still ${index + 1} of ${count}`;
}

function EventCard({
  event,
  onStill,
  onDelete,
  debug = false,
}: {
  event: DoorEvent;
  onStill: (index: number) => void;
  /** Absent for viewers. */
  onDelete?: () => void;
  /** Link to the opening's debug trace (owner only: traces hold unblurred stills). */
  debug?: boolean;
}) {
  const shown = event.changes.filter((c) => !c.rejected);
  const quiet = "text-sm text-slate-500 dark:text-slate-400";
  return (
    <article className="rounded-2xl bg-white p-4 shadow-sm shadow-slate-900/5 ring-1 ring-slate-200 dark:bg-slate-900 dark:shadow-none dark:ring-slate-800">
      <header className="flex items-center justify-between text-sm">
        <span className="text-lg font-bold tabular-nums tracking-tight">{clock(event.opened_at)}</span>
        <span className="flex items-center gap-1">
          <span className="flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600 dark:bg-slate-800 dark:text-slate-300">
            <Clock aria-hidden className="size-3.5" />
            <span>{event.duration_s} s</span>
          </span>
          {debug && (
            <a
              href={`#config/debug/${encodeURIComponent(event.id)}`}
              aria-label={`Debug door opening at ${clock(event.opened_at)}`}
              title="Debug"
              className="grid size-9 place-items-center rounded-full text-slate-500 transition hover:bg-slate-100 hover:text-slate-800 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-100"
            >
              <Bug aria-hidden className="size-4" />
            </a>
          )}
          {onDelete && (
            <button
              type="button"
              aria-label={`Delete door opening at ${clock(event.opened_at)}`}
              onClick={onDelete}
              className="-mr-2 grid size-9 place-items-center rounded-full text-slate-500 transition hover:bg-red-50 hover:text-red-600 dark:text-slate-400 dark:hover:bg-red-950/50 dark:hover:text-red-400"
            >
              <Trash2 aria-hidden className="size-4" />
            </button>
          )}
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
            key={i}
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
