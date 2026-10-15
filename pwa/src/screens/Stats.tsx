import { useCallback, useMemo } from "react";
import { Bar, BarChart, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis } from "recharts";
import { useApp } from "../AppContext";
import { NoData } from "../components/NoData";
import { plural } from "../format";
import { averageDuration, byWeekdayHour, deviceTimeZone, heatLevel, lastDays, perDay, todayCount } from "../stats";
import { useLoad } from "../useLoad";

const AXIS = { fontSize: 11, fill: "#64748b" };
const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const LEVELS = [
  "bg-slate-100 dark:bg-slate-800",
  "bg-brand-200 dark:bg-brand-900",
  "bg-brand-400 dark:bg-brand-700",
  "bg-brand-600 dark:bg-brand-500",
  "bg-brand-800 dark:bg-brand-300",
];

export function Stats() {
  const { api } = useApp();
  const { data: events, failed } = useLoad(
    useCallback(() => api.events(28).then((r) => r.events), [api]),
    60_000,
  );

  const stats = useMemo(() => {
    const all = events ?? [];
    const tz = deviceTimeZone();
    const now = new Date();
    const week = lastDays(all, now, tz, 7);
    return {
      today: todayCount(week, now, tz),
      week: week.length,
      average: averageDuration(week),
      days: perDay(week, now, tz),
      grid: byWeekdayHour(all, tz),
    };
  }, [events]);

  if (!events) {
    if (failed) return <NoData />;
    return <div aria-hidden data-testid="loading" className="h-64 animate-pulse rounded-3xl bg-slate-200/70 dark:bg-slate-800" />;
  }

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
      <Chart title="Opens by day and hour" note="Last 4 weeks">
        <Heatmap grid={stats.grid} />
      </Chart>
    </div>
  );
}

/** Weekday rows by hour columns, shaded in 5 levels like a contribution graph. */
function Heatmap({ grid }: { grid: number[][] }) {
  const max = Math.max(0, ...grid.flat());
  const label = "text-[10px] leading-none text-slate-500 dark:text-slate-400";
  return (
    <div>
      <div role="table" className="grid grid-cols-[auto_repeat(24,minmax(0,1fr))] gap-[2px]">
        <div role="row" className="contents">
          <span aria-hidden />
          {Array.from({ length: 24 }, (_, hour) => (
            <span key={hour} aria-hidden className={`${label} pb-1 ${hour % 6 === 0 ? "" : "invisible"}`}>
              {String(hour).padStart(2, "0")}
            </span>
          ))}
        </div>
        {grid.map((hours, day) => (
          <div key={day} role="row" className="contents">
            <span aria-hidden className={`${label} self-center pr-1.5 ${day % 2 === 1 ? "" : "invisible"}`}>
              {WEEKDAYS[day]}
            </span>
            {hours.map((opens, hour) => {
              const name = `${WEEKDAYS[day]} ${String(hour).padStart(2, "0")}:00, ${plural(opens, "open")}`;
              return (
                <span
                  key={hour}
                  role="cell"
                  aria-label={name}
                  title={name.replace(",", " ·")}
                  className={`aspect-square rounded-[3px] ${LEVELS[heatLevel(opens, max)]}`}
                />
              );
            })}
          </div>
        ))}
      </div>
      <div className={`${label} mt-2 flex items-center justify-end gap-[3px]`}>
        <span className="mr-1">Less</span>
        {LEVELS.map((level) => (
          <span key={level} aria-hidden className={`size-2.5 rounded-[3px] ${level}`} />
        ))}
        <span className="ml-1">More</span>
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

function Chart({ title, note, children }: { title: string; note?: string; children: React.ReactNode }) {
  return (
    <figure
      aria-label={title}
      className="rounded-2xl bg-white p-4 shadow-sm shadow-slate-900/5 ring-1 ring-slate-200 dark:bg-slate-900 dark:shadow-none dark:ring-slate-800"
    >
      <figcaption className="mb-3 flex items-baseline justify-between gap-2">
        <span className="text-sm font-bold">{title}</span>
        {note && <span className="text-xs text-slate-500 dark:text-slate-400">{note}</span>}
      </figcaption>
      {children}
    </figure>
  );
}
