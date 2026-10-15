import { render, screen, within } from "@testing-library/react";
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
