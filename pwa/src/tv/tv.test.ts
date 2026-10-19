import type { Change, DoorEvent, Item } from "../api/types";
import { fridgeRows, opensSummary, recentRows } from "./tv";

const TZ = "America/Toronto";
const NOW = new Date("2026-10-20T18:00:00Z"); // 14:00 in Toronto

function item(name: string, quantity: number, category: string): Item {
  return { key: name.replace(/ /g, "-"), name, category, quantity, last_changed_at: null };
}

function change(item: string, direction: "added" | "removed", quantity: number, extra: Partial<Change> = {}): Change {
  return { item, category: "dairy", direction, quantity, confidence: 0.9, applied: true, ...extra };
}

function event(opened_at: string, extra: Partial<DoorEvent> = {}): DoorEvent {
  return {
    id: opened_at,
    opened_at,
    closed_at: opened_at,
    duration_s: 20,
    status: "done",
    changes: [],
    pending_count: 0,
    stills: [],
    clip: null,
    ...extra,
  };
}

// Items by category
test("in-stock items are grouped by category in API order and out-of-stock items are left out", () => {
  const rows = fridgeRows([
    item("eggs", 6, "dairy"),
    item("apple", 3, "produce"),
    item("milk", 1, "dairy"),
    item("soda can", 0, "beverage"),
  ]);
  expect(rows.groups.map((g) => [g.category, g.items.map((i) => `${i.name} ×${i.quantity}`)])).toEqual([
    ["dairy", ["eggs ×6", "milk ×1"]],
    ["produce", ["apple ×3"]],
  ]);
  expect(rows.more).toBe(0);
  expect(rows.empty).toBe(false);
});

// More than fits
test("at most 12 items are shown, then the rest are counted", () => {
  const items = Array.from({ length: 15 }, (_, i) => item(`item ${i + 1}`, 1, i < 10 ? "dairy" : "produce"));
  const rows = fridgeRows(items);
  expect(rows.groups.flatMap((g) => g.items)).toHaveLength(12);
  expect(rows.groups.map((g) => g.items.length)).toEqual([10, 2]);
  expect(rows.more).toBe(3);
});

// Empty fridge
test("a fridge with nothing in stock is empty", () => {
  const rows = fridgeRows([item("soda can", 0, "beverage")]);
  expect(rows).toEqual({ groups: [], more: 0, empty: true });
});

// Newest five
test("the 5 newest openings are listed, newest first", () => {
  const events = [1, 7, 3, 5, 2, 6, 4].map((h) => event(`2026-10-20T${String(10 + h).padStart(2, "0")}:00:00Z`));
  const rows = recentRows(events, NOW.getTime());
  expect(rows.map((r) => r.id)).toEqual([
    "2026-10-20T17:00:00Z",
    "2026-10-20T16:00:00Z",
    "2026-10-20T15:00:00Z",
    "2026-10-20T14:00:00Z",
    "2026-10-20T13:00:00Z",
  ]);
});

// Change labels
test("an opening shows when it happened and its changes, without rejected ones", () => {
  const rows = recentRows(
    [
      event("2026-10-20T17:58:00Z", {
        changes: [
          change("milk", "added", 2),
          change("eggs", "removed", 1),
          change("apple", "added", 1, { rejected: true, applied: false }),
        ],
      }),
    ],
    NOW.getTime(),
  );
  expect(rows).toEqual([{ id: "2026-10-20T17:58:00Z", ago: "2 min ago", state: "changes", labels: ["+ 2 milk", "− eggs"] }]);
});

// Analysis running
test("an opening still being analyzed is checking, one without changes has none", () => {
  const rows = recentRows(
    [event("2026-10-20T17:59:00Z", { status: "analyzing" }), event("2026-10-20T17:00:00Z")],
    NOW.getTime(),
  );
  expect(rows.map((r) => r.state)).toEqual(["checking", "none"]);
});

// Quiet week
test("no openings give no rows", () => {
  expect(recentRows([], NOW.getTime())).toEqual([]);
});

// Today's count
test("opens today and per day in the device's time zone", () => {
  const events = [
    event("2026-10-20T12:00:00Z"),
    event("2026-10-20T15:00:00Z"),
    event("2026-10-20T17:00:00Z"),
    event("2026-10-19T15:00:00Z"),
    event("2026-10-20T03:00:00Z"), // 23:00 on Oct 19 in Toronto
  ];
  const summary = opensSummary(events, NOW, TZ);
  expect(summary.today).toBe(3);
  expect(summary.label).toBe("3 opens today");
  expect(summary.days).toHaveLength(7);
  expect(summary.days.slice(-2).map((d) => d.opens)).toEqual([2, 3]);
});

// One opening today
test("one opening today is singular", () => {
  expect(opensSummary([event("2026-10-20T17:00:00Z")], NOW, TZ).label).toBe("1 open today");
});
