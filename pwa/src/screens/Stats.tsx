import { useCallback, useMemo, useState } from "react";
import { Bar, BarChart, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis } from "recharts";
import type { DoorEvent } from "../api/types";
import { useApp } from "../AppContext";
import { plural } from "../format";
import { averageDuration, deviceTimeZone, perDay, perHour, todayCount } from "../stats";
import { usePolling } from "../usePolling";

const AXIS = { fontSize: 11, fill: "#64748b" };

export function Stats() {
  const { api, report, online } = useApp();
  const [events, setEvents] = useState<DoorEvent[] | null>(null);

  const load = useCallback(() => {
    api.events(7).then((r) => {
      setEvents(r.events);
      online();
    }, report);
  }, [api, report, online]);
  usePolling(load, 60_000);

  const stats = useMemo(() => {
    const list = events ?? [];
    const tz = deviceTimeZone();
    const now = new Date();
    return {
      today: todayCount(list, now, tz),
      week: list.length,
      average: averageDuration(list),
      days: perDay(list, now, tz),
      hours: perHour(list, tz),
    };
  }, [events]);

  if (!events) return <div aria-hidden className="h-64 animate-pulse rounded-3xl bg-slate-200/70 dark:bg-slate-800" />;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3">
        <Tile label="Today" value={String(stats.today)} accent />
        <Tile label="Last 7 days" value={String(stats.week)} />
        <Tile label="Average open time" short="Avg. open" value={stats.average === null ? "–" : `${stats.average} s`} />
      </div>
      <Chart title="Opens per day">
        <div className="h-44">
          <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 320, height: 176 }}>
            <BarChart data={stats.days} margin={{ top: 20, right: 0, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id="bar-day" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" style={{ stopColor: "var(--color-brand-300)", stopOpacity: 0.55 }} />
                  <stop offset="100%" style={{ stopColor: "var(--color-brand-300)", stopOpacity: 0.2 }} />
                </linearGradient>
                <linearGradient id="bar-today" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" style={{ stopColor: "var(--color-brand-400)" }} />
                  <stop offset="100%" style={{ stopColor: "var(--color-brand-700)" }} />
                </linearGradient>
              </defs>
              <XAxis dataKey="label" tick={AXIS} tickLine={false} axisLine={false} />
              <Tooltip cursor={{ fill: "rgba(148,163,184,0.12)", radius: 8 }} />
              <Bar dataKey="opens" name="Opens" radius={[8, 8, 8, 8]} isAnimationActive={false} minPointSize={4}>
                {stats.days.map((d) => (
                  <Cell key={d.date} fill={d.isToday ? "url(#bar-today)" : "url(#bar-day)"} />
                ))}
                <LabelList dataKey="opens" position="top" style={{ fontSize: 12, fontWeight: 700, fill: "#64748b" }} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Chart>
      <Chart title="Opens by hour">
        <HourStrip hours={stats.hours} />
      </Chart>
    </div>
  );
}

/** 24 cells, one per hour, shaded by how many openings fell in it. */
function HourStrip({ hours }: { hours: number[] }) {
  const max = Math.max(1, ...hours);
  return (
    <div>
      <ul className="grid grid-cols-[repeat(24,minmax(0,1fr))] gap-0.5">
        {hours.map((opens, hour) => {
          const hh = String(hour).padStart(2, "0");
          return (
            <li
              key={hour}
              aria-label={`${hh}:00, ${plural(opens, "open")}`}
              title={`${hh}:00 · ${plural(opens, "open")}`}
              className={`h-12 rounded-[4px] ${opens === 0 ? "bg-slate-100 dark:bg-slate-800" : "bg-brand-500"}`}
              style={opens === 0 ? undefined : { opacity: 0.25 + 0.75 * (opens / max) }}
            />
          );
        })}
      </ul>
      <div aria-hidden className="mt-1.5 grid grid-cols-4 text-[11px] text-slate-500 dark:text-slate-400">
        {["00", "06", "12", "18"].map((h) => (
          <span key={h}>{h}:00</span>
        ))}
      </div>
    </div>
  );
}

function Tile({ label, value, short, accent }: { label: string; value: string; short?: string; accent?: boolean }) {
  return (
    <div
      role="group"
      aria-label={label}
      className={`rounded-2xl p-3 ring-1 ${
        accent
          ? "bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow-md shadow-brand-900/20 ring-brand-600"
          : "bg-white ring-slate-200 dark:bg-slate-900 dark:ring-slate-800"
      }`}
    >
      <p
        aria-hidden
        className={`truncate text-xs font-semibold ${accent ? "text-brand-50/85" : "text-slate-500 dark:text-slate-400"}`}
      >
        {short ?? label}
      </p>
      <p className="mt-1 text-2xl font-bold tabular-nums tracking-tight">{value}</p>
    </div>
  );
}

function Chart({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <figure
      aria-label={title}
      className="rounded-2xl bg-white p-4 shadow-sm shadow-slate-900/5 ring-1 ring-slate-200 dark:bg-slate-900 dark:shadow-none dark:ring-slate-800"
    >
      <figcaption className="mb-3 text-sm font-bold">{title}</figcaption>
      {children}
    </figure>
  );
}
