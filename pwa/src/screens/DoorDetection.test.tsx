import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApiError } from "../api/client";
import type { Box, DoorReference, DoorSetup, DoorZone } from "../api/types";
import { AppContext, type Api } from "../AppContext";
import { drag, fakeApi } from "../test-utils";
import { CameraOffline, NoVideo } from "../camera/liveSnapshot";
import { DoorDetection } from "./DoorDetection";

const BOX = { x: 0.38, y: 0.32, width: 0.21, height: 0.3 };
const DRAWER_BOX = { x: 0.38, y: 0.65, width: 0.2, height: 0.25 };

function zoneOf(id: string, name: string, open = 0, closed = 0, box: Box = BOX): DoorZone {
  return { id, name, box, open, closed };
}

function doorRef(id: string, status: "open" | "closed", score: number | null = null, zone = "z1"): DoorReference {
  return { id, zone_id: zone, image: "/9j/REF", box: BOX, status, score, created_at: "2026-10-15T19:20:00.000Z" };
}

/** A setup body whose zone counts follow the references (zones default to one "Doors" zone). */
function setupOf(
  references: DoorReference[],
  setup: DoorSetup["setup"] = null,
  zones: DoorZone[] = [zoneOf("z1", "Doors")],
): DoorSetup {
  const count = (z: DoorZone, s: string) => references.filter((r) => r.zone_id === z.id && r.status === s).length;
  return {
    device_id: "ava1.ring.device.D1",
    zones: zones.map((z) => ({ ...z, open: count(z, "open"), closed: count(z, "closed") })),
    references,
    setup,
    defaults: { zones: [{ x: 0.38, y: 0.32, width: 0.21, height: 0.3 }], threshold: 0.02 },
  };
}

const NO_ZONES = setupOf([], null, []);
const TWO_ZONES = [zoneOf("z1", "Doors"), zoneOf("z2", "Drawer", 0, 0, DRAWER_BOX)];

const ZONE = { id: "z1", name: "Doors", ...BOX, feature: "color" as const, direction: "above" as const, threshold: 0.05, margin: 0.1 };
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
  const api = fakeApi({
    doorCalibration: vi.fn().mockResolvedValue(data),
    cameraSnapshot: vi.fn().mockResolvedValue(SNAPSHOT),
    ...overrides,
  });
  const report = vi.fn();
  render(
    <AppContext.Provider value={{ api, role, report, online: vi.fn(), go: vi.fn() }}>
      <DoorDetection />
    </AppContext.Provider>,
  );
  return { api, report };
}

const zonesRegion = () => screen.findByRole("region", { name: "1. Door zones" });
const refsRegion = () => screen.findByRole("region", { name: "2. References" });
const dialog = () => screen.getByRole("dialog");
const zoneGroup = (name: string) => screen.getByRole("group", { name });

// Blue light feature named
test("a blue setup zone is named Blue light", async () => {
  const setup = SET_UP.setup!;
  renderTab({ ...SET_UP, setup: { ...setup, zones: [{ ...setup.zones[0], feature: "blue" }] } });
  expect(await screen.findByText("Doors: Blue light above 5.0%, margin 10.0%")).toBeInTheDocument();
});

test("a setup zone from before zones existed is numbered", async () => {
  const setup = SET_UP.setup!;
  renderTab({ ...SET_UP, setup: { ...setup, zones: [{ ...setup.zones[0], id: null, name: null }] } });
  expect(await screen.findByText("Zone 1: Color above 5.0%, margin 10.0%")).toBeInTheDocument();
});

