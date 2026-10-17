import { duration } from "./format";

// Minutes and seconds
test("durations read N s under a minute and M m SS s from a minute up", () => {
  expect([0, 45, 59, 60, 65, 600].map(duration)).toEqual(["0 s", "45 s", "59 s", "1 m 00 s", "1 m 05 s", "10 m 00 s"]);
});
