import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "../App";
import type { Inventory, Item } from "../api/types";
import { ApiError, Offline } from "../api/client";
import { fakeApi, signedIn } from "../test-utils";

function item(key: string, quantity: number, category: string, name = key): Item {
  return { key, name, category, quantity, last_changed_at: "2026-10-15T08:00:00.000Z" };
}

const STOCKED: Inventory = {
  items: [
    item("soda can", 0, "beverage"),
    item("eggs", 6, "dairy", "Eggs"),
    item("milk", 1, "dairy", "Milk"),
    item("apple", 3, "produce"),
  ],
  pending_count: 0,
};

function renderFridge(inventory: Inventory | (() => Inventory) = STOCKED, role?: "viewer") {
  signedIn(role);
  location.hash = "";
  const get = typeof inventory === "function" ? inventory : () => inventory;
  const api = fakeApi({ inventory: vi.fn(async () => get()) });
  render(<App api={api} />);
  return api;
}

// Items by category
test("items are grouped by category", async () => {
  renderFridge();
  const dairy = await screen.findByRole("region", { name: "Dairy" });
  expect(within(dairy).getByText("Eggs")).toBeInTheDocument();
  expect(within(dairy).getByText("×6")).toBeInTheDocument();
  expect(within(dairy).getByText("Milk")).toBeInTheDocument();
  expect(within(dairy).getByText("×1")).toBeInTheDocument();
  const produce = screen.getByRole("region", { name: "Produce" });
  expect(within(produce).getByText("apple")).toBeInTheDocument();
  expect(within(produce).getByText("×3")).toBeInTheDocument();
});

// Out of stock
test("items with quantity 0 are only in the Out of section", async () => {
  renderFridge();
  await screen.findByRole("region", { name: "Dairy" });
  expect(screen.queryByRole("region", { name: "Beverage" })).not.toBeInTheDocument();
  const outOf = screen.getByRole("group", { name: /Out of/ });
  expect(within(outOf).getByText("soda can")).toBeInTheDocument();
  expect(outOf).not.toHaveAttribute("open");
});

// Pending banner
test("a banner links to Review when changes are pending", async () => {
  renderFridge({ ...STOCKED, pending_count: 2 });
  const banner = await screen.findByRole("link", { name: /2 items to confirm/ });
  await userEvent.click(banner);
  expect(await screen.findByRole("heading", { name: "Review" })).toBeInTheDocument();
});

test("one pending change reads in the singular", async () => {
  renderFridge({ ...STOCKED, pending_count: 1 });
  expect(await screen.findByRole("link", { name: /1 item to confirm/ })).toBeInTheDocument();
});

// Empty fridge
test("an empty fridge explains when items appear", async () => {
  renderFridge({ items: [], pending_count: 0 });
  expect(await screen.findByText(/fridge looks empty/i)).toBeInTheDocument();
  expect(screen.getByText(/after the next door opening/i)).toBeInTheDocument();
});

describe("polling", () => {
  let visibility: DocumentVisibilityState = "visible";
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    visibility = "visible";
    vi.spyOn(document, "visibilityState", "get").mockImplementation(() => visibility);
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  // Live refresh
  test("the inventory refreshes every 10 s without a reload", async () => {
    let eggs = 6;
    const api = renderFridge(() => ({ items: [item("eggs", eggs, "dairy", "Eggs")], pending_count: 0 }));
    expect(await screen.findByText("×6")).toBeInTheDocument();
    eggs = 9;
    await act(() => vi.advanceTimersByTimeAsync(10_000));
    expect(await screen.findByText("×9")).toBeInTheDocument();
    expect(api.inventory).toHaveBeenCalledTimes(2);
  });

  // Hidden app does not poll
  test("no requests while the page is hidden", async () => {
    const api = renderFridge();
    await screen.findByRole("region", { name: "Dairy" });
    visibility = "hidden";
    act(() => void document.dispatchEvent(new Event("visibilitychange")));
    await act(() => vi.advanceTimersByTimeAsync(60_000));
    expect(api.inventory).toHaveBeenCalledTimes(1);
  });
});

