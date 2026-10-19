import { useCallback, useMemo, type ReactNode } from "react";
import { useApp } from "../AppContext";
import type { DoorEvent } from "../api/types";
import { titleCase } from "../format";
import { itemIcon } from "../itemIcon";
import { deviceTimeZone } from "../stats";
import { useLoad } from "../useLoad";
import { fridgeRows, opensSummary, recentRows } from "./tv";

const INVENTORY_MS = 10_000;
const EVENTS_MS = 30_000;

/**
 * The kitchen TV: what is in the fridge, the latest door openings and today's opens, read-only
 * and sized for 1920×1080 across a room. No pictures, nothing to select, no key handling, so
 * Back reaches the Fire TV app.
 */
export function TvDashboard() {
  const { api } = useApp();
  const inventory = useLoad(
    useCallback(() => api.inventory(), [api]),
    INVENTORY_MS,
  );
  const events = useLoad(
    useCallback(() => api.events(7).then((r) => r.events), [api]),
    EVENTS_MS,
  );
  return (
    <section
      aria-label="TV dashboard"
      className="dark flex h-dvh flex-col gap-[2vw] overflow-hidden bg-slate-950 p-[3vw] text-slate-100"
    >
      <h1 className="text-4xl font-bold tracking-tight">FridgeSense</h1>
      <div className="grid min-h-0 flex-1 grid-cols-[1.4fr_1fr_1fr] gap-[2vw]">
        <Panel title="In the fridge">
          {inventory.data ? <Fridge items={inventory.data.items} /> : <Status failed={inventory.failed} />}
        </Panel>
        <Panel title="Recent changes">
          {events.data ? <Recent events={events.data} /> : <Status failed={events.failed} />}
        </Panel>
        <Panel title="Opens">{events.data ? <Opens events={events.data} /> : <Status failed={events.failed} />}</Panel>
      </div>
    </section>
  );
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section aria-label={title} className="flex min-h-0 flex-col gap-4 rounded-3xl bg-slate-900 p-[1.5vw] ring-1 ring-slate-800">
      <h2 className="text-2xl font-semibold uppercase tracking-wider text-slate-400">{title}</h2>
      <div className="min-h-0 flex-1 overflow-hidden">{children}</div>
    </section>
  );
}

function Status({ failed }: { failed: boolean }) {
  if (failed) return <p className="text-3xl text-slate-400">No Data</p>;
  return <div aria-hidden className="h-full animate-pulse rounded-2xl bg-slate-800" />;
}

function Fridge({ items }: { items: Parameters<typeof fridgeRows>[0] }) {
  const rows = fridgeRows(items);
  if (rows.empty) return <p className="text-3xl text-slate-400">The fridge is empty</p>;
  return (
    <div className="columns-2 gap-[2vw]">
      {rows.groups.map((g) => (
        <div key={g.category} className="mb-6 break-inside-avoid">
          <h3 id={`tv-${g.category}`} className="mb-2 text-xl font-bold uppercase tracking-wider text-slate-500">
            {titleCase(g.category)}
          </h3>
          <ul aria-labelledby={`tv-${g.category}`} className="space-y-2">
            {g.items.map((item) => (
              <li key={item.key} className="flex items-center gap-3 text-3xl">
                <span aria-hidden>{itemIcon(item.name, item.category)}</span>
                <span className="truncate font-semibold">{item.name}</span>
                <span className="ml-auto tabular-nums text-slate-400">×{item.quantity}</span>
              </li>
            ))}
          </ul>
        </div>
      ))}
      {rows.more > 0 && <p className="text-2xl font-semibold text-slate-400">+{rows.more} more</p>}
    </div>
  );
}

function Recent({ events }: { events: DoorEvent[] }) {
  const rows = recentRows(events, Date.now());
  if (rows.length === 0) return <p className="text-3xl text-slate-400">No door openings this week</p>;
  return (
    <ol className="space-y-5">
      {rows.map((r) => (
        <li key={r.id} className="space-y-1">
          <p className="text-xl font-semibold text-slate-400">{r.ago}</p>
          <p className="text-3xl font-semibold">
            {r.state === "checking" ? "Checking…" : r.state === "none" ? "No changes" : r.labels.join(", ")}
          </p>
        </li>
      ))}
    </ol>
  );
}

function Opens({ events }: { events: DoorEvent[] }) {
  const summary = useMemo(() => opensSummary(events, new Date(), deviceTimeZone()), [events]);
  const max = Math.max(1, ...summary.days.map((d) => d.opens));
  return (
    <div className="flex h-full flex-col gap-6">
      <p className="text-5xl font-bold tabular-nums">{summary.label}</p>
      <ol aria-label="Opens per day" className="flex min-h-0 flex-1 items-end gap-3">
        {summary.days.map((d) => (
          <li key={d.date} aria-label={`${d.label}: ${d.opens}`} className="flex h-full flex-1 flex-col items-center justify-end gap-2">
            <span className="text-xl tabular-nums text-slate-300">{d.opens}</span>
            <span
              aria-hidden
              className={`w-full rounded-t-xl ${d.isToday ? "bg-brand-400" : "bg-slate-600"}`}
              style={{ height: `${(d.opens / max) * 70}%`, minHeight: "0.25rem" }}
            />
            <span className="text-xl text-slate-400">{d.label}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}
