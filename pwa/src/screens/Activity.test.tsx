import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "../App";
import type { DoorEvent } from "../api/types";
import { ApiError } from "../api/client";
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
const STILLS = [1, 2, 3, 4].map((n) => `https://stills.example.com/still-${n}.jpg?sig=x`);

test("stills show with the first one featured, and open full size", async () => {
  renderActivity([event({ stills: STILLS })]);
  const card = await screen.findByRole("article");
  const thumbs = within(card).getAllByRole("button", { name: /Still \d of 4/ });
  expect(thumbs).toHaveLength(4);
  expect(thumbs[0]).toHaveAttribute("data-featured");
  expect(thumbs[1]).not.toHaveAttribute("data-featured");
  await userEvent.click(thumbs[2]);
  const dialog = screen.getByRole("dialog");
  expect(within(dialog).getByRole("img")).toHaveAttribute("src", STILLS[2]);
});

// Step through stills
test("the viewer steps to the next and previous still", async () => {
  renderActivity([event({ stills: STILLS })]);
  const card = await screen.findByRole("article");
  await userEvent.click(within(card).getByRole("button", { name: "Still 3 of 4" }));
  const dialog = screen.getByRole("dialog");
  await userEvent.click(within(dialog).getByRole("button", { name: "Next still" }));
  expect(within(dialog).getByRole("img")).toHaveAttribute("src", STILLS[3]);
  await userEvent.click(within(dialog).getByRole("button", { name: "Previous still" }));
  expect(within(dialog).getByRole("img")).toHaveAttribute("src", STILLS[2]);
  await userEvent.click(within(dialog).getByRole("button", { name: "Previous still" }));
  expect(within(dialog).getByRole("img")).toHaveAttribute("src", STILLS[1]);
  expect(within(dialog).getByRole("heading", { name: "Still 2 of 4" })).toBeInTheDocument();
});

// Viewer at the ends
test("the viewer can't step past the first or last still", async () => {
  renderActivity([event({ stills: STILLS })]);
  const card = await screen.findByRole("article");
  await userEvent.click(within(card).getByRole("button", { name: "Still 1 of 4" }));
  expect(within(screen.getByRole("dialog")).getByRole("button", { name: "Previous still" })).toBeDisabled();
  await userEvent.keyboard("{Escape}");
  await userEvent.click(within(card).getByRole("button", { name: "Still 4 of 4" }));
  expect(within(screen.getByRole("dialog")).getByRole("button", { name: "Next still" })).toBeDisabled();
});

// No stills
test("an event without stills shows no still area", async () => {
  renderActivity([event({ stills: [] })]);
  const card = await screen.findByRole("article");
  expect(within(card).queryByRole("button", { name: /Still/ })).not.toBeInTheDocument();
  expect(card.querySelector("[data-stills]")).toBeNull();
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

// No camera linked
test("a 409 shows No Data instead of the skeleton", async () => {
  signedIn();
  location.hash = "#activity";
  render(<App api={fakeApi({ events: vi.fn().mockRejectedValue(new ApiError(409)) })} />);
  expect(await screen.findByText("No Data")).toBeInTheDocument();
  expect(screen.queryByTestId("loading")).not.toBeInTheDocument();
});

// Later poll fails
test("door openings stay listed when a later poll fails", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.spyOn(console, "error").mockImplementation(() => {});
  try {
    signedIn();
    location.hash = "#activity";
    const events = vi.fn().mockResolvedValueOnce({ events: [event()] }).mockRejectedValue(new ApiError(500));
    render(<App api={fakeApi({ events })} />);
    expect(await screen.findByRole("article")).toBeInTheDocument();
    await act(() => vi.advanceTimersByTimeAsync(10_000));
    expect(events).toHaveBeenCalledTimes(2);
    expect(screen.getByRole("article")).toBeInTheDocument();
    expect(screen.queryByText("No Data")).not.toBeInTheDocument();
  } finally {
    vi.useRealTimers();
  }
});
