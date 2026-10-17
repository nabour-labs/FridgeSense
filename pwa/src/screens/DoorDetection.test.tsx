import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApiError } from "../api/client";
import type { DoorReference, DoorSetup } from "../api/types";
import { AppContext, type Api } from "../AppContext";
import { drag, fakeApi } from "../test-utils";
import { NoVideo } from "../camera/liveSnapshot";
import { DoorDetection } from "./DoorDetection";

const BOX = { x: 0.38, y: 0.32, width: 0.21, height: 0.3 };

function doorRef(id: string, status: "open" | "closed", score: number | null = null): DoorReference {
  return { id, image: "/9j/REF", box: BOX, status, score, created_at: "2026-10-15T19:20:00.000Z" };
}

function setupOf(references: DoorReference[], setup: DoorSetup["setup"] = null): DoorSetup {
  return {
    device_id: "ava1.ring.device.D1",
    references,
    setup,
    defaults: { zones: [{ x: 0.38, y: 0.32, width: 0.21, height: 0.3 }], threshold: 0.02 },
  };
}

const ZONE = { ...BOX, feature: "color" as const, direction: "above" as const, threshold: 0.05, margin: 0.1 };
const SET_UP = setupOf([doorRef("a", "open", 0.1), doorRef("b", "closed", 0)], {
  zones: [ZONE],
  ran_at: "2026-10-15T19:21:00.000Z",
  stale: false,
});
const SNAPSHOT = { image: "/9j/SNAP", captured_at: "2026-10-15T19:20:07.000Z" };

function renderTab(data: DoorSetup, { role = "owner", api: overrides = {} } = {} as {
  role?: "owner" | "viewer";
  api?: Partial<Record<keyof Api, unknown>>;
}) {
  const api = fakeApi({ doorCalibration: vi.fn().mockResolvedValue(data), ...overrides });
  const report = vi.fn();
  render(
    <AppContext.Provider value={{ api, role, report, online: vi.fn(), go: vi.fn() }}>
      <DoorDetection />
    </AppContext.Provider>,
  );
  return { api, report };
}

const refsRegion = () => screen.findByRole("region", { name: "Door references" });
const dialog = () => screen.getByRole("dialog");

// Blue light feature named
test("a blue setup zone is named Blue light", async () => {
  const setup = SET_UP.setup!;
  renderTab({ ...SET_UP, setup: { ...setup, zones: [{ ...setup.zones[0], feature: "blue" }] } });
  expect(await screen.findByText("Zone 1: Blue light above 5.0%, margin 10.0%")).toBeInTheDocument();
});

// References shown
test("references show their box, status, score and the setup state", async () => {
  renderTab(SET_UP);
  const refs = await refsRegion();
  const items = within(refs).getAllByRole("listitem").filter((li) => li.querySelector("img"));
  expect(items).toHaveLength(2);
  expect(within(items[0]).getByText("Open")).toBeInTheDocument();
  expect(within(items[0]).getByText("10.0%")).toBeInTheDocument();
  expect(within(items[1]).getByText("Closed")).toBeInTheDocument();
  expect(within(items[1]).getByText("0.0%")).toBeInTheDocument();
  expect(within(items[0]).getAllByTestId("markup-shape")).toHaveLength(1);
  expect(screen.getByText("2 of 12")).toBeInTheDocument();
  expect(screen.getByText("Zone 1: Color above 5.0%, margin 10.0%")).toBeInTheDocument();
});

test("a reference with no score shows a dash", async () => {
  renderTab(setupOf([doorRef("a", "open")]));
  expect(await within(await refsRegion()).findByText("–")).toBeInTheDocument();
});

test("a below rule reads below", async () => {
  const zone = { ...ZONE, feature: "brightness" as const, direction: "below" as const, threshold: 0.59, margin: 0.47 };
  renderTab(setupOf([], { zones: [zone], ran_at: "2026-10-15T19:21:00.000Z", stale: false }));
  expect(await screen.findByText("Zone 1: Brightness below 59.0%, margin 47.0%")).toBeInTheDocument();
});

// Not set up
test("without a setup it says so and Run setup is disabled", async () => {
  renderTab(setupOf([]));
  expect(await screen.findByText("Not set up yet. Using default zones.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Run setup" })).toBeDisabled();
});

async function openAdd(api: Api) {
  await userEvent.click(await screen.findByRole("button", { name: "Add" }));
  expect(api.cameraSnapshot).toHaveBeenCalled();
  return within(dialog()).findByRole("img", { name: "Snapshot to box the door on" });
}

