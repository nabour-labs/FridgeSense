import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { useState } from "react";
import { ApiError } from "../api/client";
import type { LiveSession } from "../api/types";
import { AppContext, type Api } from "../AppContext";
import { fakeApi } from "../test-utils";
import { LiveStream, type DecoderStats } from "./LiveStream";

/** A stand-in RTCPeerConnection: records what the dialog does and lets a test fire events. */
class FakePeer {
  transceivers: [string, RTCRtpTransceiverInit | undefined][] = [];
  closed = 0;
  iceGatheringState: RTCIceGatheringState = "complete";
  connectionState: RTCPeerConnectionState = "new";
  localDescription: RTCSessionDescriptionInit | null = null;
  remoteDescription: RTCSessionDescriptionInit | null = null;
  ontrack: ((e: { streams: MediaStream[] }) => void) | null = null;
  onconnectionstatechange: (() => void) | null = null;
  onicegatheringstatechange: (() => void) | null = null;
  addTransceiver(kind: string, init?: RTCRtpTransceiverInit) {
    this.transceivers.push([kind, init]);
  }
  async createOffer() {
    return { type: "offer" as const, sdp: "v=0\r\noffer\r\n" };
  }
  async setLocalDescription(d: RTCSessionDescriptionInit) {
    this.localDescription = d;
  }
  /** Fire the video track while the answer is applied, as browsers do. */
  trackOnAnswer = false;
  async setRemoteDescription(d: RTCSessionDescriptionInit) {
    this.remoteDescription = d;
    if (this.trackOnAnswer) {
      this.framesDecoded = 1;
      this.ontrack?.({ streams: [{ id: "stream" } as unknown as MediaStream] });
    }
  }
  close() {
    this.closed += 1;
  }
  statsCalls = 0;
  /** Video frames the browser has decoded; 0 while the camera sends nothing. */
  framesDecoded = 0;
  async getStats() {
    this.statsCalls += 1;
    return new Map<string, Record<string, unknown>>([
      ["A1", { type: "inbound-rtp", kind: "audio", codecId: "C2" }],
      [
        "V1",
        {
          type: "inbound-rtp",
          kind: "video",
          codecId: "C1",
          decoderImplementation: "ExternalDecoder",
          frameWidth: 1920,
          frameHeight: 1080,
          framesPerSecond: 15,
          framesDecoded: this.framesDecoded,
        },
      ],
      ["C1", { type: "codec", mimeType: "video/H264" }],
      ["C2", { type: "codec", mimeType: "audio/opus" }],
    ]);
  }
  /** Video arrives and decodes. */
  track() {
    this.framesDecoded = 1;
    act(() => this.ontrack?.({ streams: [{ id: "stream" } as unknown as MediaStream] }));
  }
  /** The track arrives but the camera sends no video (unplugged). */
  trackWithoutVideo() {
    act(() => this.ontrack?.({ streams: [{ id: "stream" } as unknown as MediaStream] }));
  }
  fail() {
    this.connectionState = "failed";
    act(() => this.onconnectionstatechange?.());
  }
}

const SESSION: LiveSession = { answer: "v=0\r\nanswer\r\n", session_id: "S1", max_seconds: 60 };

/** Let pending promises (offer, API answer) settle. */
const settle = () => act(() => vi.advanceTimersByTimeAsync(0));
const wait = (ms: number) => act(() => vi.advanceTimersByTimeAsync(ms));

function Harness({
  createPeer,
  onStats,
}: {
  createPeer: () => RTCPeerConnection | null;
  onStats?: (stats: DecoderStats) => void;
}) {
  const [open, setOpen] = useState(true);
  return open ? <LiveStream onClose={() => setOpen(false)} createPeer={createPeer} onStats={onStats} /> : <p>closed</p>;
}

function renderLive(
  overrides: Partial<Record<keyof Api, unknown>> = {},
  createPeer?: () => RTCPeerConnection | null,
  onStats?: (stats: DecoderStats) => void,
) {
  const peers: FakePeer[] = [];
  const api = fakeApi({ startLive: vi.fn().mockResolvedValue(SESSION), ...overrides });
  const report = vi.fn();
  const make =
    createPeer ??
    (() => {
      const p = new FakePeer();
      peers.push(p);
      return p as unknown as RTCPeerConnection;
    });
  render(
    <AppContext.Provider value={{ api, role: "viewer", report, online: vi.fn(), go: vi.fn() }}>
      <Harness createPeer={make} onStats={onStats} />
    </AppContext.Provider>,
  );
  return { api, peers, report };
}

