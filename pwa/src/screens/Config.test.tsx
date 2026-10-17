import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { Mock } from "vitest";
import { ApiError } from "../api/client";
import type { Resize } from "../image";
import type { Config as ConfigData, Reference, Role } from "../api/types";
import { AppContext, type Api } from "../AppContext";
import { drag, fakeApi } from "../test-utils";
import { CameraOffline } from "../camera/liveSnapshot";
import { Config } from "./Config";

function ref(id: string, annotation: string): Reference {
  return { id, annotation, image: "/9j/AAAA", created_at: "2026-10-15T08:00:00.000Z" };
}

const MILK = ref("r1", "milk bag");

function renderConfig(
  config: ConfigData,
  { role = "owner", api: overrides = {}, resize = vi.fn().mockResolvedValue("/9j/RESIZED") } = {} as {
    role?: Role;
    api?: Partial<Record<keyof Api, unknown>>;
    resize?: Mock<Resize>;
  },
) {
  const api = fakeApi({ config: vi.fn().mockResolvedValue(config), ...overrides });
  const report = vi.fn();
  if (!location.hash) location.hash = "#config/refs";
  render(
    <AppContext.Provider value={{ api, role, report, online: vi.fn(), go: vi.fn() }}>
      <Config resize={resize} />
    </AppContext.Provider>,
  );
  return { api, report, resize };
}

