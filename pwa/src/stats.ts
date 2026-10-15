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

/** Opens by hour of day (0–23). */
export function perHour(events: Opening[], timeZone: string): number[] {
  const hours = Array(24).fill(0);
  for (const e of events) hours[hourOf(new Date(e.opened_at), timeZone)] += 1;
  return hours;
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