function closeDialog() {
  fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Close" }));
}

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

test("Live video plays", async () => {
  const { api, peers } = renderLive();
  expect(screen.getByRole("dialog", { name: "Livestream" })).toBeInTheDocument();
  expect(screen.getByText("Connecting…")).toBeInTheDocument();
  await settle();
  const peer = peers[0];
  expect(peer.transceivers).toEqual([
    ["video", { direction: "recvonly" }],
    ["audio", { direction: "recvonly" }],
  ]);
  expect(api.startLive).toHaveBeenCalledWith("v=0\r\noffer\r\n");
  expect(peer.remoteDescription).toEqual({ type: "answer", sdp: SESSION.answer });
  expect(screen.getByText("Connecting…")).toBeInTheDocument();
  peer.track();
  const video = screen.getByTestId("live-video") as HTMLVideoElement;
  expect(video.srcObject).toEqual({ id: "stream" });
  expect(video.muted).toBe(true);
  expect(video).toHaveAttribute("playsinline");
  expect(screen.getByText("60 s left")).toBeInTheDocument();
  expect(screen.queryByText("Connecting…")).not.toBeInTheDocument();
});

test("Countdown", async () => {
  const { peers } = renderLive();
  await settle();
  peers[0].track();
  await wait(15_000);
  expect(screen.getByText("45 s left")).toBeInTheDocument();
});

test("Close stops the stream", async () => {
  const { api, peers } = renderLive();
  await settle();
  peers[0].track();
  closeDialog();
  expect(screen.getByText("closed")).toBeInTheDocument();
  expect(peers[0].closed).toBe(1);
  expect(api.stopLive).toHaveBeenCalledTimes(1);
  expect(api.stopLive).toHaveBeenCalledWith("S1");
});