// Viewer sees read-only config
test("a viewer sees references and instructions without controls", async () => {
  renderConfig({ instructions: "Count yogurt cups individually.", references: [MILK] }, { role: "viewer" });
  const refs = await screen.findByRole("region", { name: "Reference images" });
  expect(within(refs).getByText("milk bag")).toBeInTheDocument();
  expect(within(refs).getByRole("img", { name: "milk bag" })).toHaveAttribute("src", "data:image/jpeg;base64,/9j/AAAA");
  expect(screen.getByText("Count yogurt cups individually.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Add|Delete|Save/ })).not.toBeInTheDocument();
  expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
});

const PHOTO = new File([new Uint8Array([1, 2, 3])], "IMG_0001.jpg", { type: "image/jpeg" });

async function openAdd(annotation?: string) {
  await userEvent.click(await screen.findByRole("button", { name: "Add" }));
  await userEvent.upload(screen.getByLabelText("Choose photo"), PHOTO);
  if (annotation) await userEvent.type(screen.getByLabelText("Annotation"), annotation);
}

// Add a reference
test("adding a reference resizes the photo, uploads it and lists it", async () => {
  const added = { instructions: "", references: [ref("r2", "soda can")] };
  const { api, resize } = renderConfig(
    { instructions: "", references: [] },
    { api: { addReference: vi.fn().mockResolvedValue(added) } },
  );
  await openAdd("soda can");
  await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Save" }));
  expect(resize).toHaveBeenCalledWith(PHOTO);
  expect(api.addReference).toHaveBeenCalledWith("soda can", "/9j/RESIZED");
  const refs = screen.getByRole("region", { name: "Reference images" });
  expect(await within(refs).findByText("soda can")).toBeInTheDocument();
  expect(screen.queryByLabelText("Choose photo")).not.toBeInTheDocument();
});

// Annotation required
test("Save stays disabled until there is an annotation", async () => {
  const { api } = renderConfig({ instructions: "", references: [] });
  await openAdd();
  expect(within(screen.getByRole("dialog")).getByRole("button", { name: "Save" })).toBeDisabled();
  await userEvent.type(screen.getByLabelText("Annotation"), "   ");
  expect(within(screen.getByRole("dialog")).getByRole("button", { name: "Save" })).toBeDisabled();
  expect(api.addReference).not.toHaveBeenCalled();
});

// Limit reached
test("with 6 references the count reads 6 of 6 and Add is disabled", async () => {
  const six = Array.from({ length: 6 }, (_, n) => ref(`r${n}`, `item ${n}`));
  renderConfig({ instructions: "", references: six });
  expect(await screen.findByText("6 of 6")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Add" })).toBeDisabled();
});

test("the count shows how many of 6 are used", async () => {
  renderConfig({ instructions: "", references: [MILK] });
  expect(await screen.findByText("1 of 6")).toBeInTheDocument();
});

// Delete a reference
test("deleting a reference asks first, then removes it", async () => {
  const confirm = vi.spyOn(window, "confirm").mockReturnValueOnce(false).mockReturnValueOnce(true);
  const { api } = renderConfig(
    { instructions: "", references: [MILK] },
    { api: { deleteReference: vi.fn().mockResolvedValue({ instructions: "", references: [] }) } },
  );
  const del = await screen.findByRole("button", { name: "Delete milk bag" });
  await userEvent.click(del);
  expect(api.deleteReference).not.toHaveBeenCalled();
  await userEvent.click(del);
  expect(confirm).toHaveBeenCalledTimes(2);
  expect(api.deleteReference).toHaveBeenCalledWith("r1");
  expect(await screen.findByText("0 of 6")).toBeInTheDocument();
  expect(screen.queryByText("milk bag")).not.toBeInTheDocument();
  confirm.mockRestore();
});

// Upload refused
test.each([
  [400, "image must be a JPEG of at most 200 KB"],
  [409, "at most 6 reference images"],
])("a %i from the API shows its message and keeps the list", async (status, message) => {
  renderConfig(
    { instructions: "", references: [MILK] },
    { api: { addReference: vi.fn().mockRejectedValue(new ApiError(status, message)) } },
  );
  await openAdd("soda can");
  await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Save" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(message);
  const refs = screen.getByRole("region", { name: "Reference images" });
  expect(within(refs).getByText("milk bag")).toBeInTheDocument();
  expect(within(refs).queryByText("soda can")).not.toBeInTheDocument();
});

function instructionsBox() {
  return screen.findByRole("textbox", { name: "Custom instructions" });
}

function saveInstructionsButton() {
  const section = screen.getByRole("region", { name: "Custom instructions" });
  return within(section).getByRole("button", { name: "Save" });
}

// Save instructions
test("saving instructions sends them and confirms with Saved", async () => {
  const saved = { instructions: "Count yogurt cups individually.", references: [] };
  const { api } = renderConfig(
    { instructions: "", references: [] },
    { api: { saveInstructions: vi.fn().mockResolvedValue(saved) } },
  );
  await userEvent.type(await instructionsBox(), "Count yogurt cups individually.");
  expect(screen.getByText("31 / 1000")).toBeInTheDocument();
  await userEvent.click(saveInstructionsButton());
  expect(api.saveInstructions).toHaveBeenCalledWith("Count yogurt cups individually.");
  expect(await screen.findByText("Saved")).toBeInTheDocument();
  expect(saveInstructionsButton()).toBeDisabled();
});

// Over the limit
test("over 1000 characters the count shows it and Save is disabled", async () => {
  const { api } = renderConfig({ instructions: "x".repeat(1000), references: [] });
  const box = await instructionsBox();
  await userEvent.type(box, "y");
  expect(screen.getByText("1001 / 1000")).toBeInTheDocument();
  expect(saveInstructionsButton()).toBeDisabled();
  expect(api.saveInstructions).not.toHaveBeenCalled();
});

// Unchanged text
test("Save is disabled while the text equals the saved instructions", async () => {
  renderConfig({ instructions: "Count yogurt cups individually.", references: [] });
  expect(await instructionsBox()).toHaveValue("Count yogurt cups individually.");
  expect(saveInstructionsButton()).toBeDisabled();
});

// Open config: the Camera tab is selected by default
test("Config opens on the Camera tab", async () => {
  location.hash = "#config";
  const { api } = renderConfig({ instructions: "", references: [] });
  expect(await screen.findByRole("tab", { name: "Camera", selected: true })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Reference images", selected: false })).toBeInTheDocument();
  expect(api.camera).toHaveBeenCalled();
  expect(api.config).not.toHaveBeenCalled();
  location.hash = "";
});

// Reference images tab
test("tapping Reference images switches the tab and the hash", async () => {
  location.hash = "#config";
  const { api } = renderConfig({ instructions: "", references: [] });
  await userEvent.click(await screen.findByRole("tab", { name: "Reference images" }));
  expect(location.hash).toBe("#config/refs");
  expect(api.config).toHaveBeenCalled();
  expect(await screen.findByRole("region", { name: "Reference images" })).toBeInTheDocument();
  expect(screen.getByRole("region", { name: "Custom instructions" })).toBeInTheDocument();
  location.hash = "";
});

// Direct link to reference images
test("#config/refs opens on the Reference images tab", async () => {
  location.hash = "#config/refs";
  renderConfig({ instructions: "", references: [] });
  expect(await screen.findByRole("tab", { name: "Reference images", selected: true })).toBeInTheDocument();
  location.hash = "";
});

// Switch to open/close detection
test("tapping Open/close detection switches the tab and the hash", async () => {
  location.hash = "#config";
  const { api } = renderConfig({ instructions: "", references: [] });
  await userEvent.click(await screen.findByRole("tab", { name: "Open/close detection" }));
  expect(location.hash).toBe("#config/doors");
  expect(screen.getByRole("tab", { name: "Open/close detection", selected: true })).toBeInTheDocument();
  expect(api.doorCalibration).toHaveBeenCalled();
  expect(screen.queryByRole("region", { name: "Reference images" })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("tab", { name: "Reference images" }));
  expect(location.hash).toBe("#config/refs");
  location.hash = "";
});

// Open the detection tab by link
test("#config/doors opens on the detection tab", async () => {
  location.hash = "#config/doors";
  const { api } = renderConfig({ instructions: "", references: [] });
  expect(await screen.findByRole("tab", { name: "Open/close detection", selected: true })).toBeInTheDocument();
  expect(api.doorCalibration).toHaveBeenCalled();
  location.hash = "";
});

// Switch to fridge area
test("tapping Fridge area switches the tab and the hash", async () => {
  location.hash = "#config";
  const { api } = renderConfig({ instructions: "", references: [] });
  await userEvent.click(await screen.findByRole("tab", { name: "Fridge area" }));
  expect(location.hash).toBe("#config/fridge");
  expect(screen.getByRole("tab", { name: "Fridge area", selected: true })).toBeInTheDocument();
  expect(api.fridgeArea).toHaveBeenCalled();
  location.hash = "";
});

// Open the fridge area tab by link
test("#config/fridge opens on the fridge area tab", async () => {
  location.hash = "#config/fridge";
  const { api } = renderConfig({ instructions: "", references: [] });
  expect(await screen.findByRole("tab", { name: "Fridge area", selected: true })).toBeInTheDocument();
  expect(api.fridgeArea).toHaveBeenCalled();
  location.hash = "";
});

const SNAPSHOT = { image: "/9j/SNAP", captured_at: "2026-10-15T19:20:07.000Z" };

async function openSnapshot(api: Api) {
  await userEvent.click(await screen.findByRole("button", { name: "Add" }));
  await userEvent.click(screen.getByRole("button", { name: "Camera snapshot" }));
  expect(api.cameraSnapshot).toHaveBeenCalledTimes(1);
  return within(screen.getByRole("dialog")).findByRole("img", { name: "Reference to draw on" });
}

// Add a camera snapshot
test("a camera snapshot can be added as a reference", async () => {
  const added = { instructions: "", references: [ref("r2", "milk bag")] };
  const { api, resize } = renderConfig(
    { instructions: "", references: [] },
    { api: { cameraSnapshot: vi.fn().mockResolvedValue(SNAPSHOT), addReference: vi.fn().mockResolvedValue(added) } },
  );
  const img = await openSnapshot(api);
  expect(img).toHaveAttribute("src", "data:image/jpeg;base64,/9j/SNAP");
  await userEvent.type(screen.getByLabelText("Annotation"), "milk bag");
  await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Save" }));
  expect(resize).toHaveBeenCalledTimes(1);
  const [blob, shapes] = resize.mock.calls[0];
  expect(blob).toBeInstanceOf(Blob);
  expect((blob as Blob).type).toBe("image/jpeg");
  expect(shapes).toBeUndefined();
  expect(api.addReference).toHaveBeenCalledWith("milk bag", "/9j/RESIZED");
});

// Add a reference from a recent clip
test("a frame from a recent clip can be added as a reference, blurred first", async () => {
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({ drawImage: vi.fn() } as never);
  vi.spyOn(HTMLCanvasElement.prototype, "toBlob").mockImplementation((cb) => cb(new Blob(["raw"], { type: "image/jpeg" })));
  const opened = new Date();
  opened.setHours(18, 2, 0, 0);
  const clipEvent = {
    id: "e1",
    opened_at: opened.toISOString(),
    closed_at: opened.toISOString(),
    duration_s: 25,
    status: "done",
    changes: [],
    pending_count: 0,
    stills: [],
    clip: "https://stills.example.com/clip.mp4?sig=1#t=0.5,8.5",
  };
  const added = { instructions: "", references: [ref("r2", "milk bag")] };
  const { api, resize } = renderConfig(
    { instructions: "", references: [] },
    {
      api: {
        events: vi.fn().mockResolvedValue({ events: [clipEvent] }),
        cameraFrame: vi.fn().mockResolvedValue(SNAPSHOT),
        addReference: vi.fn().mockResolvedValue(added),
      },
    },
  );
  await userEvent.click(await screen.findByRole("button", { name: "Add" }));
  await userEvent.click(screen.getByRole("button", { name: "Recent clip" }));
  const picker = await screen.findByRole("dialog", { name: "Snapshot from a recent clip" });
  expect(await within(picker).findByRole("combobox", { name: "Clip" })).toHaveTextContent("Today 18:02 · 25 s");
  const video = within(picker).getByTestId("clip-video");
  fireEvent.loadedData(video);
  await userEvent.click(within(picker).getByRole("button", { name: "Use this frame" }));
  expect(api.cameraFrame).toHaveBeenCalledWith(btoa("raw"));
  expect(screen.queryByRole("dialog", { name: "Snapshot from a recent clip" })).not.toBeInTheDocument();
  const img = await within(screen.getByRole("dialog")).findByRole("img", { name: "Reference to draw on" });
  expect(img).toHaveAttribute("src", "data:image/jpeg;base64,/9j/SNAP");
  await userEvent.type(screen.getByLabelText("Annotation"), "milk bag");
  await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Save" }));
  const [blob] = resize.mock.calls[0];
  expect((blob as Blob).type).toBe("image/jpeg");
  expect(api.addReference).toHaveBeenCalledWith("milk bag", "/9j/RESIZED");
  vi.restoreAllMocks();
});

// Snapshot with no recent footage
test("a snapshot with no recent footage says so and keeps Choose photo", async () => {
  const { api } = renderConfig(
    { instructions: "", references: [] },
    { api: { cameraSnapshot: vi.fn().mockRejectedValue(new ApiError(409, "no recent footage")) } },
  );
  await userEvent.click(await screen.findByRole("button", { name: "Add" }));
  await userEvent.click(screen.getByRole("button", { name: "Camera snapshot" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("No recent footage. Walk past the camera, then try again.");
  expect(screen.getByLabelText("Choose photo")).toBeInTheDocument();
  expect(api.addReference).not.toHaveBeenCalled();
});

// Draw on the image
test("boxes and lines drawn on the image go into the upload", async () => {
  const { api, resize } = renderConfig(
    { instructions: "", references: [] },
    { api: { cameraSnapshot: vi.fn().mockResolvedValue(SNAPSHOT), addReference: vi.fn().mockResolvedValue({ instructions: "", references: [] }) } },
  );
  await openSnapshot(api);
  await userEvent.click(screen.getByRole("button", { name: "Box" }));
  drag([10, 10], [40, 50]);
  await userEvent.click(screen.getByRole("button", { name: "Line" }));
  drag([50, 50], [90, 90]);
  await userEvent.type(screen.getByLabelText("Annotation"), "milk bag");
  await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Save" }));
  expect(resize.mock.calls[0][1]).toEqual([
    { kind: "box", x1: 0.1, y1: 0.1, x2: 0.4, y2: 0.5 },
    { kind: "line", x1: 0.5, y1: 0.5, x2: 0.9, y2: 0.9 },
  ]);
});

// Undo a shape
test("Undo removes the last shape and is disabled with none left", async () => {
  const { api } = renderConfig(
    { instructions: "", references: [] },
    { api: { cameraSnapshot: vi.fn().mockResolvedValue(SNAPSHOT) } },
  );
  await openSnapshot(api);
  const undo = screen.getByRole("button", { name: "Undo" });
  expect(undo).toBeDisabled();
  drag([10, 10], [40, 50]);
  drag([60, 60], [90, 90]);
  expect(screen.getAllByTestId("markup-shape")).toHaveLength(2);
  await userEvent.click(undo);
  expect(screen.getAllByTestId("markup-shape")).toHaveLength(1);
  await userEvent.click(undo);
  expect(screen.queryAllByTestId("markup-shape")).toHaveLength(0);
  expect(undo).toBeDisabled();
});

// Switch to debug
test("tapping Debug switches the tab and the hash", async () => {
  location.hash = "#config";
  const { api } = renderConfig({ instructions: "", references: [] });
  await userEvent.click(await screen.findByRole("tab", { name: "Debug" }));
  expect(location.hash).toBe("#config/debug");
  expect(screen.getByRole("tab", { name: "Debug", selected: true })).toBeInTheDocument();
  expect(api.debugMotions).toHaveBeenCalled();
  location.hash = "";
});

test("#config/debug/<id> opens one motion on the debug tab", async () => {
  location.hash = "#config/debug/abc";
  const { api } = renderConfig({ instructions: "", references: [] });
  expect(await screen.findByRole("tab", { name: "Debug", selected: true })).toBeInTheDocument();
  expect(api.debugMotion).toHaveBeenCalledWith("abc");
  location.hash = "";
});

// Owner's tabs
test("the owner gets five tabs in one row", async () => {
  location.hash = "#config";
  renderConfig({ instructions: "", references: [] });
  const tabs = await screen.findAllByRole("tab");
  expect(tabs.map((t) => t.getAttribute("aria-label") ?? t.textContent)).toEqual([
    "Camera",
    "Reference images",
    "Open/close detection",
    "Fridge area",
    "Debug",
  ]);
  expect(screen.getByRole("tablist")).toHaveClass("grid-cols-5");
  location.hash = "";
});

// Viewer sees read-only config (no Debug tab)
test("a viewer gets no Debug tab", async () => {
  location.hash = "#config";
  renderConfig({ instructions: "", references: [] }, { role: "viewer" });
  const tabs = await screen.findAllByRole("tab");
  expect(tabs.map((t) => t.getAttribute("aria-label") ?? t.textContent)).toEqual([
    "Camera",
    "Reference images",
    "Open/close detection",
    "Fridge area",
  ]);
  expect(screen.getByRole("tablist")).toHaveClass("grid-cols-4");
  location.hash = "";
});

// Viewer opens the debug link
test("a viewer opening #config/debug sees reference images instead", async () => {
  location.hash = "#config/debug";
  const { api } = renderConfig({ instructions: "", references: [] }, { role: "viewer" });
  expect(await screen.findByRole("tab", { name: "Reference images", selected: true })).toBeInTheDocument();
  expect(api.debugMotions).not.toHaveBeenCalled();
  expect(api.debugMotion).not.toHaveBeenCalled();
  location.hash = "";
});

// User sees no Debug tab
test("a user gets the edit controls but no Debug tab", async () => {
  location.hash = "#config";
  renderConfig({ instructions: "", references: [] }, { role: "user" });
  const tabs = await screen.findAllByRole("tab");
  expect(tabs.map((t) => t.getAttribute("aria-label") ?? t.textContent)).toEqual([
    "Camera",
    "Reference images",
    "Open/close detection",
    "Fridge area",
  ]);
  await userEvent.click(screen.getByRole("tab", { name: "Reference images" }));
  expect(await screen.findByRole("button", { name: "Add" })).toBeInTheDocument();
  location.hash = "";
});

// User opens the debug hash
test("a user opening #config/debug sees reference images instead", async () => {
  location.hash = "#config/debug";
  const { api } = renderConfig({ instructions: "", references: [] }, { role: "user" });
  expect(await screen.findByRole("tab", { name: "Reference images", selected: true })).toBeInTheDocument();
  expect(api.debugMotions).not.toHaveBeenCalled();
  expect(api.debugMotion).not.toHaveBeenCalled();
  location.hash = "";
});

// Setup warning banners on the Config screen
test("setup warnings show above the config tabs", async () => {
  location.hash = "#config/fridge";
  const warnings = vi.fn().mockResolvedValue({
    warnings: [
      {
        code: "camera_moved",
        message: "The camera has moved or changed angle. Update the references so detection stays accurate.",
        since: "2026-10-17T10:00:00.000Z",
        update: ["door_references", "fridge_area"],
      },
    ],
    checked_at: "2026-10-17T12:00:00.000Z",
  });
  renderConfig({ instructions: "", references: [] }, { api: { warnings } });
  const banner = await screen.findByRole("alert");
  expect(within(banner).getByRole("link", { name: "Update door references" })).toBeInTheDocument();
  expect(within(banner).getByRole("link", { name: "Update fridge area" })).toBeInTheDocument();
  location.hash = "";
});

// Reference image while the camera is offline
test("a snapshot from an offline camera warns and keeps Choose photo", async () => {
  const { api } = renderConfig(
    { instructions: "", references: [] },
    { api: { cameraSnapshot: vi.fn().mockRejectedValue(new CameraOffline()) } },
  );
  await userEvent.click(await screen.findByRole("button", { name: "Add" }));
  await userEvent.click(screen.getByRole("button", { name: "Camera snapshot" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "The camera is offline. Check that it's plugged in and connected to Wi-Fi.",
  );
  expect(screen.getByLabelText("Choose photo")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Camera snapshot" })).toBeEnabled();
  expect(screen.queryByRole("img", { name: "Reference to draw on" })).not.toBeInTheDocument();
  expect(api.addReference).not.toHaveBeenCalled();
});
