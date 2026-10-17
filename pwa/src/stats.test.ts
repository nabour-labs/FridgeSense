import { averageDuration, byWeekdayHour, durationStats, heatLevel, lastDays, perDay, todayCount } from "./stats";

const UTC = "UTC";
const NOW = new Date("2026-10-15T20:00:00Z");

function at(iso: string, duration_s: number) {
  return { opened_at: iso, duration_s };
}

const WEEK = [
  at("2026-10-15T08:00:00Z", 20),
  at("2026-10-15T12:00:00Z", 30),
  at("2026-10-15T18:30:00Z", 40),
  at("2026-10-14T09:00:00Z", 25),
  at("2026-10-14T19:00:00Z", 35),
];

// Stats from events
test("today, per day and average from a week of events", () => {
  expect(todayCount(WEEK, NOW, UTC)).toBe(3);
  const days = perDay(WEEK, NOW, UTC);
  expect(days).toHaveLength(7);
  expect(days.map((d) => d.opens)).toEqual([0, 0, 0, 0, 0, 2, 3]);
  expect(days[6].date).toBe("2026-10-15");
  expect(days[0].date).toBe("2026-10-09");
  expect(averageDuration(WEEK)).toBe(30);
});

// Day and hour heatmap
test("by weekday and hour counts by local weekday (Sunday first) and hour", () => {
  const grid = byWeekdayHour(WEEK, UTC);
  expect(grid).toHaveLength(7);
  grid.forEach((row) => expect(row).toHaveLength(24));
  // 2026-10-15 is a Thursday (4), 2026-10-14 a Wednesday (3).
  expect(grid[4][8]).toBe(1);
  expect(grid[4][18]).toBe(1);
  expect(grid[3][19]).toBe(1);
  expect(grid.flat().reduce((a, b) => a + b, 0)).toBe(5);
});

// Heat levels
test("heat levels split counts into 5 levels relative to the busiest cell", () => {
  expect([0, 1, 4, 5, 8].map((n) => heatLevel(n, 8))).toEqual([0, 1, 2, 3, 4]);
  expect(heatLevel(0, 0)).toBe(0);
});

// Older events only in the heatmap
test("last days keeps only events from the last 7 local days", () => {
  const old = at("2026-10-05T12:00:00Z", 10);
  expect(lastDays([...WEEK, old], NOW, UTC, 7)).toEqual(WEEK);
  expect(lastDays([at("2026-10-09T00:00:00Z", 10)], NOW, UTC, 7)).toHaveLength(1);
  expect(lastDays([at("2026-10-08T23:59:00Z", 10)], NOW, UTC, 7)).toHaveLength(0);
});

// Local time zone
test("an event counts toward the local day and hour", () => {
  const ev = [at("2026-10-15T02:30:00Z", 10)];
  const tz = "America/Vancouver";
  const days = perDay(ev, new Date("2026-10-15T03:00:00Z"), tz);
  expect(days[6].date).toBe("2026-10-14");
  expect(days[6].opens).toBe(1);
  expect(byWeekdayHour(ev, tz)[3][19]).toBe(1);
  expect(todayCount(ev, new Date("2026-10-15T03:00:00Z"), tz)).toBe(1);
});

// No openings yet
test("no openings gives zeros and no average", () => {
  expect(todayCount([], NOW, UTC)).toBe(0);
  expect(perDay([], NOW, UTC).map((d) => d.opens)).toEqual([0, 0, 0, 0, 0, 0, 0]);
  expect(byWeekdayHour([], UTC).flat()).toEqual(Array(168).fill(0));
  expect(averageDuration([])).toBeNull();
});

// Today marked
test("only today is marked as today", () => {
  const days = perDay(WEEK, NOW, UTC);
  expect(days.map((d) => d.isToday)).toEqual([false, false, false, false, false, false, true]);
});

// Today's open times
test("duration stats give the average, longest and shortest opening of a day", () => {
  expect(durationStats(WEEK, "2026-10-15", UTC)).toEqual({ average: 30, longest: 40, shortest: 20 });
  expect(durationStats(WEEK, "2026-10-14", UTC)).toEqual({ average: 30, longest: 35, shortest: 25 });
});

// Average rounded
test("the day's average open time is rounded to the nearest second", () => {
  const day = [at("2026-10-15T08:00:00Z", 20), at("2026-10-15T09:00:00Z", 25)];
  expect(durationStats(day, "2026-10-15", UTC)?.average).toBe(23);
});

// Single opening
test("a single opening is the average, longest and shortest", () => {
  expect(durationStats([at("2026-10-15T08:00:00Z", 18)], "2026-10-15", UTC)).toEqual({
    average: 18,
    longest: 18,
    shortest: 18,
  });
});

// Day without openings
test("a day without openings has no duration stats", () => {
  expect(durationStats(WEEK, "2026-10-13", UTC)).toBeNull();
  expect(durationStats([], "2026-10-15", UTC)).toBeNull();
});

// Open time in local days
test("open time counts toward the local day", () => {
  const ev = [at("2026-10-15T02:30:00Z", 50)];
  const tz = "America/Vancouver";
  expect(durationStats(ev, "2026-10-14", tz)).toEqual({ average: 50, longest: 50, shortest: 50 });
  expect(durationStats(ev, "2026-10-15", tz)).toBeNull();
});
