import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AppContext, type Api } from "../AppContext";
import { LiveStream } from "../components/LiveStream";
import { fakeApi } from "../test-utils";
import { DebugContext } from "./DebugContext";

const CLIPS = {
  clips: [
    { name: "Ring_Fridge_20261015_2025.mp4", size: 16246581, url: "/__dev/videos/Ring_Fridge_20261015_2025.mp4" },
    { name: "Ring_Fridge_20261015_1920.mp4", size: 8266528, url: "/__dev/videos/Ring_Fridge_20261015_1920.mp4" },
  ],
  upload: false,
};

function serve(body: unknown) {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(body), { headers: { "content-type": "application/json" } })));
}

afterEach(() => vi.unstubAllGlobals());

/** A peer that gets as far as sending the offer. */
class OfferPeer {
  iceGatheringState = "complete";
  localDescription: RTCSessionDescriptionInit | null = null;
  addTransceiver() {}
  async createOffer() {
    return { type: "offer", sdp: "v=0\r\noffer\r\n" };
  }
  async setLocalDescription(d: RTCSessionDescriptionInit) {
    this.localDescription = d;
  }
  async setRemoteDescription() {}
  close() {}
}
const peer = () => new OfferPeer() as unknown as RTCPeerConnection;

function renderLive(mockVideo: boolean, api: Api = fakeApi()) {
  render(
    <DebugContext.Provider value={{ mockVideo }}>
      <AppContext.Provider value={{ api, role: "owner", report: vi.fn(), online: vi.fn(), go: vi.fn() }}>
        <LiveStream onClose={vi.fn()} createPeer={peer} />
      </AppContext.Provider>
    </DebugContext.Provider>,
  );
  return api;
}

const video = () => screen.getByTestId("clip-live") as HTMLVideoElement;

it("Livestream from a clip: plays the newest clip muted on a loop, with no live view", async () => {
  serve(CLIPS);
  const api = renderLive(true);
  expect(await screen.findByRole("combobox", { name: "Clip" })).toHaveTextContent("Ring_Fridge_20261015_2025.mp4");
  expect(screen.getByRole("dialog", { name: "Livestream" })).toHaveTextContent("Mock video");
  expect(video()).toHaveAttribute("src", "/__dev/videos/Ring_Fridge_20261015_2025.mp4");
  expect(video().muted).toBe(true);
  expect(video().loop).toBe(true);
  expect(video().autoplay).toBe(true);
  expect(api.startLive).not.toHaveBeenCalled();
  expect(api.stopLive).not.toHaveBeenCalled();
});

it("Change clip: the player switches to the picked clip", async () => {
  serve(CLIPS);
  renderLive(true);
  await userEvent.click(await screen.findByRole("combobox", { name: "Clip" }));
  await userEvent.click(screen.getByRole("option", { name: "Ring_Fridge_20261015_1920.mp4" }));
  expect(video()).toHaveAttribute("src", "/__dev/videos/Ring_Fridge_20261015_1920.mp4");
});

it("Livestream with no clips: says so and asks nothing of the camera", async () => {
  serve({ clips: [], upload: false });
  const api = renderLive(true);
  expect(await screen.findByText("No clips in the videos folder")).toBeInTheDocument();
  expect(api.startLive).not.toHaveBeenCalled();
});

it("Livestream switch off: the live view starts as before, with no clip dropdown", async () => {
  serve(CLIPS);
  const api = renderLive(false);
  await waitFor(() => expect(api.startLive).toHaveBeenCalledWith("v=0\r\noffer\r\n"));
  expect(screen.queryByRole("combobox", { name: "Clip" })).not.toBeInTheDocument();
  expect(screen.getByText("Connecting…")).toBeInTheDocument();
});

it("Mock video Livestream is wide", async () => {
  serve(CLIPS);
  renderLive(true);
  const dialog = await screen.findByRole("dialog", { name: "Livestream" });
  expect(dialog).toHaveClass("sm:max-w-3xl");
  expect(dialog).not.toHaveClass("max-w-md");
  await screen.findByRole("combobox", { name: "Clip" });
});
