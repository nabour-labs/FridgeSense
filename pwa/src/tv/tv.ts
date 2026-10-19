/** What the TV dashboard shows, worked out from the API's inventory and door openings. */
import type { DoorEvent, Item } from "../api/types";
import { ago, changeLabel, plural } from "../format";
import { perDay, todayCount, type DayCount } from "../stats";

export const MAX_ITEMS = 12;
export const MAX_OPENINGS = 5;

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

export interface RecentRow {
  id: string;
  ago: string;
  state: "checking" | "none" | "changes";
  labels: string[];
}

/** The newest openings, newest first, with their changes as labels; rejected changes are left out. */
export function recentRows(events: DoorEvent[], now: number, n = MAX_OPENINGS): RecentRow[] {
  return [...events]
    .sort((a, b) => Date.parse(b.opened_at) - Date.parse(a.opened_at))
    .slice(0, n)
    .map((e) => {
      const labels = e.changes.filter((c) => !c.rejected).map(changeLabel);
      const state = e.status === "analyzing" ? "checking" : labels.length ? "changes" : "none";
      return { id: e.id, ago: ago(e.opened_at, now), state, labels };
    });
}

export interface OpensSummary {
  today: number;
  label: string;
  days: DayCount[];
}

/** Today's opens and the last 7 days, counted as on the Stats screen. */
export function opensSummary(events: DoorEvent[], now: Date, timeZone: string): OpensSummary {
  const today = todayCount(events, now, timeZone);
  return { today, label: `${plural(today, "open")} today`, days: perDay(events, now, timeZone, 7) };
}
