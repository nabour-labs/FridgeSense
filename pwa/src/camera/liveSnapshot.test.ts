import { ApiError } from "../api/client";
import type { LiveSession, Snapshot } from "../api/types";
import { fakeApi } from "../test-utils";
import { CameraOffline, FRAME_WAIT_MS, FRAMES_NEEDED, liveSnapshot, NoVideo } from "./liveSnapshot";

const SESSION: LiveSession = { answer: "v=0\r\nanswer\r\n", session_id: "S1", max_seconds: 60 };
const BLURRED: Snapshot = { image: "BLURRED", captured_at: "2026-10-15T19:20:10.000Z" };

/** A stand-in RTCPeerConnection that delivers video as soon as the answer is set. */
class FakePeer {
  iceGatheringState: RTCIceGatheringState = "complete";
  connectionState: RTCPeerConnectionState = "new";
  localDescription: RTCSessionDescriptionInit | null = null;
  ontrack: ((e: { streams: MediaStream[] }) => void) | null = null;
  onconnectionstatechange: (() => void) | null = null;
  onicegatheringstatechange: (() => void) | null = null;
  closed = 0;
  constructor(private readonly sendsVideo = true) {}
  addTransceiver() {}
  async createOffer() {
    return { type: "offer" as const, sdp: "v=0\r\noffer\r\n" };
  }
  async setLocalDescription(d: RTCSessionDescriptionInit) {
    this.localDescription = d;
  }
  async setRemoteDescription() {
    if (this.sendsVideo) queueMicrotask(() => this.ontrack?.({ streams: [{ id: "stream" } as unknown as MediaStream] }));
  }
  close() {
    this.closed += 1;
  }
}

/** Video frames: the test decides when each one is decoded. */
let frameCallbacks: VideoFrameRequestCallback[] = [];
function decodeFrames(n: number) {
  for (let i = 0; i < n; i++) frameCallbacks.shift()?.(0, {} as VideoFrameCallbackMetadata);
}
/** Lets pending promises, the FileReader and other zero-delay work finish. */
const settle = async () => {
  for (let i = 0; i < 5; i++) await vi.advanceTimersByTimeAsync(1);
};

let drawn: [number, number] | null;
let calls: string[];

beforeEach(() => {
  vi.useFakeTimers();
  frameCallbacks = [];
  drawn = null;
  calls = [];
  vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined);
  Object.defineProperty(HTMLVideoElement.prototype, "requestVideoFrameCallback", {
    configurable: true,
    value: (cb: VideoFrameRequestCallback) => frameCallbacks.push(cb),
  });
  Object.defineProperty(HTMLVideoElement.prototype, "videoWidth", { configurable: true, get: () => 1920 });
  Object.defineProperty(HTMLVideoElement.prototype, "videoHeight", { configurable: true, get: () => 1080 });
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({ drawImage: vi.fn() } as never);
  vi.spyOn(HTMLCanvasElement.prototype, "toBlob").mockImplementation(function (this: HTMLCanvasElement, cb) {
    drawn = [this.width, this.height];
    calls.push("draw");
    cb(new Blob(["jpeg!"], { type: "image/jpeg" }));
  });
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  delete (HTMLVideoElement.prototype as Partial<HTMLVideoElement>).requestVideoFrameCallback;
});

function api(overrides: Record<string, unknown> = {}) {
  return fakeApi({
    camera: vi.fn().mockImplementation(async () => {
      calls.push("camera");
      return { name: "Fridge", online: true };
    }),
    startLive: vi.fn().mockImplementation(async () => {
      calls.push("startLive");
      return SESSION;
    }),
    stopLive: vi.fn().mockImplementation(async () => {
      calls.push("stopLive");
      return { ok: true };
    }),
    cameraFrame: vi.fn().mockImplementation(async () => {
      calls.push("cameraFrame");
      return BLURRED;
    }),
    cameraSnapshot: vi.fn().mockResolvedValue({ image: "STILL", captured_at: "x" }),
    ...overrides,
  });
}

/** Starts a snapshot and lets the live view connect; `result` is the snapshot promise. */
async function start(a = api(), peer = new FakePeer()) {
  const result = liveSnapshot(a, { createPeer: () => peer as unknown as RTCPeerConnection });
  result.catch(() => {});
  await settle();
  return { result };
}

// Snapshot taken from the live view
test("a snapshot is one blurred frame from the live view", async () => {
  const a = api();
  const { result } = await start(a);
  decodeFrames(FRAMES_NEEDED);
  await settle();
  await expect(result).resolves.toEqual(BLURRED);
  expect(a.startLive).toHaveBeenCalledTimes(1);
  expect(drawn).toEqual([960, 540]);
  expect(a.cameraFrame).toHaveBeenCalledWith(btoa("jpeg!"));
  expect(a.stopLive).toHaveBeenCalledWith("S1");
  expect(a.cameraSnapshot).not.toHaveBeenCalled();
});

test("the frame is not drawn before ten frames are decoded", async () => {
  const a = api();
  await start(a);
  decodeFrames(FRAMES_NEEDED - 1);
  await settle();
  expect(drawn).toBeNull();
  expect(a.cameraFrame).not.toHaveBeenCalled();
});

// Live session ended before the frame is sent
test("the live session ends before the frame is sent", async () => {
  const peer = new FakePeer();
  const { result } = await start(api(), peer);
  decodeFrames(FRAMES_NEEDED);
  await settle();
  await result;
  expect(calls).toEqual(["camera", "startLive", "draw", "stopLive", "cameraFrame"]);
  expect(peer.closed).toBe(1);
});

// Unblurred frame never shown
test("no live video is attached to the page", async () => {
  await start();
  decodeFrames(FRAMES_NEEDED - 1);
  expect(document.querySelectorAll("video, canvas")).toHaveLength(0);
});

