import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { useState } from "react";
import { ApiError } from "../api/client";
import type { LiveSession } from "../api/types";
import { AppContext, type Api } from "../AppContext";
import { fakeApi } from "../test-utils";
import { LiveStream } from "./LiveStream";

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
  async setRemoteDescription(d: RTCSessionDescriptionInit) {
    this.remoteDescription = d;
  }
  close() {
    this.closed += 1;
  }
  /** Video arrives. */
  track() {
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

function Harness({ createPeer }: { createPeer: () => RTCPeerConnection | null }) {
  const [open, setOpen] = useState(true);
  return open ? <LiveStream onClose={() => setOpen(false)} createPeer={createPeer} /> : <p>closed</p>;
}

function renderLive(overrides: Partial<Record<keyof Api, unknown>> = {}, createPeer?: () => RTCPeerConnection | null) {
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
      <Harness createPeer={make} />
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

test("Video never arrives", async () => {
  const { api, peers } = renderLive();
  await settle();
  await wait(15_000);
  expect(peers[0].closed).toBe(1);
  expect(api.stopLive).toHaveBeenCalledWith("S1");
  expect(screen.getByText("Could not connect to the camera.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
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
