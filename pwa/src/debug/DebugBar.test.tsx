import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "../App";
import { fakeApi, signedIn } from "../test-utils";

const CLIPS = {
  clips: [{ name: "Ring_Fridge_20261015_2025.mp4", size: 16246581, url: "/__dev/videos/Ring_Fridge_20261015_2025.mp4" }],
  upload: false,
};
const SNAPSHOT = { image: "/9j/SNAP", captured_at: "2026-10-15T19:20:07.000Z" };

let fetchMock: ReturnType<typeof vi.fn>;
beforeEach(() => {
  fetchMock = vi.fn(async () => new Response(JSON.stringify(CLIPS), { headers: { "content-type": "application/json" } }));
  vi.stubGlobal("fetch", fetchMock);
  // jsdom has no canvas: the frame grab draws nothing and encodes "jpeg!".
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({ drawImage: vi.fn() } as never);
  vi.spyOn(HTMLCanvasElement.prototype, "toBlob").mockImplementation((cb) => cb(new Blob(["jpeg!"], { type: "image/jpeg" })));
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
  location.hash = "";
});

const FRAME = btoa("jpeg!");
const switchOn = () => localStorage.setItem("fridgesense.mockVideo", "1");
const picker = () => screen.findByRole("dialog", { name: "Snapshot from a clip" });

async function useFrame() {
  const dialog = await picker();
  await within(dialog).findByRole("combobox", { name: "Clip" });
  fireEvent.loadedData(within(dialog).getByTestId("clip-video"));
  await userEvent.click(within(dialog).getByRole("button", { name: "Use this frame" }));
}

it("Dev server: the Debug bar and an unchecked Mock video switch are shown", async () => {
  signedIn();
  render(<App api={fakeApi()} />);
  const bar = await screen.findByRole("region", { name: "Debug" });
  expect(within(bar).getByRole("switch", { name: "Mock video" })).not.toBeChecked();
});

it("the switch turns on and is remembered", async () => {
  signedIn();
  render(<App api={fakeApi()} />);
  await userEvent.click(await screen.findByRole("switch", { name: "Mock video" }));
  expect(screen.getByRole("switch", { name: "Mock video" })).toBeChecked();
  expect(localStorage.getItem("fridgesense.mockVideo")).toBe("1");
});

it("Production build: no Debug bar, no switch, and no clip requests", async () => {
  vi.stubEnv("DEV", false);
  switchOn();
  signedIn();
  location.hash = "#config/refs";
  const api = fakeApi({ cameraSnapshot: vi.fn().mockResolvedValue(SNAPSHOT) });
  render(<App api={api} />);
  await userEvent.click(await screen.findByRole("button", { name: "Add" }));
  await userEvent.click(screen.getByRole("button", { name: "Camera snapshot" }));
  expect(api.cameraSnapshot).toHaveBeenCalledTimes(1);
  expect(screen.queryByRole("region", { name: "Debug" })).not.toBeInTheDocument();
  expect(screen.queryByRole("switch", { name: "Mock video" })).not.toBeInTheDocument();
  expect(fetchMock).not.toHaveBeenCalled();
});

it("Reference image from a clip: the frame is used and the camera is not asked", async () => {
  switchOn();
  signedIn();
  location.hash = "#config/refs";
  const api = fakeApi();
  render(<App api={api} />);
  await userEvent.click(await screen.findByRole("button", { name: "Add" }));
  await userEvent.click(screen.getByRole("button", { name: "Camera snapshot" }));
  await useFrame();
  expect(await screen.findByRole("img", { name: "Reference to draw on" })).toHaveAttribute("src", `data:image/jpeg;base64,${FRAME}`);
  expect(api.cameraSnapshot).not.toHaveBeenCalled();
  expect(fetchMock).toHaveBeenCalledWith("/__dev/videos");
});

it("Door reference from a clip: Add opens the picker and the frame is shown for boxing", async () => {
  switchOn();
  signedIn();
  location.hash = "#config/doors";
  const api = fakeApi();
  render(<App api={api} />);
  await userEvent.click(await screen.findByRole("button", { name: "Add" }));
  await useFrame();
  expect(await screen.findByRole("img", { name: "Snapshot to box the door on" })).toBeInTheDocument();
  expect(api.cameraSnapshot).not.toHaveBeenCalled();
});

it("Switch off: the camera is asked once and no picker opens", async () => {
  signedIn();
  location.hash = "#config/refs";
  const api = fakeApi({ cameraSnapshot: vi.fn().mockResolvedValue(SNAPSHOT) });
  render(<App api={api} />);
  await userEvent.click(await screen.findByRole("button", { name: "Add" }));
  await userEvent.click(screen.getByRole("button", { name: "Camera snapshot" }));
  expect(await screen.findByRole("img", { name: "Reference to draw on" })).toBeInTheDocument();
  expect(api.cameraSnapshot).toHaveBeenCalledTimes(1);
  expect(screen.queryByRole("dialog", { name: "Snapshot from a clip" })).not.toBeInTheDocument();
  expect(fetchMock).not.toHaveBeenCalled();
});

it("Cancel: the picker closes with no snapshot, no error and no request", async () => {
  switchOn();
  signedIn();
  location.hash = "#config/refs";
  const api = fakeApi();
  const errors = vi.spyOn(console, "error");
  render(<App api={api} />);
  await userEvent.click(await screen.findByRole("button", { name: "Add" }));
  await userEvent.click(screen.getByRole("button", { name: "Camera snapshot" }));
  const dialog = await picker();
  await userEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
  await waitFor(() => expect(screen.queryByRole("dialog", { name: "Snapshot from a clip" })).not.toBeInTheDocument());
  expect(screen.queryByRole("img", { name: "Reference to draw on" })).not.toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Camera snapshot" })).toBeEnabled();
  expect(api.cameraSnapshot).not.toHaveBeenCalled();
  expect(errors).not.toHaveBeenCalled();
});
