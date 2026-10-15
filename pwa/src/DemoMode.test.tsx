import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";
import { ReadOnly } from "./api/client";
import type { Inventory } from "./api/types";
import { fakeApi, signedIn } from "./test-utils";

const INVENTORY: Inventory = {
  items: [{ key: "eggs", name: "Eggs", category: "dairy", quantity: 6, last_changed_at: null }],
  pending_count: 1,
};
const PENDING = {
  id: "p1",
  door_event_id: "ev1",
  item: "chocolate bar",
  category: "snack",
  direction: "removed" as const,
  quantity: 1,
  confidence: 0.62,
  opened_at: "2026-10-15T01:02:00.000Z",
};

// Demo sign-in
test("signing in with the demo passcode shows the read-only badge", async () => {
  location.hash = "";
  const api = fakeApi({
    signIn: vi.fn().mockResolvedValue({ token: "vt", expires_at: "x", role: "viewer" }),
  });
  render(<App api={api} />);
  await userEvent.type(screen.getByLabelText("Passcode"), "look-only");
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByRole("heading", { name: "Fridge" })).toBeInTheDocument();
  expect(screen.getByText("Demo · read-only")).toBeInTheDocument();
  expect(localStorage.getItem("fridgesense.token")).toBe("vt");
  expect(localStorage.getItem("fridgesense.role")).toBe("viewer");
});

test("the badge shows on every screen", async () => {
  signedIn("viewer");
  for (const hash of ["#fridge", "#activity", "#review", "#stats"]) {
    location.hash = hash;
    const { unmount } = render(<App api={fakeApi()} />);
    expect(await screen.findByText("Demo · read-only")).toBeInTheDocument();
    unmount();
  }
});

// No edits on Fridge
test("a viewer can't edit quantities", async () => {
  signedIn("viewer");
  location.hash = "";
  const api = fakeApi({ inventory: vi.fn().mockResolvedValue(INVENTORY) });
  render(<App api={api} />);
  expect(await screen.findByText("Eggs")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Eggs/ })).not.toBeInTheDocument();
  await userEvent.click(screen.getByText("Eggs"));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(api.setQuantity).not.toHaveBeenCalled();
  expect(api.editItem).not.toHaveBeenCalled();
  expect(api.deleteItem).not.toHaveBeenCalled();
});

// No Add item for viewers
test.each([
  ["with items", INVENTORY],
  ["with an empty fridge", { items: [], pending_count: 0 }],
])("a viewer sees no Add item button %s", async (_, inventory) => {
  signedIn("viewer");
  location.hash = "";
  render(<App api={fakeApi({ inventory: vi.fn().mockResolvedValue(inventory) })} />);
  expect(await screen.findByText("Demo · read-only")).toBeInTheDocument();
  await screen.findByRole("region", { name: "Fridge summary" });
  expect(screen.queryByRole("button", { name: "Add item" })).not.toBeInTheDocument();
});

// No actions on Review
test("a viewer sees pending changes without actions", async () => {
  signedIn("viewer");
  location.hash = "#review";
  render(<App api={fakeApi({ pending: vi.fn().mockResolvedValue({ pending: [PENDING] }) })} />);
  expect(await screen.findByText("− chocolate bar")).toBeInTheDocument();
  expect(screen.getByText("62% sure")).toBeInTheDocument();
  for (const name of ["Confirm", "Edit", "Not right"]) {
    expect(screen.queryByRole("button", { name })).not.toBeInTheDocument();
  }
});

// Write refused
test("a 403 shows the read-only notice and keeps the list", async () => {
  signedIn("owner"); // e.g. a stale role on the device; the API is the authority
  location.hash = "#review";
  const api = fakeApi({
    pending: vi.fn().mockResolvedValue({ pending: [PENDING] }),
    confirm: vi.fn().mockRejectedValue(new ReadOnly()),
  });
  render(<App api={api} />);
  await userEvent.click(await screen.findByRole("button", { name: "Confirm" }));
  expect(await screen.findByText("Read-only demo")).toBeInTheDocument();
  await waitFor(() => expect(screen.getByText("− chocolate bar")).toBeInTheDocument());
});

test("a 403 on Add item shows the read-only notice and keeps the list", async () => {
  signedIn("owner");
  location.hash = "";
  const api = fakeApi({
    inventory: vi.fn().mockResolvedValue(INVENTORY),
    addItem: vi.fn().mockRejectedValue(new ReadOnly()),
  });
  render(<App api={api} />);
  await userEvent.click(await screen.findByRole("button", { name: "Add item" }));
  await userEvent.type(screen.getByLabelText("Name"), "Butter");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByText("Read-only demo")).toBeInTheDocument();
  expect(screen.getByText("Eggs")).toBeInTheDocument();
  expect(screen.queryByText("Butter")).not.toBeInTheDocument();
});