// Add a door reference
test("adding a reference boxes the door on a snapshot and labels it", async () => {
  const added = setupOf([doorRef("a", "open")]);
  const { api } = renderTab(setupOf([]), {
    api: { cameraSnapshot: vi.fn().mockResolvedValue(SNAPSHOT), addDoorReference: vi.fn().mockResolvedValue(added) },
  });
  expect(await openAdd(api)).toHaveAttribute("src", "data:image/jpeg;base64,/9j/SNAP");
  drag([38, 32], [59, 62]);
  await userEvent.click(within(dialog()).getByRole("button", { name: "Open" }));
  await userEvent.click(within(dialog()).getByRole("button", { name: "Save" }));
  expect(api.addDoorReference).toHaveBeenCalledWith("/9j/SNAP", { x: 0.38, y: 0.32, width: 0.21, height: 0.3 }, "open");
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(await screen.findByText("1 of 12")).toBeInTheDocument();
});

// Box and status required
test("Save needs both a box and a status", async () => {
  const { api } = renderTab(setupOf([]), { api: { cameraSnapshot: vi.fn().mockResolvedValue(SNAPSHOT) } });
  await openAdd(api);
  const save = within(dialog()).getByRole("button", { name: "Save" });
  expect(save).toBeDisabled();
  await userEvent.click(within(dialog()).getByRole("button", { name: "Closed" }));
  expect(save).toBeDisabled();
  drag([38, 32], [59, 62]);
  expect(save).toBeEnabled();
  expect(api.addDoorReference).not.toHaveBeenCalled();
});

// Redraw replaces the box
test("drawing again replaces the box", async () => {
  const { api } = renderTab(setupOf([]), {
    api: { cameraSnapshot: vi.fn().mockResolvedValue(SNAPSHOT), addDoorReference: vi.fn().mockResolvedValue(setupOf([])) },
  });
  await openAdd(api);
  drag([10, 10], [40, 50]);
  drag([60, 60], [90, 90]);
  expect(within(dialog()).getAllByTestId("markup-shape")).toHaveLength(1);
  await userEvent.click(within(dialog()).getByRole("button", { name: "Closed" }));
  await userEvent.click(within(dialog()).getByRole("button", { name: "Save" }));
  expect(api.addDoorReference).toHaveBeenCalledWith("/9j/SNAP", { x: 0.6, y: 0.6, width: 0.3, height: 0.3 }, "closed");
});

// Tiny drag ignored
test("a tiny drag draws no box", async () => {
  const { api } = renderTab(setupOf([]), { api: { cameraSnapshot: vi.fn().mockResolvedValue(SNAPSHOT) } });
  await openAdd(api);
  drag([50, 50], [51, 90]);
  expect(within(dialog()).queryAllByTestId("markup-shape")).toHaveLength(0);
});

// Camera not sending video
test("a camera that sends no video says so and offers Try again", async () => {
  const cameraSnapshot = vi.fn().mockRejectedValueOnce(new NoVideo()).mockResolvedValueOnce(SNAPSHOT);
  const { report } = renderTab(setupOf([]), { api: { cameraSnapshot } });
  await userEvent.click(await screen.findByRole("button", { name: "Add" }));
  expect(await within(dialog()).findByRole("alert")).toHaveTextContent(
    "The camera isn't sending video. Check that it's plugged in.",
  );
  expect(report).not.toHaveBeenCalled();
  await userEvent.click(within(dialog()).getByRole("button", { name: "Try again" }));
  expect(cameraSnapshot).toHaveBeenCalledTimes(2);
});

// Snapshot fails while adding
test("a snapshot with no recent footage offers Try again", async () => {
  const cameraSnapshot = vi
    .fn()
    .mockRejectedValueOnce(new ApiError(409, "no recent footage"))
    .mockResolvedValueOnce(SNAPSHOT);
  renderTab(setupOf([]), { api: { cameraSnapshot } });
  await userEvent.click(await screen.findByRole("button", { name: "Add" }));
  expect(await within(dialog()).findByRole("alert")).toHaveTextContent(
    "No recent footage. Walk past the camera, then try again.",
  );
  await userEvent.click(within(dialog()).getByRole("button", { name: "Try again" }));
  expect(cameraSnapshot).toHaveBeenCalledTimes(2);
  expect(await within(dialog()).findByRole("img", { name: "Snapshot to box the door on" })).toBeInTheDocument();
});

// Delete a door reference
test("deleting a reference asks first, then removes it", async () => {
  const confirm = vi.spyOn(window, "confirm").mockReturnValueOnce(false).mockReturnValueOnce(true);
  const { api } = renderTab(setupOf([doorRef("a", "open")]), {
    api: { deleteDoorReference: vi.fn().mockResolvedValue(setupOf([])) },
  });
  const del = await screen.findByRole("button", { name: "Delete reference 1" });
  await userEvent.click(del);
  expect(api.deleteDoorReference).not.toHaveBeenCalled();
  await userEvent.click(del);
  expect(api.deleteDoorReference).toHaveBeenCalledWith("a");
  expect(await screen.findByText("0 of 12")).toBeInTheDocument();
  confirm.mockRestore();
});