// Blurring fails
test("a failed blur is reported and the Ring still is not requested", async () => {
  const a = api({ cameraFrame: vi.fn().mockRejectedValue(new ApiError(502, "camera unavailable")) });
  const { result } = await start(a);
  decodeFrames(FRAMES_NEEDED);
  await settle();
  await expect(result).rejects.toMatchObject({ status: 502 });
  expect(a.cameraSnapshot).not.toHaveBeenCalled();
});

// Live route unavailable
test("when the live route fails, the snapshot is the Ring still", async () => {
  const a = api({ startLive: vi.fn().mockRejectedValue(new ApiError(502, "camera unavailable")) });
  const { result } = await start(a);
  await expect(result).resolves.toEqual({ image: "STILL", captured_at: "x" });
  expect(a.cameraSnapshot).toHaveBeenCalledTimes(1);
  expect(a.cameraFrame).not.toHaveBeenCalled();
});

// No frames in time
test("with no frames for 15 s, the camera is reported as not sending video", async () => {
  const a = api();
  const { result } = await start(a);
  decodeFrames(FRAMES_NEEDED - 1);
  await vi.advanceTimersByTimeAsync(FRAME_WAIT_MS);
  await expect(result).rejects.toBeInstanceOf(NoVideo);
  expect(a.stopLive).toHaveBeenCalledWith("S1");
  expect(a.cameraSnapshot).not.toHaveBeenCalled();
  expect(a.cameraFrame).not.toHaveBeenCalled();
});

// Connection fails before any frame
test("a connection that fails before any frame still falls back", async () => {
  const a = api();
  const peer = new FakePeer();
  const { result } = await start(a, peer);
  decodeFrames(3);
  peer.connectionState = "failed";
  peer.onconnectionstatechange?.();
  await expect(result).resolves.toEqual({ image: "STILL", captured_at: "x" });
  expect(a.stopLive).toHaveBeenCalledWith("S1");
});

test("a connection that fails falls back to the Ring still", async () => {
  const a = api();
  const peer = new FakePeer(false);
  const { result } = await start(a, peer);
  peer.connectionState = "failed";
  peer.onconnectionstatechange?.();
  await expect(result).resolves.toEqual({ image: "STILL", captured_at: "x" });
  expect(a.cameraSnapshot).toHaveBeenCalledTimes(1);
});

// Browser without WebRTC
test("a browser without WebRTC asks for the Ring still only", async () => {
  const a = api();
  const result = liveSnapshot(a, { createPeer: () => null });
  await expect(result).resolves.toEqual({ image: "STILL", captured_at: "x" });
  expect(a.startLive).not.toHaveBeenCalled();
  expect(a.cameraSnapshot).toHaveBeenCalledTimes(1);
});

// Fallback finds no footage
test("the fallback's 409 reaches the screen", async () => {
  const a = api({
    startLive: vi.fn().mockRejectedValue(new ApiError(502)),
    cameraSnapshot: vi.fn().mockRejectedValue(new ApiError(409, "no recent footage")),
  });
  const { result } = await start(a);
  await expect(result).rejects.toMatchObject({ status: 409 });
});

// Screen closed while taking the snapshot
test("aborting ends the session and sends nothing", async () => {
  const a = api();
  const abort = new AbortController();
  const result = liveSnapshot(a, {
    createPeer: () => new FakePeer() as unknown as RTCPeerConnection,
    signal: abort.signal,
  });
  result.catch(() => {});
  await settle();
  abort.abort();
  decodeFrames(FRAMES_NEEDED);
  await settle();
  await expect(result).rejects.toMatchObject({ name: "AbortError" });
  expect(a.stopLive).toHaveBeenCalledWith("S1");
  expect(a.cameraFrame).not.toHaveBeenCalled();
  expect(a.cameraSnapshot).not.toHaveBeenCalled();
});

test("aborting while connecting ends the session once it opens", async () => {
  const a = api();
  const abort = new AbortController();
  const result = liveSnapshot(a, {
    createPeer: () => new FakePeer() as unknown as RTCPeerConnection,
    signal: abort.signal,
  });
  result.catch(() => {});
  abort.abort();
  await settle();
  await expect(result).rejects.toMatchObject({ name: "AbortError" });
  expect(a.cameraSnapshot).not.toHaveBeenCalled();
});

// Online check before a snapshot
test("an offline camera is reported and nothing else is requested", async () => {
  const a = api({ camera: vi.fn().mockResolvedValue({ name: "Fridge", online: false }) });
  const { result } = await start(a);
  await expect(result).rejects.toBeInstanceOf(CameraOffline);
  await expect(result).rejects.toThrow("The camera is offline. Check that it's plugged in and connected to Wi-Fi.");
  expect(a.startLive).not.toHaveBeenCalled();
  expect(a.cameraFrame).not.toHaveBeenCalled();
  expect(a.cameraSnapshot).not.toHaveBeenCalled();
});

test("an online camera is checked, then the live view opens", async () => {
  const a = api();
  await start(a);
  expect(a.camera).toHaveBeenCalledTimes(1);
  expect(a.startLive).toHaveBeenCalledTimes(1);
});

test.each([
  ["online null", vi.fn().mockResolvedValue({ name: "Fridge", online: null })],
  ["502", vi.fn().mockRejectedValue(new ApiError(502, "camera unavailable"))],
  ["network error", vi.fn().mockRejectedValue(new TypeError("Failed to fetch"))],
])("an unknown status (%s) still opens the live view", async (_, camera) => {
  const a = api({ camera });
  await start(a);
  expect(a.startLive).toHaveBeenCalledTimes(1);
});
