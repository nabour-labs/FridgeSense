import { useCallback, useMemo, useState } from "react";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { DoorEvent } from "../api/types";
import { useApp } from "../AppContext";
import { averageDuration, deviceTimeZone, perDay, perHour, todayCount } from "../stats";
import { usePolling } from "../usePolling";

const SKY = "#0284c7";
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
      hours: perHour(list, tz).map((opens, hour) => ({ hour: String(hour), opens })),
    };
  }, [events]);

  if (!events) return <div aria-hidden className="h-64 animate-pulse rounded-3xl bg-slate-200/70 dark:bg-slate-800" />;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3">
        <Tile label="Today" value={String(stats.today)} />
        <Tile label="Last 7 days" value={String(stats.week)} />
        <Tile label="Average open time" short="Avg. open" value={stats.average === null ? "–" : `${stats.average} s`} />
      </div>
      <Chart title="Opens per day">
        <BarChart data={stats.days} margin={{ top: 8, right: 4, bottom: 0, left: -24 }}>
          <XAxis dataKey="label" tick={AXIS} tickLine={false} axisLine={false} />
          <YAxis allowDecimals={false} tick={AXIS} tickLine={false} axisLine={false} />
          <Tooltip cursor={{ fill: "rgba(148,163,184,0.15)" }} />
          <Bar dataKey="opens" name="Opens" fill={SKY} radius={[6, 6, 0, 0]} isAnimationActive={false} />
        </BarChart>
      </Chart>
      <Chart title="Opens by hour">
        <BarChart data={stats.hours} margin={{ top: 8, right: 4, bottom: 0, left: -24 }}>
          <XAxis dataKey="hour" tick={AXIS} tickLine={false} axisLine={false} interval={5} />
          <YAxis allowDecimals={false} tick={AXIS} tickLine={false} axisLine={false} />
          <Tooltip cursor={{ fill: "rgba(148,163,184,0.15)" }} labelFormatter={(h) => `${h}:00`} />
          <Bar dataKey="opens" name="Opens" fill={SKY} radius={[4, 4, 0, 0]} isAnimationActive={false} />
        </BarChart>
      </Chart>
    </div>
  );
}

function Tile({ label, value, short }: { label: string; value: string; short?: string }) {
  return (
    <div
      role="group"
      aria-label={label}
      className="rounded-2xl bg-white p-3 ring-1 ring-slate-200 dark:bg-slate-900 dark:ring-slate-800"
    >
      <p aria-hidden className="truncate text-xs font-medium text-slate-500 dark:text-slate-400">
        {short ?? label}
      </p>
      <p className="mt-1 text-2xl font-semibold tabular-nums tracking-tight">{value}</p>
    </div>
  );
}

function Chart({ title, children }: { title: string; children: React.ReactElement }) {
  return (
    <figure
      aria-label={title}
      className="rounded-2xl bg-white p-4 ring-1 ring-slate-200 dark:bg-slate-900 dark:ring-slate-800"
    >
      <figcaption className="mb-2 text-sm font-semibold">{title}</figcaption>
      <div className="h-44">
        <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 320, height: 176 }}>
          {children}
        </ResponsiveContainer>
      </div>
    </figure>
  );
}
