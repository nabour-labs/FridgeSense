import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "../App";
import type { DoorEvent } from "../api/types";
import { fakeApi, signedIn } from "../test-utils";

const opened = new Date();
opened.setHours(18, 2, 0, 0);

function event(overrides: Partial<DoorEvent> = {}): DoorEvent {
  return {
    id: "ev1",
    opened_at: opened.toISOString(),
    closed_at: new Date(opened.getTime() + 25_000).toISOString(),
    duration_s: 25,
    status: "done",
    pending_count: 0,
    stills: [],
    changes: [
      { item: "milk", category: "dairy", direction: "added", quantity: 1, confidence: 0.92, applied: true },
      { item: "eggs", category: "dairy", direction: "removed", quantity: 2, confidence: 0.81, applied: true },
    ],
    ...overrides,
  };
}

function renderActivity(events: DoorEvent[]) {
  signedIn();
  location.hash = "#activity";
  const api = fakeApi({ events: vi.fn().mockResolvedValue({ events }) });
  render(<App api={api} />);
  return api;
}

// Door opening shown
test("a door opening shows its time, duration and changes", async () => {
  const api = renderActivity([event()]);
  const card = await screen.findByRole("article");
  expect(within(card).getByText("18:02")).toBeInTheDocument();
  expect(within(card).getByText("25 s")).toBeInTheDocument();
  expect(within(card).getByText("+ milk")).toBeInTheDocument();
  expect(within(card).getByText("− 2 eggs")).toBeInTheDocument();
  expect(api.events).toHaveBeenCalledWith(7);
});

test("unconfirmed changes are marked", async () => {
  renderActivity([
    event({
      pending_count: 1,
      changes: [
        { item: "chocolate bar", category: "snack", direction: "removed", quantity: 1, confidence: 0.62, applied: false },
      ],
    }),
  ]);
  const card = await screen.findByRole("article");
  expect(within(card).getByText("− chocolate bar")).toBeInTheDocument();
  expect(within(card).getByText("to confirm")).toBeInTheDocument();
});

// Stills
test("stills show as thumbnails that open full size", async () => {
  const stills = [1, 2, 3, 4].map((n) => `https://stills.example.com/still-${n}.jpg?sig=x`);
  renderActivity([event({ stills })]);
  const card = await screen.findByRole("article");
  const thumbs = within(card).getAllByRole("button", { name: /Still \d of 4/ });
  expect(thumbs).toHaveLength(4);
  await userEvent.click(thumbs[2]);
  const dialog = screen.getByRole("dialog");
  expect(within(dialog).getByRole("img")).toHaveAttribute("src", stills[2]);
});

// Failed analysis
test("a failed analysis says so instead of listing changes", async () => {
  renderActivity([event({ status: "analysis_failed", changes: [] })]);
  const card = await screen.findByRole("article");
  expect(within(card).getByText("Couldn't tell what changed")).toBeInTheDocument();
});

test("no door openings yet", async () => {
  renderActivity([]);
  expect(await screen.findByText(/No door openings in the last 7 days/)).toBeInTheDocument();
});
