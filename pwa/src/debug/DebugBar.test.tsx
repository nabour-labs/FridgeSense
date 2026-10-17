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
  expect(api.startLive).not.toHaveBeenCalled();
  expect(api.cameraFrame).not.toHaveBeenCalled();
  expect(fetchMock).toHaveBeenCalledWith("/__dev/videos");
});

it("Door zone from a clip: Add zone opens the picker and the frame is shown for boxing", async () => {
  switchOn();
  signedIn();
  location.hash = "#config/doors";
  const api = fakeApi();
  render(<App api={api} />);
  await userEvent.click(await screen.findByRole("button", { name: "Add zone" }));
  await useFrame();
  expect(await screen.findByRole("img", { name: "Snapshot to box the zone on" })).toBeInTheDocument();
  expect(api.cameraSnapshot).not.toHaveBeenCalled();
});

/** A stand-in RTCPeerConnection, so the live view starts in jsdom. */
class StubPeer {
  iceGatheringState = "complete";
  connectionState = "new";
  localDescription: RTCSessionDescriptionInit | null = null;
  ontrack = null;
  onconnectionstatechange = null;
  onicegatheringstatechange = null;
  addTransceiver() {}
  async createOffer() {
    return { type: "offer", sdp: "v=0\r\n" };
  }
  async setLocalDescription(d: RTCSessionDescriptionInit) {
    this.localDescription = d;
  }
  async setRemoteDescription() {}
  close() {}
}

it("Switch off: a live view is opened once and no picker opens", async () => {
  vi.stubGlobal("RTCPeerConnection", StubPeer);
  signedIn();
  location.hash = "#config/refs";
  const api = fakeApi();
  render(<App api={api} />);
  await userEvent.click(await screen.findByRole("button", { name: "Add" }));
  await userEvent.click(screen.getByRole("button", { name: "Camera snapshot" }));
  await waitFor(() => expect(api.startLive).toHaveBeenCalledTimes(1));
  expect(api.cameraSnapshot).not.toHaveBeenCalled();
  expect(screen.queryByRole("dialog", { name: "Snapshot from a clip" })).not.toBeInTheDocument();
  expect(fetchMock).not.toHaveBeenCalled();
});

it.each([
  ["Open/close detection", "#config/doors", "Add zone"],
  ["Fridge area", "#config/fridge", "Set area"],
])("Switch off: %s takes its snapshot from a live view", async (_, hash, button) => {
  vi.stubGlobal("RTCPeerConnection", StubPeer);
  signedIn();
  location.hash = hash;
  const api = fakeApi();
  render(<App api={api} />);
  await userEvent.click(await screen.findByRole("button", { name: button }));
  await waitFor(() => expect(api.startLive).toHaveBeenCalledTimes(1));
  expect(api.cameraSnapshot).not.toHaveBeenCalled();
});

it("Switch off without WebRTC: the Ring still is used", async () => {
  signedIn();
  location.hash = "#config/refs";
  const api = fakeApi({ cameraSnapshot: vi.fn().mockResolvedValue(SNAPSHOT) });
  render(<App api={api} />);
  await userEvent.click(await screen.findByRole("button", { name: "Add" }));
  await userEvent.click(screen.getByRole("button", { name: "Camera snapshot" }));
  expect(await screen.findByRole("img", { name: "Reference to draw on" })).toBeInTheDocument();
  expect(api.startLive).not.toHaveBeenCalled();
  expect(api.cameraSnapshot).toHaveBeenCalledTimes(1);
});

it("Closing the door sheet ends the live view and sends no frame", async () => {
  vi.stubGlobal("RTCPeerConnection", StubPeer);
  signedIn();
  location.hash = "#config/doors";
  const api = fakeApi({ startLive: vi.fn().mockResolvedValue({ answer: "v=0\r\n", session_id: "S1", max_seconds: 60 }) });
  const errors = vi.spyOn(console, "error");
  render(<App api={api} />);
  await userEvent.click(await screen.findByRole("button", { name: "Add zone" }));
  await waitFor(() => expect(api.startLive).toHaveBeenCalledTimes(1));
  await userEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Close" }));
  await waitFor(() => expect(api.stopLive).toHaveBeenCalledWith("S1"));
  expect(api.cameraFrame).not.toHaveBeenCalled();
  expect(api.cameraSnapshot).not.toHaveBeenCalled();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(errors).not.toHaveBeenCalled();
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