// References shown
test("zones and their references show box, status, score and the setup state", async () => {
  renderTab(SET_UP);
  expect(within(await zonesRegion()).getByText("Doors")).toBeInTheDocument();
  expect(screen.getByText("1 of 6")).toBeInTheDocument();
  await refsRegion();
  const items = within(zoneGroup("Doors")).getAllByRole("listitem").filter((li) => li.querySelector("img"));
  expect(items).toHaveLength(2);
  expect(within(items[0]).getByText("Open")).toBeInTheDocument();
  expect(within(items[0]).getByText("10.0%")).toBeInTheDocument();
  expect(within(items[1]).getByText("Closed")).toBeInTheDocument();
  expect(within(items[1]).getByText("0.0%")).toBeInTheDocument();
  expect(within(items[0]).getAllByTestId("markup-shape")).toHaveLength(1);
  expect(screen.getByText("2 of 24")).toBeInTheDocument();
  expect(screen.getByText("Doors: Color above 5.0%, margin 10.0%")).toBeInTheDocument();
});

test("a reference with no score shows a dash", async () => {
  renderTab(setupOf([doorRef("a", "open")]));
  expect(await within(await refsRegion()).findByText("–")).toBeInTheDocument();
});

test("a below rule reads below", async () => {
  const zone = { ...ZONE, feature: "brightness" as const, direction: "below" as const, threshold: 0.59, margin: 0.47 };
  renderTab(setupOf([], { zones: [zone], ran_at: "2026-10-15T19:21:00.000Z", stale: false }));
  expect(await screen.findByText("Doors: Brightness below 59.0%, margin 47.0%")).toBeInTheDocument();
});