// Fix a quantity
test("tapping an item lets the owner fix its quantity", async () => {
  const api = renderFridge();
  (api.setQuantity as ReturnType<typeof vi.fn>).mockResolvedValue({
    items: [item("eggs", 12, "dairy", "Eggs")],
    pending_count: 0,
  });
  await userEvent.click(await screen.findByRole("button", { name: /Eggs/ }));
  const dialog = screen.getByRole("dialog", { name: "Eggs" });
  const input = within(dialog).getByLabelText("Quantity");
  await userEvent.clear(input);
  await userEvent.type(input, "12");
  await userEvent.click(within(dialog).getByRole("button", { name: "Save" }));
  expect(api.setQuantity).toHaveBeenCalledWith("eggs", 12);
  expect(await screen.findByText("×12")).toBeInTheDocument();
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

// Summary card
test("a summary card shows the in-stock count and the last change", async () => {
  const twoMinAgo = new Date(Date.now() - 2 * 60_000).toISOString();
  renderFridge({
    ...STOCKED,
    items: STOCKED.items.map((i) => (i.key === "milk" ? { ...i, last_changed_at: twoMinAgo } : i)),
  });
  const summary = await screen.findByRole("region", { name: "Fridge summary" });
  expect(within(summary).getByText("3 in stock")).toBeInTheDocument();
  expect(within(summary).getByText("Last change 2 min ago")).toBeInTheDocument();
});

// Summary with nothing changed yet
test("the summary leaves out the last change when nothing has changed", async () => {
  renderFridge({ items: STOCKED.items.map((i) => ({ ...i, last_changed_at: null })), pending_count: 0 });
  const summary = await screen.findByRole("region", { name: "Fridge summary" });
  expect(within(summary).getByText("3 in stock")).toBeInTheDocument();
  expect(within(summary).queryByText(/Last change/)).not.toBeInTheDocument();
});

// Pending banner (inside the summary card)
test("the pending link sits in the summary card", async () => {
  renderFridge({ ...STOCKED, pending_count: 2 });
  const summary = await screen.findByRole("region", { name: "Fridge summary" });
  expect(within(summary).getByRole("link", { name: /2 items to confirm/ })).toBeInTheDocument();
});

// Item icons from name
test("each item row shows its icon", async () => {
  renderFridge({
    items: [item("milk", 1, "dairy", "Milk"), item("apple", 3, "produce"), item("leftover pasta", 2, "leftovers")],
    pending_count: 0,
  });
  await screen.findByText("Milk");
  const icons = Array.from(document.querySelectorAll("[data-icon]")).map((e) => e.getAttribute("data-icon"));
  expect(icons).toEqual(["🥛", "🍎", "🍝"]);
});

describe("no data", () => {
  // No camera linked
  test("a 409 shows No Data instead of the skeleton", async () => {
    renderFailing(new ApiError(409));
    expect(await screen.findByText("No Data")).toBeInTheDocument();
    expect(screen.queryByTestId("loading")).not.toBeInTheDocument();
  });

  // First load fails
  test.each([
    ["a server error", new ApiError(500)],
    ["being offline", new Offline("x")],
  ])("a first load failing with %s shows No Data", async (_, error) => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    renderFailing(error);
    expect(await screen.findByText("No Data")).toBeInTheDocument();
    expect(screen.queryByTestId("loading")).not.toBeInTheDocument();
  });

  test("offline on first load also shows the offline banner", async () => {
    renderFailing(new Offline("x"));
    expect(await screen.findByText("No Data")).toBeInTheDocument();
    expect(screen.getByText(/Can't reach FridgeSense/)).toBeInTheDocument();
  });

  // Still loading
  test("the skeleton shows while the first request is in flight", () => {
    signedIn();
    location.hash = "";
    render(<App api={fakeApi({ inventory: vi.fn(() => new Promise(() => {})) })} />);
    expect(screen.getByTestId("loading")).toBeInTheDocument();
    expect(screen.queryByText("No Data")).not.toBeInTheDocument();
  });

  // Data arrives later
  test("data from a later poll replaces No Data", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      signedIn();
      location.hash = "";
      const inventory = vi.fn().mockRejectedValueOnce(new ApiError(409)).mockResolvedValue({
        items: [item("eggs", 6, "dairy", "Eggs")],
        pending_count: 0,
      });
      render(<App api={fakeApi({ inventory })} />);
      expect(await screen.findByText("No Data")).toBeInTheDocument();
      await act(() => vi.advanceTimersByTimeAsync(10_000));
      expect(await screen.findByText("Eggs")).toBeInTheDocument();
      expect(screen.getByText("×6")).toBeInTheDocument();
      expect(screen.queryByText("No Data")).not.toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  function renderFailing(error: Error) {
    signedIn();
    location.hash = "";
    render(<App api={fakeApi({ inventory: vi.fn().mockRejectedValue(error) })} />);
  }
});
