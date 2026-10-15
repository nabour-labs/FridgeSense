import { averageDuration, perDay, perHour, todayCount } from "./stats";

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

test("per hour counts by local hour", () => {
  const hours = perHour(WEEK, UTC);
  expect(hours).toHaveLength(24);
  expect(hours[8]).toBe(1);
  expect(hours[18]).toBe(1);
  expect(hours.reduce((a, b) => a + b, 0)).toBe(5);
});

// Local time zone
test("an event counts toward the local day and hour", () => {
  const ev = [at("2026-10-15T02:30:00Z", 10)];
  const tz = "America/Vancouver";
  const days = perDay(ev, new Date("2026-10-15T03:00:00Z"), tz);
  expect(days[6].date).toBe("2026-10-14");
  expect(days[6].opens).toBe(1);
  expect(perHour(ev, tz)[19]).toBe(1);
  expect(todayCount(ev, new Date("2026-10-15T03:00:00Z"), tz)).toBe(1);
});

// No openings yet
test("no openings gives zeros and no average", () => {
  expect(todayCount([], NOW, UTC)).toBe(0);
  expect(perDay([], NOW, UTC).map((d) => d.opens)).toEqual([0, 0, 0, 0, 0, 0, 0]);
  expect(perHour([], UTC)).toEqual(Array(24).fill(0));
  expect(averageDuration([])).toBeNull();
});
