import { render, screen, within } from "@testing-library/react";
import App from "../App";
import type { DoorEvent } from "../api/types";
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

function renderStats(events: DoorEvent[]) {
  signedIn();
  location.hash = "#stats";
  render(<App api={fakeApi({ events: vi.fn().mockResolvedValue({ events }) })} />);
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
  expect(screen.getByRole("figure", { name: "Opens by hour" })).toBeInTheDocument();
});

// No openings yet
test("no openings shows zeros without errors", async () => {
  renderStats([]);
  const today = await screen.findByRole("group", { name: "Today" });
  expect(within(today).getByText("0")).toBeInTheDocument();
  expect(within(screen.getByRole("group", { name: "Average open time" })).getByText("–")).toBeInTheDocument();
});

// Hour heat strip
test("opens by hour is a 24-cell strip labelled per hour", async () => {
  renderStats([event(0, 19, 20), event(1, 19, 30)]);
  const figure = await screen.findByRole("figure", { name: "Opens by hour" });
  expect(within(figure).getAllByRole("listitem")).toHaveLength(24);
  expect(within(figure).getByRole("listitem", { name: "19:00, 2 opens" })).toBeInTheDocument();
  expect(within(figure).getByRole("listitem", { name: "03:00, 0 opens" })).toBeInTheDocument();
});
