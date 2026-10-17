import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "../App";
import type { DoorEvent } from "../api/types";
import { ApiError } from "../api/client";
import { fakeApi, signedIn } from "../test-utils";

function event(daysAgo: number, hour: number, duration_s: number): DoorEvent {
  const d = new Date();
  d.setDate(d.getDate() - daysAgo);
  d.setHours(hour, 0, 0, 0);
  return {
    id: `${daysAgo}-${hour}`,
    opened_at: d.toISOString(),
    closed_at: d.toISOString(),
    duration_s,
    status: "done",
    changes: [],
    pending_count: 0,
    stills: [],
  };
}

/** Days ago of the most recent `weekday` (0 = Sunday) at least `weeksAgo` weeks back. */
function daysAgoOn(weekday: number, weeksAgo: number): number {
  return ((new Date().getDay() - weekday + 7) % 7) + 7 * weeksAgo;
}

function renderStats(events: DoorEvent[]) {
  signedIn();
  location.hash = "#stats";
  const api = fakeApi({ events: vi.fn().mockResolvedValue({ events }) });
  render(<App api={api} />);
  return api;
}

// Stats from events
test("shows today's opens and the average open time", async () => {
  const hour = Math.min(new Date().getHours(), 20);
  renderStats([
    event(0, hour, 20),
    event(0, hour, 30),
    event(0, hour, 40),
    event(1, 9, 25),
    event(1, 19, 35),
  ]);
  const today = await screen.findByRole("group", { name: "Today" });
  expect(within(today).getByText("3")).toBeInTheDocument();
  const avg = screen.getByRole("group", { name: "Average open time" });
  expect(within(avg).getByText("30 s")).toBeInTheDocument();
  const week = screen.getByRole("group", { name: "Last 7 days" });
  expect(within(week).getByText("5")).toBeInTheDocument();
  expect(screen.getByRole("figure", { name: "Opens per day" })).toBeInTheDocument();
  expect(screen.getByRole("figure", { name: "Opens by day and hour" })).toBeInTheDocument();
});

// Four weeks requested
test("requests the last 28 days of events", async () => {
  const api = renderStats([]);
  await screen.findByRole("group", { name: "Today" });
  expect(api.events).toHaveBeenCalledWith(28);
});

// Older events only in the heatmap
test("an event 10 days ago is in the heatmap but not in the last 7 days", async () => {
  const hour = Math.min(new Date().getHours(), 20);
  const old = event(10, 7, 30);
  renderStats([event(0, hour, 20), old]);
  const week = await screen.findByRole("group", { name: "Last 7 days" });
  expect(within(week).getByText("1")).toBeInTheDocument();
  const figure = screen.getByRole("figure", { name: "Opens by day and hour" });
  const day = new Date(old.opened_at).toLocaleDateString("en-US", { weekday: "short" });
  expect(within(figure).getByRole("cell", { name: `${day} 07:00, 1 open` })).toBeInTheDocument();
});

// No openings yet
test("no openings shows zeros without errors", async () => {
  renderStats([]);
  const today = await screen.findByRole("group", { name: "Today" });
  expect(within(today).getByText("0")).toBeInTheDocument();
  expect(within(screen.getByRole("group", { name: "Average open time" })).getByText("–")).toBeInTheDocument();
});

// Day and hour heatmap
test("opens by day and hour is a 7 by 24 heatmap with a legend", async () => {
  renderStats([event(daysAgoOn(1, 1), 19, 20), event(daysAgoOn(1, 2), 19, 30)]);
  const figure = await screen.findByRole("figure", { name: "Opens by day and hour" });
  expect(within(figure).getAllByRole("cell")).toHaveLength(168);
  expect(within(figure).getByRole("cell", { name: "Mon 19:00, 2 opens" })).toBeInTheDocument();
  expect(within(figure).getByRole("cell", { name: "Wed 03:00, 0 opens" })).toBeInTheDocument();
  expect(within(figure).getByText("Less")).toBeInTheDocument();
  expect(within(figure).getByText("More")).toBeInTheDocument();
});

// No camera linked
test("a 409 shows No Data instead of the skeleton", async () => {
  signedIn();
  location.hash = "#stats";
  render(<App api={fakeApi({ events: vi.fn().mockRejectedValue(new ApiError(409)) })} />);
  expect(await screen.findByText("No Data")).toBeInTheDocument();
  expect(screen.queryByTestId("loading")).not.toBeInTheDocument();
});

function weekday(daysAgo: number): string {
  const d = new Date();
  d.setDate(d.getDate() - daysAgo);
  return d.toLocaleDateString("en-US", { weekday: "short" });
}

function openTimes(figure: HTMLElement) {
  return ["Average", "Longest", "Shortest"].map((name) => within(figure).getByRole("group", { name }).textContent);
}

const TWO_DAYS = () => {
  const hour = Math.min(new Date().getHours(), 20);
  return [event(0, hour, 20), event(0, hour, 30), event(0, hour, 40), event(1, 9, 25), event(1, 19, 35)];
};

// Today's open times
test("open time shows today's average, longest and shortest opening", async () => {
  renderStats(TWO_DAYS());
  const figure = await screen.findByRole("figure", { name: "Open time" });
  expect(within(figure).getByRole("button", { name: "Today" })).toHaveAttribute("aria-pressed", "true");
  expect(openTimes(figure)).toEqual(["Average30 s", "Longest40 s", "Shortest20 s"]);
});

// Pick another day
test("tapping yesterday shows yesterday's open times", async () => {
  renderStats(TWO_DAYS());
  const figure = await screen.findByRole("figure", { name: "Open time" });
  await userEvent.click(within(figure).getByRole("button", { name: weekday(1) }));
  expect(within(figure).getByRole("button", { name: weekday(1) })).toHaveAttribute("aria-pressed", "true");
  expect(within(figure).getByRole("button", { name: "Today" })).toHaveAttribute("aria-pressed", "false");
  expect(openTimes(figure)).toEqual(["Average30 s", "Longest35 s", "Shortest25 s"]);
});

// Seven day buttons
test("open time has a button for each of the last 7 days, oldest first", async () => {
  renderStats([]);
  const figure = await screen.findByRole("figure", { name: "Open time" });
  const names = within(figure).getAllByRole("button").map((b) => b.textContent);
  expect(names).toEqual([6, 5, 4, 3, 2, 1].map(weekday).concat("Today"));
});

// Long opening on the card
test("an opening of a minute or more reads in minutes and seconds", async () => {
  const hour = Math.min(new Date().getHours(), 20);
  renderStats([event(0, hour, 65), event(0, hour, 20)]);
  const figure = await screen.findByRole("figure", { name: "Open time" });
  expect(openTimes(figure)).toEqual(["Average43 s", "Longest1 m 05 s", "Shortest20 s"]);
});

// Day without openings
test("a day without openings shows dashes and No openings", async () => {
  renderStats(TWO_DAYS());
  const figure = await screen.findByRole("figure", { name: "Open time" });
  await userEvent.click(within(figure).getByRole("button", { name: weekday(2) }));
  expect(openTimes(figure)).toEqual(["Average–", "Longest–", "Shortest–"]);
  expect(within(figure).getByText("No openings")).toBeInTheDocument();
});
