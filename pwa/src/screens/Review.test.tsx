import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "../App";
import type { Pending } from "../api/types";
import { fakeApi, signedIn } from "../test-utils";

function pending(overrides: Partial<Pending> = {}): Pending {
  return {
    id: "p1",
    door_event_id: "ev1",
    item: "chocolate bar",
    category: "snack",
    direction: "removed",
    quantity: 1,
    confidence: 0.62,
    opened_at: "2026-10-15T01:02:00.000Z",
    ...overrides,
  };
}

function renderReview(items: Pending[], role?: "viewer") {
  signedIn(role);
  location.hash = "#review";
  let current = items;
  const api = fakeApi({
    pending: vi.fn(async () => ({ pending: current })),
    confirm: vi.fn(async (id: string) => {
      current = current.filter((p) => p.id !== id);
      return { items: [], pending_count: current.length };
    }),
    reject: vi.fn(async (id: string) => {
      current = current.filter((p) => p.id !== id);
      return { items: [], pending_count: current.length };
    }),
  });
  render(<App api={api} />);
  return api;
}

test("pending changes show item, direction, quantity and confidence", async () => {
  renderReview([pending()]);
  const card = await screen.findByRole("article");
  expect(within(card).getByText("− chocolate bar")).toBeInTheDocument();
  expect(within(card).getByText("62% sure")).toBeInTheDocument();
});

// Confirm
test("confirm sends the request and removes the change", async () => {
  const api = renderReview([pending()]);
  await userEvent.click(await screen.findByRole("button", { name: "Confirm" }));
  expect(api.confirm).toHaveBeenCalledWith("p1", undefined);
  await waitFor(() => expect(screen.queryByRole("article")).not.toBeInTheDocument());
});

// Edit and confirm
test("edit then confirm sends the corrected item and quantity", async () => {
  const api = renderReview([pending({ item: "bottle", direction: "added", category: "beverage" })]);
  await userEvent.click(await screen.findByRole("button", { name: "Edit" }));
  const dialog = screen.getByRole("dialog");
  const name = within(dialog).getByLabelText("Item");
  await userEvent.clear(name);
  await userEvent.type(name, "Oat Milk");
  const qty = within(dialog).getByLabelText("Quantity");
  await userEvent.clear(qty);
  await userEvent.type(qty, "2");
  await userEvent.click(within(dialog).getByRole("button", { name: "Confirm" }));
  expect(api.confirm).toHaveBeenCalledWith("p1", { item: "Oat Milk", quantity: 2 });
  await waitFor(() => expect(screen.queryByRole("article")).not.toBeInTheDocument());
});

// Reject
test("not right rejects the change", async () => {
  const api = renderReview([pending()]);
  await userEvent.click(await screen.findByRole("button", { name: "Not right" }));
  expect(api.reject).toHaveBeenCalledWith("p1");
  await waitFor(() => expect(screen.queryByRole("article")).not.toBeInTheDocument());
});

// Nothing to review
test("nothing to review", async () => {
  renderReview([]);
  expect(await screen.findByText(/Everything is confirmed/)).toBeInTheDocument();
});

// Confidence meter
test("each pending change shows a confidence meter toned by confidence", async () => {
  renderReview([
    pending({ id: "a", confidence: 0.62 }),
    pending({ id: "b", item: "bottle", direction: "added", confidence: 0.48 }),
    pending({ id: "c", item: "butter", confidence: 0.85 }),
  ]);
  await screen.findAllByRole("article");
  const meters = screen.getAllByRole("meter", { name: "Confidence" });
  expect(meters.map((m) => m.getAttribute("aria-valuenow"))).toEqual(["62", "48", "85"]);
  expect(meters.map((m) => m.getAttribute("data-tone"))).toEqual(["medium", "low", "high"]);
});