// Not set up
test("with no zones it asks for one first and nothing else can be done", async () => {
  renderTab(NO_ZONES);
  expect(await screen.findByText("Not set up yet. Using default zones.")).toBeInTheDocument();
  expect(within(await refsRegion()).getByText("Add a door zone first.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Add reference" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Run setup" })).toBeDisabled();
});

async function openAddZone(api: Api) {
  await userEvent.click(await screen.findByRole("button", { name: "Add zone" }));
  expect(api.cameraSnapshot).toHaveBeenCalled();
  return within(dialog()).findByRole("img", { name: "Snapshot to box the zone on" });
}

// Add a door zone
test("adding a zone boxes it on a snapshot and names it", async () => {
  const added = setupOf([], null, [zoneOf("z2", "Freezer drawer", 0, 0, DRAWER_BOX)]);
  const { api } = renderTab(NO_ZONES, { api: { addDoorZone: vi.fn().mockResolvedValue(added) } });
  expect(await openAddZone(api)).toHaveAttribute("src", "data:image/jpeg;base64,/9j/SNAP");
  drag([38, 65], [58, 90]);
  await userEvent.type(within(dialog()).getByLabelText("Name"), "Freezer drawer");
  await userEvent.click(within(dialog()).getByRole("button", { name: "Save" }));
  expect(api.addDoorZone).toHaveBeenCalledWith("Freezer drawer", DRAWER_BOX);
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(within(await zonesRegion()).getByText("Freezer drawer")).toBeInTheDocument();
});

// Zone needs a box and a name
test("Save needs both a zone box and a name", async () => {
  const { api } = renderTab(NO_ZONES);
  await openAddZone(api);
  const save = within(dialog()).getByRole("button", { name: "Save" });
  expect(save).toBeDisabled();
  await userEvent.type(within(dialog()).getByLabelText("Name"), "   ");
  drag([38, 32], [59, 62]);
  expect(save).toBeDisabled();
  await userEvent.type(within(dialog()).getByLabelText("Name"), "Doors");
  expect(save).toBeEnabled();
  expect(api.addDoorZone).not.toHaveBeenCalled();
});

// Redraw replaces the box
test("drawing again replaces the zone box", async () => {
  const { api } = renderTab(NO_ZONES, { api: { addDoorZone: vi.fn().mockResolvedValue(NO_ZONES) } });
  await openAddZone(api);
  drag([10, 10], [40, 50]);
  drag([60, 60], [90, 90]);
  expect(within(dialog()).getAllByTestId("markup-shape")).toHaveLength(1);
  await userEvent.type(within(dialog()).getByLabelText("Name"), "Doors");
  await userEvent.click(within(dialog()).getByRole("button", { name: "Save" }));
  expect(api.addDoorZone).toHaveBeenCalledWith("Doors", { x: 0.6, y: 0.6, width: 0.3, height: 0.3 });
});

// Tiny drag ignored
test("a tiny drag draws no zone box", async () => {
  const { api } = renderTab(NO_ZONES);
  await openAddZone(api);
  drag([50, 50], [51, 90]);
  expect(within(dialog()).queryAllByTestId("markup-shape")).toHaveLength(0);
});

// Edit a zone
test("editing a zone renames and redraws it", async () => {
  const edited = setupOf([], null, [zoneOf("z1", "Fridge doors", 0, 0, { x: 0.6, y: 0.6, width: 0.3, height: 0.3 })]);
  const { api } = renderTab(setupOf([]), { api: { updateDoorZone: vi.fn().mockResolvedValue(edited) } });
  await userEvent.click(await screen.findByRole("button", { name: "Edit Doors" }));
  await within(dialog()).findByRole("img", { name: "Snapshot to box the zone on" });
  expect(within(dialog()).getAllByTestId("markup-shape")).toHaveLength(1); // the current box
  const name = within(dialog()).getByLabelText("Name");
  expect(name).toHaveValue("Doors");
  await userEvent.clear(name);
  await userEvent.type(name, "Fridge doors");
  drag([60, 60], [90, 90]);
  await userEvent.click(within(dialog()).getByRole("button", { name: "Save" }));
  expect(api.updateDoorZone).toHaveBeenCalledWith("z1", {
    name: "Fridge doors",
    box: { x: 0.6, y: 0.6, width: 0.3, height: 0.3 },
  });
  expect(within(await zonesRegion()).getByText("Fridge doors")).toBeInTheDocument();
});

// Delete a zone
test("deleting a zone asks first, naming how many references go with it", async () => {
  const refs = [doorRef("a", "closed", null, "z2"), doorRef("b", "closed", null, "z2"), doorRef("c", "open", null, "z2")];
  const confirm = vi.spyOn(window, "confirm").mockReturnValueOnce(false).mockReturnValueOnce(true);
  const { api } = renderTab(setupOf(refs, null, TWO_ZONES), {
    api: { deleteDoorZone: vi.fn().mockResolvedValue(setupOf([], null, [TWO_ZONES[0]])) },
  });
  const del = await screen.findByRole("button", { name: "Delete Drawer" });
  await userEvent.click(del);
  expect(confirm).toHaveBeenLastCalledWith("Delete Drawer and its 3 references?");
  expect(api.deleteDoorZone).not.toHaveBeenCalled();
  await userEvent.click(del);
  expect(api.deleteDoorZone).toHaveBeenCalledWith("z2");
  expect(await screen.findByText("0 of 24")).toBeInTheDocument();
  expect(within(await zonesRegion()).queryByText("Drawer")).not.toBeInTheDocument();
  confirm.mockRestore();
});

async function openAddReference(api: Api) {
  await userEvent.click(await screen.findByRole("button", { name: "Add reference" }));
  expect(api.cameraSnapshot).toHaveBeenCalled();
  return within(dialog()).findByRole("img", { name: "Snapshot of the door zone" });
}

// Add a door reference
test("adding a reference picks its zone, shows the zone's box and labels it", async () => {
  const added = setupOf([doorRef("a", "open", null, "z2")], null, TWO_ZONES);
  const { api } = renderTab(setupOf([], null, TWO_ZONES), {
    api: { addDoorReference: vi.fn().mockResolvedValue(added) },
  });
  expect(await openAddReference(api)).toHaveAttribute("src", "data:image/jpeg;base64,/9j/SNAP");
  expect(within(dialog()).queryAllByTestId("markup-shape")).toHaveLength(0);
  await userEvent.click(within(dialog()).getByRole("button", { name: "Drawer" }));
  expect(within(dialog()).getAllByTestId("markup-shape")).toHaveLength(1);
  await userEvent.click(within(dialog()).getByRole("button", { name: "Open" }));
  await userEvent.click(within(dialog()).getByRole("button", { name: "Save" }));
  expect(api.addDoorReference).toHaveBeenCalledWith("/9j/SNAP", "z2", "open");
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(await screen.findByText("1 of 24")).toBeInTheDocument();
  expect(within(zoneGroup("Drawer")).getByText("Open")).toBeInTheDocument();
});

// Box and status required (now: zone and status)
test("Save needs both a zone and a status", async () => {
  const { api } = renderTab(setupOf([], null, TWO_ZONES));
  await openAddReference(api);
  const save = within(dialog()).getByRole("button", { name: "Save" });
  expect(save).toBeDisabled();
  await userEvent.click(within(dialog()).getByRole("button", { name: "Closed" }));
  expect(save).toBeDisabled();
  await userEvent.click(within(dialog()).getByRole("button", { name: "Doors" }));
  expect(save).toBeEnabled();
  expect(api.addDoorReference).not.toHaveBeenCalled();
});

test("the reference snapshot cannot be drawn on", async () => {
  const { api } = renderTab(setupOf([]));
  await openAddReference(api);
  drag([60, 60], [90, 90]);
  expect(within(dialog()).getAllByTestId("markup-shape")).toHaveLength(1); // still only the zone's box
});

// Only one zone
test("with one zone it is already picked and its box drawn", async () => {
  const { api } = renderTab(setupOf([]));
  await openAddReference(api);
  expect(within(dialog()).getByRole("button", { name: "Doors" })).toHaveAttribute("aria-pressed", "true");
  expect(within(dialog()).getAllByTestId("markup-shape")).toHaveLength(1);
});

// Camera not sending video
test("a camera that sends no video says so and offers Try again", async () => {
  const cameraSnapshot = vi.fn().mockRejectedValueOnce(new NoVideo()).mockResolvedValueOnce(SNAPSHOT);
  const { report } = renderTab(setupOf([]), { api: { cameraSnapshot } });
  await userEvent.click(await screen.findByRole("button", { name: "Add reference" }));
  expect(await within(dialog()).findByRole("alert")).toHaveTextContent(
    "The camera isn't sending video. Check that it's plugged in.",
  );
  expect(report).not.toHaveBeenCalled();
  await userEvent.click(within(dialog()).getByRole("button", { name: "Try again" }));
  expect(cameraSnapshot).toHaveBeenCalledTimes(2);
});

// Snapshot fails while adding
test.each([
  ["Add zone", "Snapshot to box the zone on"],
  ["Add reference", "Snapshot of the door zone"],
])("%s with no recent footage offers Try again", async (button, img) => {
  const cameraSnapshot = vi
    .fn()
    .mockRejectedValueOnce(new ApiError(409, "no recent footage"))
    .mockResolvedValueOnce(SNAPSHOT);
  renderTab(setupOf([]), { api: { cameraSnapshot } });
  await userEvent.click(await screen.findByRole("button", { name: button }));
  expect(await within(dialog()).findByRole("alert")).toHaveTextContent(
    "No recent footage. Walk past the camera, then try again.",
  );
  await userEvent.click(within(dialog()).getByRole("button", { name: "Try again" }));
  expect(cameraSnapshot).toHaveBeenCalledTimes(2);
  expect(await within(dialog()).findByRole("img", { name: img })).toBeInTheDocument();
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
  expect(await screen.findByText("0 of 24")).toBeInTheDocument();
  confirm.mockRestore();
});

// Zone checklist
test("each zone shows its counts and what it still needs", async () => {
  const refs = [
    doorRef("a", "open"),
    doorRef("b", "open"),
    doorRef("c", "closed"),
    doorRef("d", "closed", null, "z2"),
  ];
  renderTab(setupOf(refs, null, TWO_ZONES));
  await refsRegion();
  expect(within(zoneGroup("Doors")).getByText("2 open · 1 closed")).toBeInTheDocument();
  expect(within(zoneGroup("Doors")).queryByText(/Needs/)).not.toBeInTheDocument();
  expect(within(zoneGroup("Drawer")).getByText("0 open · 1 closed")).toBeInTheDocument();
  expect(within(zoneGroup("Drawer")).getByText("Needs an open reference")).toBeInTheDocument();
});

test("a zone with no references needs both", async () => {
  renderTab(setupOf([]));
  await refsRegion();
  expect(within(zoneGroup("Doors")).getByText("Needs an open and a closed reference")).toBeInTheDocument();
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
  expect(await screen.findByText("Doors: Color above 5.0%, margin 10.0%")).toBeInTheDocument();
  expect(screen.getByText("10.0%")).toBeInTheDocument();
});

// Setup fails
test("a failed setup shows the error and the scores it measured", async () => {
  const body = {
    error: "Doors: open and closed references overlap",
    references: [doorRef("a", "open", 0.005), doorRef("b", "closed", 0.004)],
  };
  renderTab(setupOf([doorRef("a", "open"), doorRef("b", "closed")]), {
    api: { runDoorSetup: vi.fn().mockRejectedValue(new ApiError(422, body.error, body)) },
  });
  await userEvent.click(await screen.findByRole("button", { name: "Run setup" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Doors: open and closed references overlap");
  expect(screen.getByText("0.5%")).toBeInTheDocument();
  expect(screen.getByText("0.4%")).toBeInTheDocument();
});

// Run setup needs both statuses
test("a zone without both statuses disables Run setup with a hint", async () => {
  renderTab(setupOf([doorRef("a", "open"), doorRef("b", "closed"), doorRef("c", "closed", null, "z2")], null, TWO_ZONES));
  expect(await screen.findByRole("button", { name: "Run setup" })).toBeDisabled();
  expect(screen.getByText("Each zone needs at least one open and one closed reference.")).toBeInTheDocument();
});

// Stale setup
test("a stale setup asks to run it again", async () => {
  renderTab({ ...SET_UP, setup: { ...SET_UP.setup!, stale: true } });
  expect(await screen.findByText("Zones or references changed. Run setup again.")).toBeInTheDocument();
});

// Viewer sees setup read-only
test("a viewer sees zones and references without controls", async () => {
  const { api } = renderTab(SET_UP, { role: "viewer" });
  await refsRegion();
  expect(within(zoneGroup("Doors")).getAllByText(/^(Open|Closed)$/)).toHaveLength(2);
  expect(screen.queryByRole("button", { name: /Add|Edit|Delete|Run setup/ })).not.toBeInTheDocument();
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
  await screen.findByText("Doors: Color above 5.0%, margin 10.0%");
  expect(screen.queryByText(/Adjusted for camera shift/)).not.toBeInTheDocument();
  expect(screen.queryByText(/Tuned from/)).not.toBeInTheDocument();
  expect(screen.queryByText(/Camera moved/)).not.toBeInTheDocument();
});

// Door reference while the camera is offline
test("an offline camera warns in the add sheet and offers Try again", async () => {
  const cameraSnapshot = vi.fn().mockRejectedValueOnce(new CameraOffline()).mockResolvedValueOnce(SNAPSHOT);
  const { report } = renderTab(setupOf([]), { api: { cameraSnapshot } });
  await userEvent.click(await screen.findByRole("button", { name: "Add reference" }));
  expect(await within(dialog()).findByRole("alert")).toHaveTextContent(
    "The camera is offline. Check that it's plugged in and connected to Wi-Fi.",
  );
  expect(report).not.toHaveBeenCalled();
  await userEvent.click(within(dialog()).getByRole("button", { name: "Try again" }));
  expect(cameraSnapshot).toHaveBeenCalledTimes(2);
});
