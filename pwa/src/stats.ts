/** Door-opening statistics, computed on the device in its own time zone. */

interface Opening {
  opened_at: string;
  duration_s: number;
}

export interface DayCount {
  date: string; // YYYY-MM-DD in the time zone
  label: string; // short weekday, e.g. "Thu"
  opens: number;
  isToday: boolean;
}

export function deviceTimeZone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone;
}

function dayKey(date: Date, timeZone: string): string {
  // en-CA formats as YYYY-MM-DD.
  return new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}

function hourOf(date: Date, timeZone: string): number {
  return Number(
    new Intl.DateTimeFormat("en-GB", { timeZone, hour: "2-digit", hourCycle: "h23" }).format(date),
  );
}

/** The last `days` days ending today, oldest first, with opens per day. */
export function perDay(events: Opening[], now: Date, timeZone: string, days = 7): DayCount[] {
  const [y, m, d] = dayKey(now, timeZone).split("-").map(Number);
  const counts = new Map<string, number>();
  for (const e of events) {
    const key = dayKey(new Date(e.opened_at), timeZone);
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return Array.from({ length: days }, (_, i) => {
    const day = new Date(Date.UTC(y, m - 1, d - (days - 1 - i)));
    const date = day.toISOString().slice(0, 10);
    const label = day.toLocaleDateString("en-US", { weekday: "short", timeZone: "UTC" });
    return { date, label, opens: counts.get(date) ?? 0, isToday: i === days - 1 };
  });
}

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

function weekdayOf(date: Date, timeZone: string): number {
  return WEEKDAYS.indexOf(new Intl.DateTimeFormat("en-US", { timeZone, weekday: "short" }).format(date));
}

/** Events that opened in the last `days` local days, today included. */
export function lastDays<T extends Opening>(events: T[], now: Date, timeZone: string, days: number): T[] {
  const first = perDay([], now, timeZone, days)[0].date;
  return events.filter((e) => dayKey(new Date(e.opened_at), timeZone) >= first);
}

/** Opens by weekday (rows, Sunday first) and hour of day (columns, 0–23). */
export function byWeekdayHour(events: Opening[], timeZone: string): number[][] {
  const grid = WEEKDAYS.map(() => Array(24).fill(0));
  for (const e of events) {
    const date = new Date(e.opened_at);
    grid[weekdayOf(date, timeZone)][hourOf(date, timeZone)] += 1;
  }
  return grid;
}

/** Shade level 0–4 for a heatmap cell; the busiest cell is always 4. */
export function heatLevel(opens: number, max: number): number {
  if (opens <= 0 || max <= 0) return 0;
  return Math.min(4, Math.ceil((4 * opens) / max));
}

export function todayCount(events: Opening[], now: Date, timeZone: string): number {
  const today = dayKey(now, timeZone);
  return events.filter((e) => dayKey(new Date(e.opened_at), timeZone) === today).length;
}

/** Average seconds the door stayed open, or null without events. */
export function averageDuration(events: Opening[]): number | null {
  if (events.length === 0) return null;
  return Math.round(events.reduce((sum, e) => sum + e.duration_s, 0) / events.length);
}

export interface DurationStats {
  average: number;
  longest: number;
  shortest: number;
}

/** Average (rounded), longest and shortest seconds open on one local day (YYYY-MM-DD), or null without openings. */
export function durationStats(events: Opening[], date: string, timeZone: string): DurationStats | null {
  const day = events.filter((e) => dayKey(new Date(e.opened_at), timeZone) === date);
  const average = averageDuration(day);
  if (average === null) return null;
  const seconds = day.map((e) => e.duration_s);
  return { average, longest: Math.max(...seconds), shortest: Math.min(...seconds) };
}
