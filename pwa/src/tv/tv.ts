/** What the TV dashboard shows, worked out from the API's inventory and door openings. */
import type { CameraInfo, DoorEvent, Item } from "../api/types";
import { ago, changeLabel, plural } from "../format";
import { itemIcon } from "../itemIcon";
import { byWeekdayHour, durationStats, heatLevel, lastDays, perDay, todayCount, type DayCount } from "../stats";

export const MAX_ITEMS = 12;
export const MAX_OPENINGS = 5;
export const MAX_OUT = 6;

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

export interface FridgeRows {
  groups: { category: string; items: Item[] }[];
  /** In-stock items left out to fit the screen. */
  more: number;
  empty: boolean;
}

/** In-stock items grouped by category (in the order categories first appear, as on the Fridge screen), capped. */
export function fridgeRows(items: Item[], max = MAX_ITEMS): FridgeRows {
  const inStock = items.filter((i) => i.quantity > 0);
  const groups = new Map<string, Item[]>();
  for (const item of inStock) groups.set(item.category, [...(groups.get(item.category) ?? []), item]);
  const ordered = [...groups.values()].flat();
  const shown = new Set(ordered.slice(0, max));
  return {
    groups: [...groups]
      .map(([category, all]) => ({ category, items: all.filter((i) => shown.has(i)) }))
      .filter((g) => g.items.length > 0),
    more: Math.max(0, ordered.length - max),
    empty: inStock.length === 0,
  };
}

/** "8:42 pm" in the given time zone. */
export function clockTime(iso: string, timeZone: string): string {
  return new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit", timeZone }).format(new Date(iso)).toLowerCase();
}

export interface RecentRow {
  id: string;
  /** "2 min ago · 8:42 pm · 12 s", for the row's newest opening. */
  when: string;
  state: "checking" | "none" | "changes";
  labels: string[];
  /** Openings in this row: above 1 when back-to-back no-change openings are collapsed. */
  count: number;
}

/**
 * The last 7 days' openings, newest first, with their changes as labels (rejected ones left out).
 * Back-to-back openings with no changes collapse into one row, before the first n rows are taken.
 */
export function recentRows(events: DoorEvent[], now: number, timeZone: string, n = MAX_OPENINGS): RecentRow[] {
  const rows: RecentRow[] = [];
  const week = lastDays(events, new Date(now), timeZone, 7);
  for (const e of [...week].sort((a, b) => Date.parse(b.opened_at) - Date.parse(a.opened_at))) {
    const labels = e.changes.filter((c) => !c.rejected).map(changeLabel);
    const state = e.status === "analyzing" ? "checking" : labels.length ? "changes" : "none";
    const last = rows.at(-1);
    if (state === "none" && last?.state === "none") {
      last.count += 1;
      continue;
    }
    const when = `${ago(e.opened_at, now)} · ${clockTime(e.opened_at, timeZone)} · ${Math.round(e.duration_s)} s`;
    rows.push({ id: e.id, when, state, labels, count: 1 });
  }
  return rows.slice(0, n);
}

/** "Out: milk, eggs" for items at quantity 0, at most max names; null when nothing is out. */
export function outOfStock(items: Item[], max = MAX_OUT): string | null {
  const out = items.filter((i) => i.quantity <= 0).map((i) => i.name);
  if (out.length === 0) return null;
  const more = out.length > max ? [`+${out.length - max} more`] : [];
  return `Out: ${[...out.slice(0, max), ...more].join(", ")}`;
}

export interface OpensSummary {
  today: number;
  label: string;
  /** "Avg 21 s · Longest 40 s" for today, or null with no openings today. */
  openTime: string | null;
  days: DayCount[];
}

/** Today's opens and open time, and the last 7 days, counted as on the Stats screen. */
export function opensSummary(events: DoorEvent[], now: Date, timeZone: string): OpensSummary {
  const week = lastDays(events, now, timeZone, 7);
  const today = todayCount(week, now, timeZone);
  const days = perDay(week, now, timeZone, 7);
  const date = days.find((d) => d.isToday)?.date;
  const time = date ? durationStats(week, date, timeZone) : null;
  return {
    today,
    label: `${plural(today, "open")} today`,
    openTime: time ? `Avg ${time.average} s · Longest ${time.longest} s` : null,
    days,
  };
}

export interface HeatCell {
  label: string;
  level: number;
}

function hourLabel(hour: number): string {
  return `${hour % 12 || 12} ${hour < 12 ? "am" : "pm"}`;
}

/** Opens by weekday (rows, Sunday first) and hour (24 columns), labelled and shaded as on the Stats screen. */
export function heatCells(events: DoorEvent[], timeZone: string): HeatCell[][] {
  const grid = byWeekdayHour(events, timeZone);
  const max = Math.max(0, ...grid.flat());
  return grid.map((row, day) =>
    row.map((opens, hour) => ({
      label: `${WEEKDAYS[day]} ${hourLabel(hour)}: ${plural(opens, "open")}`,
      level: heatLevel(opens, max),
    })),
  );
}

/** The camera's name, status, uptime and motion detection, joined by " · ". */
export function cameraLine(info: CameraInfo): string {
  const status = info.ring === "unavailable" || info.online == null ? "Status unknown" : info.online ? "Online" : "Offline";
  const parts = [info.name, status];
  if (info.monitoring?.paused) parts.push("Paused");
  if (info.ring !== "unavailable" && info.uptime.percent != null) parts.push(`${info.uptime.percent.toFixed(1)}% uptime`);
  if (info.ring !== "unavailable" && info.motion_detection != null)
    parts.push(`Motion detection ${info.motion_detection ? "on" : "off"}`);
  return parts.join(" · ");
}

// Newer emoji the Fire TV font can't draw, and older ones it can.
const TV_SAFE: Record<string, string> = { "🫙": "🧂", "🫑": "🌶️" };

/** The item's icon, with emoji the Fire TV can't draw swapped for ones it can. */
export function tvIcon(name: string, category: string): string {
  const icon = itemIcon(name, category);
  return TV_SAFE[icon] ?? icon;
}
