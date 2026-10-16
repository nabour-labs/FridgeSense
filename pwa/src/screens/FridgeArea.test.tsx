import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApiError } from "../api/client";
import type { FridgeAreaBody } from "../api/types";
import { AppContext, type Api } from "../AppContext";
import { drag, fakeApi } from "../test-utils";
import { FridgeArea } from "./FridgeArea";

const BOX = { x: 0.2, y: 0.05, width: 0.5, height: 0.9 };
const NONE: FridgeAreaBody = { device_id: "ava1.ring.device.D1", area: null };
const SAVED: FridgeAreaBody = {
  device_id: "ava1.ring.device.D1",
  area: { image: "/9j/AREA", box: BOX, updated_at: "2026-10-16T01:00:00.000Z" },
};
const SNAPSHOT = { image: "/9j/SNAP", captured_at: "2026-10-16T00:59:57.000Z" };

function renderTab(data: FridgeAreaBody, { role = "owner", api: overrides = {} } = {} as {
  role?: "owner" | "viewer";
  api?: Partial<Record<keyof Api, unknown>>;
}) {
  const api = fakeApi({ fridgeArea: vi.fn().mockResolvedValue(data), ...overrides });
  render(
    <AppContext.Provider value={{ api, role, report: vi.fn(), online: vi.fn(), go: vi.fn() }}>
      <FridgeArea />
    </AppContext.Provider>,
  );
  return { api };
}

const dialog = () => screen.getByRole("dialog");

async function openEditor(name = "Set area") {
  await userEvent.click(await screen.findByRole("button", { name }));
  return within(dialog()).findByRole("img", { name: "Snapshot to box the fridge on" });
}

/** The drawn box's rect, in percent of the image. */
function rectOf(el: Element) {
  return ["x", "y", "width", "height"].map((a) => Number(el.getAttribute(a)));
}

// Fridge area shown
test("a saved area shows its snapshot and box", async () => {
  renderTab(SAVED);
  const img = await screen.findByRole("img", { name: "Fridge area" });
  expect(img).toHaveAttribute("src", "data:image/jpeg;base64,/9j/AREA");
  const [shape] = screen.getAllByTestId("markup-shape");
  const [x, y, w, h] = rectOf(shape);
  expect(x).toBeCloseTo(20);
  expect(y).toBeCloseTo(5);
  expect(x + w).toBeCloseTo(70);
  expect(y + h).toBeCloseTo(95);
  expect(screen.getByText(/^Saved /)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Change area" })).toBeInTheDocument();
});

// No fridge area
test("with no area it says so and offers Set area", async () => {
  renderTab(NONE);
  expect(await screen.findByText("No fridge area yet.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Set area" })).toBeInTheDocument();
});

// Set the fridge area
test("setting the area boxes the fridge on a snapshot and saves it", async () => {
  const { api } = renderTab(NONE, {
    api: { cameraSnapshot: vi.fn().mockResolvedValue(SNAPSHOT), saveFridgeArea: vi.fn().mockResolvedValue(SAVED) },
  });
  expect(await openEditor()).toHaveAttribute("src", "data:image/jpeg;base64,/9j/SNAP");
  drag([20, 5], [70, 95]);
  await userEvent.click(within(dialog()).getByRole("button", { name: "Save" }));
  expect(api.saveFridgeArea).toHaveBeenCalledWith("/9j/SNAP", BOX);
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(await screen.findByRole("img", { name: "Fridge area" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Change area" })).toBeInTheDocument();
});

// Box required to save
test("Save needs a box", async () => {
  const { api } = renderTab(NONE, { api: { cameraSnapshot: vi.fn().mockResolvedValue(SNAPSHOT) } });
  await openEditor();
  const save = within(dialog()).getByRole("button", { name: "Save" });
  expect(save).toBeDisabled();
  await userEvent.click(save);
  expect(api.saveFridgeArea).not.toHaveBeenCalled();
});

// Redraw replaces the fridge box
test("drawing again replaces the fridge box", async () => {
  const { api } = renderTab(NONE, {
    api: { cameraSnapshot: vi.fn().mockResolvedValue(SNAPSHOT), saveFridgeArea: vi.fn().mockResolvedValue(SAVED) },
  });
  await openEditor();
  drag([10, 10], [40, 50]);
  drag([10, 0], [70, 100]);
  expect(within(dialog()).getAllByTestId("markup-shape")).toHaveLength(1);
  await userEvent.click(within(dialog()).getByRole("button", { name: "Save" }));
  expect(api.saveFridgeArea).toHaveBeenCalledWith("/9j/SNAP", { x: 0.1, y: 0, width: 0.6, height: 1 });
});

// Cancel setting the area
test("Cancel closes the editor without saving", async () => {
  const { api } = renderTab(NONE, { api: { cameraSnapshot: vi.fn().mockResolvedValue(SNAPSHOT) } });
  await openEditor();
  drag([20, 5], [70, 95]);
  await userEvent.click(within(dialog()).getByRole("button", { name: "Cancel" }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(api.saveFridgeArea).not.toHaveBeenCalled();
  expect(screen.getByText("No fridge area yet.")).toBeInTheDocument();
});

// Snapshot fails while setting the area
test("a snapshot with no recent footage offers Try again", async () => {
  const cameraSnapshot = vi
    .fn()
    .mockRejectedValueOnce(new ApiError(409, "no recent footage"))
    .mockResolvedValueOnce(SNAPSHOT);
  renderTab(NONE, { api: { cameraSnapshot } });
  await userEvent.click(await screen.findByRole("button", { name: "Set area" }));
  expect(await within(dialog()).findByRole("alert")).toHaveTextContent(
    "No recent footage. Walk past the camera, then try again.",
  );
  await userEvent.click(within(dialog()).getByRole("button", { name: "Try again" }));
  expect(cameraSnapshot).toHaveBeenCalledTimes(2);
  expect(await within(dialog()).findByRole("img", { name: "Snapshot to box the fridge on" })).toBeInTheDocument();
});

// Viewer sees the fridge area read-only
test("a viewer sees the area without controls", async () => {
  const { api } = renderTab(SAVED, { role: "viewer" });
  expect(await screen.findByRole("img", { name: "Fridge area" })).toBeInTheDocument();
  expect(screen.getAllByTestId("markup-shape")).toHaveLength(1);
  expect(screen.queryByRole("button", { name: /Set area|Change area|Save/ })).not.toBeInTheDocument();
  drag([10, 10], [40, 50]);
  expect(api.saveFridgeArea).not.toHaveBeenCalled();
});