test("Time runs out", async () => {
  const { api, peers } = renderLive();
  await settle();
  peers[0].track();
  await wait(60_000);
  expect(peers[0].closed).toBe(1);
  expect(api.stopLive).toHaveBeenCalledWith("S1");
  expect(screen.getByText("Stream ended")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Watch again" })).toBeInTheDocument();
  expect(screen.queryByTestId("live-video")).not.toBeInTheDocument();
});

test("Watch again", async () => {
  const { api, peers } = renderLive();
  await settle();
  peers[0].track();
  await wait(60_000);
  fireEvent.click(screen.getByRole("button", { name: "Watch again" }));
  expect(screen.getByText("Connecting…")).toBeInTheDocument();
  await settle();
  expect(peers).toHaveLength(2);
  expect(api.startLive).toHaveBeenCalledTimes(2);
  expect(api.stopLive).toHaveBeenCalledTimes(1);
});

test("Closed while connecting", async () => {
  let answer!: (s: LiveSession) => void;
  const { api, peers } = renderLive({
    startLive: vi.fn().mockReturnValue(new Promise<LiveSession>((r) => (answer = r))),
  });
  await settle();
  closeDialog();
  expect(peers[0].closed).toBe(1);
  expect(api.stopLive).not.toHaveBeenCalled();
  await act(async () => answer({ ...SESSION, session_id: "S2" }));
  await settle();
  expect(api.stopLive).toHaveBeenCalledTimes(1);
  expect(api.stopLive).toHaveBeenCalledWith("S2");
  expect(peers[0].remoteDescription).toBeNull();
});

test("Camera unavailable", async () => {
  const { peers, report } = renderLive({
    startLive: vi.fn().mockRejectedValue(new ApiError(502, "camera unavailable")),
  });
  await settle();
  expect(screen.getByText("The camera is not available right now.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  expect(peers[0].closed).toBe(1);
  expect(report).not.toHaveBeenCalled();
});

test("Try again after an error", async () => {
  const startLive = vi.fn().mockRejectedValueOnce(new ApiError(502, "camera unavailable")).mockResolvedValue(SESSION);
  const { peers } = renderLive({ startLive });
  await settle();
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  await settle();
  peers[1].track();
  expect(screen.getByText("60 s left")).toBeInTheDocument();
});

test("No camera", async () => {
  renderLive({ startLive: vi.fn().mockRejectedValue(new ApiError(409, "no camera found")) });
  await settle();
  expect(screen.getByText("No camera is linked yet.")).toBeInTheDocument();
});

const NO_VIDEO = "The camera isn't sending video. Check that it's plugged in.";

test("Video never arrives", async () => {
  const { api, peers } = renderLive();
  await settle();
  peers[0].trackWithoutVideo();
  expect(screen.getByText("60 s left")).toBeInTheDocument();
  await wait(15_000);
  expect(peers[0].closed).toBe(1);
  expect(api.stopLive).toHaveBeenCalledWith("S1");
  expect(screen.getByText(NO_VIDEO)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
});

test("Video never arrives, not even a track", async () => {
  const { peers } = renderLive();
  await settle();
  await wait(15_000);
  expect(peers[0].closed).toBe(1);
  expect(screen.getByText(NO_VIDEO)).toBeInTheDocument();
});

test("Video track arrives before the answer is applied", async () => {
  const peers: FakePeer[] = [];
  renderLive({}, () => {
    const p = new FakePeer();
    p.trackOnAnswer = true;
    peers.push(p);
    return p as unknown as RTCPeerConnection;
  });
  await settle();
  expect(screen.getByText("60 s left")).toBeInTheDocument();
  await wait(20_000);
  expect(peers[0].closed).toBe(0);
  expect(screen.getByText("40 s left")).toBeInTheDocument();
  expect(screen.queryByText("Could not connect to the camera.")).not.toBeInTheDocument();
});

test("Connection fails", async () => {
  const { api, peers } = renderLive();
  await settle();
  peers[0].track();
  peers[0].fail();
  expect(peers[0].closed).toBe(1);
  expect(api.stopLive).toHaveBeenCalledWith("S1");
  expect(screen.getByText("Could not connect to the camera.")).toBeInTheDocument();
});

test("Waits for ICE gathering, at most 3 s", async () => {
  const peers: FakePeer[] = [];
  const { api } = renderLive({}, () => {
    const p = new FakePeer();
    p.iceGatheringState = "gathering";
    peers.push(p);
    return p as unknown as RTCPeerConnection;
  });
  await wait(2_900);
  expect(api.startLive).not.toHaveBeenCalled();
  await wait(100);
  expect(api.startLive).toHaveBeenCalledTimes(1);
});

test("Browser without WebRTC", async () => {
  const { api } = renderLive({}, () => null);
  await settle();
  expect(screen.getByText("This browser can't play live video.")).toBeInTheDocument();
  expect(api.startLive).not.toHaveBeenCalled();
});

test("Livestream dialog is wide", async () => {
  renderLive();
  const dialog = screen.getByRole("dialog", { name: "Livestream" });
  expect(dialog).toHaveClass("sm:max-w-3xl");
  expect(dialog).not.toHaveClass("max-w-md");
  await settle();
});

// Browser decoder readout: stats are read about once a second while video plays
test("decoder stats are reported once live", async () => {
  const onStats = vi.fn();
  const { peers } = renderLive({}, undefined, onStats);
  await settle();
  await wait(2_000);
  expect(peers[0].statsCalls).toBe(0);
  expect(onStats).not.toHaveBeenCalled();
  peers[0].track();
  await wait(1_000);
  expect(onStats).toHaveBeenLastCalledWith({
    codec: "video/H264",
    decoder: "ExternalDecoder",
    width: 1920,
    height: 1080,
    fps: 15,
  });
});

test("decoder stats stop when the dialog closes", async () => {
  const onStats = vi.fn();
  const { peers } = renderLive({}, undefined, onStats);
  await settle();
  peers[0].track();
  await wait(1_000);
  closeDialog();
  const calls = peers[0].statsCalls;
  expect(calls).toBeGreaterThan(0);
  await wait(3_000);
  expect(peers[0].statsCalls).toBe(calls);
});