// Run setup
test("Run setup sends one request, shows busy, then the new state", async () => {
  let finish: (value: DoorSetup) => void = () => {};
  const runDoorSetup = vi.fn().mockReturnValue(new Promise<DoorSetup>((resolve) => (finish = resolve)));
  renderTab(setupOf([doorRef("a", "open"), doorRef("b", "closed")]), { api: { runDoorSetup } });
  await userEvent.click(await screen.findByRole("button", { name: "Run setup" }));
  const busy = screen.getByRole("button", { name: "Running setup…" });
  expect(busy).toBeDisabled();
  await userEvent.click(busy);
  expect(runDoorSetup).toHaveBeenCalledTimes(1);
  finish(SET_UP);
  expect(await screen.findByText("Zone 1: Color above 5.0%, margin 10.0%")).toBeInTheDocument();
  expect(screen.getByText("10.0%")).toBeInTheDocument();
});

// Setup fails
test("a failed setup shows the error and the scores it measured", async () => {
  const body = {
    error: "zone 1: open and closed references overlap",
    references: [doorRef("a", "open", 0.005), doorRef("b", "closed", 0.004)],
  };
  renderTab(setupOf([doorRef("a", "open"), doorRef("b", "closed")]), {
    api: { runDoorSetup: vi.fn().mockRejectedValue(new ApiError(422, body.error, body)) },
  });
  await userEvent.click(await screen.findByRole("button", { name: "Run setup" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("zone 1: open and closed references overlap");
  expect(screen.getByText("0.5%")).toBeInTheDocument();
  expect(screen.getByText("0.4%")).toBeInTheDocument();
});

// Run setup needs both statuses
test("with only closed references Run setup is disabled with a hint", async () => {
  renderTab(setupOf([doorRef("a", "closed"), doorRef("b", "closed")]));
  expect(await screen.findByRole("button", { name: "Run setup" })).toBeDisabled();
  expect(screen.getByText("Add at least one open and one closed reference.")).toBeInTheDocument();
});

// Stale setup
test("a stale setup asks to run it again", async () => {
  renderTab({ ...SET_UP, setup: { ...SET_UP.setup!, stale: true } });
  expect(await screen.findByText("References changed. Run setup again.")).toBeInTheDocument();
});

// Viewer sees read-only config
test("a viewer sees the references without controls", async () => {
  const { api } = renderTab(SET_UP, { role: "viewer" });
  const refs = await refsRegion();
  expect(within(refs).getAllByText(/Open|Closed/)).toHaveLength(2);
  expect(screen.queryByRole("button", { name: /Add|Delete|Run setup/ })).not.toBeInTheDocument();
  drag([10, 10], [40, 50]);
  expect(api.addDoorReference).not.toHaveBeenCalled();
});

const ALIGNED = {
  dx: 0.016,
  dy: 0,
  error: 0.031,
  failures: 0,
  moved: false,
  moved_at: null,
  last_moved_at: null,
  checked_at: new Date(Date.now() - 5 * 60_000).toISOString(),
};

// Shift and tuning shown
test("the camera shift and tuning are shown under the setup", async () => {
  const setup = { ...SET_UP.setup!, tuned_at: new Date(Date.now() - 2 * 3600_000).toISOString(), tuned_from: 8 };
  renderTab({ ...SET_UP, setup, alignment: ALIGNED });
  expect(
    await screen.findByText("Adjusted for camera shift of 1.6% across, 0% down (checked 5 min ago)"),
  ).toBeInTheDocument();
  expect(screen.getByText("Tuned from 8 recent openings, 2 h ago")).toBeInTheDocument();
});

// Moved notice
test("a moved camera asks for new references", async () => {
  const moved = { ...ALIGNED, moved: true, moved_at: ALIGNED.checked_at, last_moved_at: ALIGNED.checked_at };
  renderTab({ ...SET_UP, alignment: moved });
  expect(await screen.findByText("Camera moved: add new references and run setup.")).toBeInTheDocument();
});

// Nothing yet
test("no shift or tuning line before the first event", async () => {
  const fresh = { ...ALIGNED, dx: 0, error: null, checked_at: null };
  renderTab({ ...SET_UP, setup: { ...SET_UP.setup!, tuned_at: null, tuned_from: null }, alignment: fresh });
  await screen.findByText("Zone 1: Color above 5.0%, margin 10.0%");
  expect(screen.queryByText(/Adjusted for camera shift/)).not.toBeInTheDocument();
  expect(screen.queryByText(/Tuned from/)).not.toBeInTheDocument();
  expect(screen.queryByText(/Camera moved/)).not.toBeInTheDocument();
});
