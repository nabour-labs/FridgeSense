import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { useApp } from "../AppContext";
import type { DoorEvent } from "../api/types";
import { titleCase } from "../format";
import { deviceTimeZone } from "../stats";
import { useLoad } from "../useLoad";
import { cameraLine, clockTime, fridgeRows, heatCells, opensSummary, outOfStock, recentRows, tvIcon } from "./tv";

const INVENTORY_MS = 10_000;
const EVENTS_MS = 30_000;
// Each camera read also calls Ring, so it refreshes far less often.
const CAMERA_MS = 300_000;
// Four weeks of openings, for the heatmap; the rest uses the last 7 days.
const EVENT_DAYS = 28;

/**
 * The kitchen TV: the camera's status, what is in the fridge, the latest door openings and when
 * the door gets opened, read-only and sized for 1920×1080 across a room. No pictures, nothing to
 * select, no pointer, no key handling, so Back reaches the Fire TV app.
 */
export function TvDashboard() {
  const { api } = useApp();
  const inventory = useLoad(
    useCallback(() => api.inventory(), [api]),
    INVENTORY_MS,
  );
  const events = useLoad(
    useCallback(() => api.events(EVENT_DAYS).then((r) => r.events), [api]),
    EVENTS_MS,
  );
  const camera = useLoad(
    useCallback(() => api.camera(), [api]),
    CAMERA_MS,
  );
  const updated = useUpdatedAt(inventory.data, events.data);
  return (
    <section
      aria-label="TV dashboard"
      // The Fire TV WebView draws a pointer for the remote; there is nothing to point at.
      style={{ cursor: "none" }}
      className="dark flex h-dvh flex-col gap-[2vw] overflow-hidden bg-slate-950 p-[3vw] text-slate-100"
    >
      <header className="space-y-2">
        <div className="flex items-baseline justify-between">
          <h1 className="text-4xl font-bold tracking-tight">FridgeSense</h1>
          {updated && <p className="text-2xl tabular-nums text-slate-400">Updated {updated}</p>}
        </div>
        <p className="text-2xl text-slate-300">
          {camera.data ? cameraLine(camera.data) : camera.failed ? "Camera: No Data" : "\u00a0"}
        </p>
      </header>
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

/** Local clock time of the latest successful inventory or events load; null before either. */
function useUpdatedAt(...data: unknown[]): string | null {
  const [at, setAt] = useState<string | null>(null);
  useEffect(() => {
    if (data.some((d) => d !== undefined && d !== null)) setAt(clockTime(new Date().toISOString(), deviceTimeZone()));
  }, data);
  return at;
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
  const out = outOfStock(items);
  return (
    <div className="flex h-full flex-col justify-between gap-6">
      {rows.empty ? <p className="text-3xl text-slate-400">The fridge is empty</p> : <FridgeGroups rows={rows} />}
      {out && <p className="text-2xl font-semibold text-rose-300">{out}</p>}
    </div>
  );
}

function FridgeGroups({ rows }: { rows: ReturnType<typeof fridgeRows> }) {
  return (
    <div className="min-h-0 columns-2 gap-[2vw]">
      {rows.groups.map((g) => (
        <div key={g.category} className="mb-6 break-inside-avoid">
          <h3 id={`tv-${g.category}`} className="mb-2 text-xl font-bold uppercase tracking-wider text-slate-500">
            {titleCase(g.category)}
          </h3>
          <ul aria-labelledby={`tv-${g.category}`} className="space-y-2">
            {g.items.map((item) => (
              <li key={item.key} className="flex items-center gap-3 text-3xl">
                <span aria-hidden>{tvIcon(item.name, item.category)}</span>
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
  const rows = recentRows(events, Date.now(), deviceTimeZone());
  if (rows.length === 0) return <p className="text-3xl text-slate-400">No door openings this week</p>;
  return (
    <ol className="space-y-5">
      {rows.map((r) => (
        <li key={r.id} className="space-y-1">
          <p className="text-xl font-semibold tabular-nums text-slate-400">{r.when}</p>
          <p className="text-3xl font-semibold">
            {r.state === "checking"
              ? "Checking…"
              : r.state === "none"
                ? r.count > 1
                  ? `${r.count} openings · No changes`
                  : "No changes"
                : r.labels.join(", ")}
          </p>
        </li>
      ))}
    </ol>
  );
}

function Opens({ events }: { events: DoorEvent[] }) {
  const tz = deviceTimeZone();
  const summary = useMemo(() => opensSummary(events, new Date(), tz), [events, tz]);
  const cells = useMemo(() => heatCells(events, tz), [events, tz]);
  const max = Math.max(1, ...summary.days.map((d) => d.opens));
  return (
    <div className="flex h-full flex-col gap-5">
      <div className="space-y-1">
        <p className="text-5xl font-bold tabular-nums">{summary.label}</p>
        {summary.openTime && <p className="text-2xl tabular-nums text-slate-300">{summary.openTime}</p>}
      </div>
      <ol aria-label="Opens per day" className="flex min-h-0 flex-1 items-end gap-3">
        {summary.days.map((d) => (
          <li key={d.date} aria-label={`${d.label}: ${d.opens}`} className="flex h-full flex-1 flex-col items-center justify-end gap-1">
            <span className="text-lg tabular-nums text-slate-300">{d.opens}</span>
            <span
              aria-hidden
              className={`w-full rounded-t-lg ${d.isToday ? "bg-brand-400" : "bg-slate-600"}`}
              style={{ height: `${(d.opens / max) * 60}%`, minHeight: "0.25rem" }}
            />
            <span className="text-lg text-slate-400">{d.label}</span>
          </li>
        ))}
      </ol>
      <Heatmap cells={cells} />
    </div>
  );
}

// Level 0–4, as on the Stats screen, on a dark background.
const HEAT = ["bg-slate-800", "bg-brand-900", "bg-brand-700", "bg-brand-500", "bg-brand-300"];
const DAY_LABELS = ["S", "M", "T", "W", "T", "F", "S"];

function Heatmap({ cells }: { cells: ReturnType<typeof heatCells> }) {
  return (
    <figure aria-label="Opens by day and hour" className="space-y-1">
      <figcaption className="text-lg text-slate-400">Opens by day and hour · 4 weeks</figcaption>
      <div className="grid grid-cols-[auto_repeat(24,minmax(0,1fr))] gap-[2px]">
        {cells.map((row, day) => [
          <span key={`d${day}`} aria-hidden className="pr-1 text-sm leading-none text-slate-500">
            {DAY_LABELS[day]}
          </span>,
          ...row.map((c, hour) => (
            <span key={`${day}-${hour}`} role="img" aria-label={c.label} className={`aspect-square rounded-[2px] ${HEAT[c.level]}`} />
          )),
        ])}
      </div>
    </figure>
  );
}
