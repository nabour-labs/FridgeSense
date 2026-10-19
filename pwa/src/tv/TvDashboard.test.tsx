import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { ApiError } from "../api/client";
import type { DoorEvent, Item } from "../api/types";
import { AppContext, type Api } from "../AppContext";
import { fakeApi } from "../test-utils";
import { TvDashboard } from "./TvDashboard";

function item(name: string, quantity: number, category: string): Item {
  return { key: name, name, category, quantity, last_changed_at: null };
}

function event(minutesAgo: number, extra: Partial<DoorEvent> = {}): DoorEvent {
  const at = new Date(Date.now() - minutesAgo * 60_000).toISOString();
  return {
    id: `e${minutesAgo}`,
    opened_at: at,
    closed_at: at,
    duration_s: 20,
    status: "done",
    changes: [],
    pending_count: 0,
    stills: [],
    clip: null,
    ...extra,
  };
}

const ITEMS = [item("eggs", 6, "dairy"), item("milk", 1, "dairy"), item("apple", 3, "produce"), item("soda can", 0, "beverage")];

const MILK_EVENT = event(2, {
  changes: [
    { item: "milk", category: "dairy", direction: "added", quantity: 2, confidence: 0.9, applied: true, proof: ["https://s3/proof-1.jpg"] },
    { item: "eggs", category: "dairy", direction: "removed", quantity: 1, confidence: 0.9, applied: true },
  ],
  stills: ["https://s3/still-1.jpg"],
  clip: "https://s3/clip.mp4#t=1,3",
});

function renderTv(overrides: Partial<Record<keyof Api, unknown>> = {}) {
  const api = fakeApi({
    inventory: vi.fn().mockResolvedValue({ items: ITEMS, pending_count: 0 }),
    events: vi.fn().mockResolvedValue({ events: [MILK_EVENT] }),
    ...overrides,
  });
  const report = vi.fn();
  render(
    <AppContext.Provider value={{ api, role: "viewer", report, online: vi.fn(), go: vi.fn() }}>
      <TvDashboard />
    </AppContext.Provider>,
  );
  return { api, report };
}

const panel = (name: string) => screen.findByRole("region", { name });

// Items by category
test("In the fridge lists in-stock items by category", async () => {
  renderTv();
  const fridge = await panel("In the fridge");
  const dairy = await within(fridge).findByRole("list", { name: "Dairy" });
  expect(within(dairy).getAllByRole("listitem").map((li) => li.textContent)).toEqual([
    expect.stringMatching(/eggs.*×6/),
    expect.stringMatching(/milk.*×1/),
  ]);
  expect(within(fridge).getByRole("list", { name: "Produce" })).toHaveTextContent(/apple.*×3/);
  expect(within(fridge).queryByText(/soda can/)).not.toBeInTheDocument();
});

// More than fits
test("more than 12 items shows +N more", async () => {
  const many = Array.from({ length: 15 }, (_, i) => item(`item ${i + 1}`, 1, "dairy"));
  renderTv({ inventory: vi.fn().mockResolvedValue({ items: many, pending_count: 0 }) });
  const fridge = await panel("In the fridge");
  expect(await within(fridge).findByText("+3 more")).toBeInTheDocument();
  expect(within(fridge).getAllByRole("listitem")).toHaveLength(12);
});

// Empty fridge
test("an empty fridge says so", async () => {
  renderTv({ inventory: vi.fn().mockResolvedValue({ items: [item("soda can", 0, "beverage")], pending_count: 0 }) });
  expect(await within(await panel("In the fridge")).findByText("The fridge is empty")).toBeInTheDocument();
});

// Change labels
test("Recent changes shows when each opening happened and what changed", async () => {
  renderTv();
  const recent = await panel("Recent changes");
  const row = await within(recent).findByRole("listitem");
  expect(row).toHaveTextContent("2 min ago");
  expect(row).toHaveTextContent("+ 2 milk");
  expect(row).toHaveTextContent("− eggs");
});

// Analysis running
test("an opening being analyzed shows Checking…", async () => {
  renderTv({ events: vi.fn().mockResolvedValue({ events: [event(1, { status: "analyzing" }), event(30)] }) });
  const recent = await panel("Recent changes");
  expect(await within(recent).findByText("Checking…")).toBeInTheDocument();
  expect(within(recent).getByText("No changes")).toBeInTheDocument();
});

// Quiet week
test("no openings says no door openings this week", async () => {
  renderTv({ events: vi.fn().mockResolvedValue({ events: [] }) });
  expect(await within(await panel("Recent changes")).findByText("No door openings this week")).toBeInTheDocument();
});

// Today's count
test("Opens shows today's count from the same openings, last 7 days", async () => {
  const { api } = renderTv({ events: vi.fn().mockResolvedValue({ events: [event(1), event(2), event(3)] }) });
  const opens = await panel("Opens");
  expect(await within(opens).findByText("3 opens today")).toBeInTheDocument();
  expect(api.events).toHaveBeenCalledWith(7);
  expect(api.events).toHaveBeenCalledTimes(1);
});

// Inventory refresh
test("inventory refreshes every 10 s and openings every 30 s", async () => {
  vi.useFakeTimers();
  try {
    const { api } = renderTv();
    await act(async () => void vi.advanceTimersByTime(30_000));
    expect(api.inventory).toHaveBeenCalledTimes(4);
    expect(api.events).toHaveBeenCalledTimes(2);
  } finally {
    vi.useRealTimers();
  }
});

// Events fail, inventory loads
test("a failed events load shows No Data in its panels only", async () => {
  const { report } = renderTv({ events: vi.fn().mockRejectedValue(new ApiError(500)) });
  expect(await within(await panel("Recent changes")).findByText("No Data")).toBeInTheDocument();
  expect(within(await panel("Opens")).getByText("No Data")).toBeInTheDocument();
  expect(await within(await panel("In the fridge")).findByText(/eggs/)).toBeInTheDocument();
  expect(report).toHaveBeenCalled();
});

// Stills not shown
test("no stills, proof stills or clips are shown", async () => {
  renderTv();
  await within(await panel("Recent changes")).findByText("2 min ago");
  const dashboard = screen.getByRole("region", { name: "TV dashboard" });
  expect(dashboard.querySelectorAll("img, video")).toHaveLength(0);
  expect(dashboard.innerHTML).not.toContain("s3/");
});

// No controls
test("the dashboard has no buttons, links or inputs", async () => {
  renderTv();
  await within(await panel("Recent changes")).findByText("2 min ago");
  const dashboard = screen.getByRole("region", { name: "TV dashboard" });
  expect(within(dashboard).queryAllByRole("button")).toHaveLength(0);
  expect(within(dashboard).queryAllByRole("link")).toHaveLength(0);
  expect(within(dashboard).queryAllByRole("textbox")).toHaveLength(0);
});

// Only two endpoints
test("only the inventory and events endpoints are called", async () => {
  const { api } = renderTv();
  await within(await panel("Recent changes")).findByText("2 min ago");
  const called = Object.entries(api)
    .filter(([, fn]) => vi.isMockFunction(fn) && fn.mock.calls.length > 0)
    .map(([name]) => name)
    .sort();
  expect(called).toEqual(["events", "inventory"]);
});

// Back is left to the TV app
test("Escape is not handled by the dashboard", async () => {
  location.hash = "#tv";
  renderTv();
  await panel("In the fridge");
  const notHandled = fireEvent.keyDown(document.body, { key: "Escape", keyCode: 27 });
  expect(notHandled).toBe(true);
  expect(location.hash).toBe("#tv");
  location.hash = "";
});
