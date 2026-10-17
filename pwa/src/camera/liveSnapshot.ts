import type { Api } from "../AppContext";
import type { Snapshot } from "../api/types";
import {
  CAMERA_OFFLINE,
  cameraOffline,
  livePeer,
  NO_VIDEO,
  openLive,
  type LiveConnection,
} from "../components/LiveStream";
import { grabFrame } from "../image";

/** The first frames after connecting are often grey until a keyframe arrives. */
export const FRAMES_NEEDED = 10;
export const FRAME_WAIT_MS = 15_000;
const POLL_MS = 100;

/** True for the error a cancelled snapshot rejects with. */
export function isAbort(err: unknown): boolean {
  return err instanceof DOMException && err.name === "AbortError";
}

/** The live view connected but the camera sent no video (for example, it is unplugged).
 * Not a reason to fall back: the newest recording would look current but isn't. */
export class NoVideo extends Error {
  constructor() {
    super(NO_VIDEO);
    this.name = "NoVideo";
  }
}

/** Ring reports the camera offline: no live view is opened and there is no fallback. */
export class CameraOffline extends Error {
  constructor() {
    super(CAMERA_OFFLINE);
    this.name = "CameraOffline";
  }
}

/** The live view could not give a frame (no WebRTC, no connection, no frames in time). */
export class NoLiveFrame extends Error {}

export interface LiveSnapshotOptions {
  createPeer?: () => RTCPeerConnection | null;
  /** Aborting ends the live session; the snapshot then rejects with an AbortError. */
  signal?: AbortSignal;
}

/** Calls `done` once `video` has decoded `n` frames. Returns a cancel function. */
function afterFrames(video: HTMLVideoElement, n: number, done: () => void): () => void {
  let cancelled = false;
  if (typeof video.requestVideoFrameCallback === "function") {
    let seen = 0;
    const next = () =>
      video.requestVideoFrameCallback(() => {
        if (cancelled) return;
        if (++seen >= n) done();
        else next();
      });
    next();
    return () => (cancelled = true);
  }
  // Browsers without requestVideoFrameCallback: poll the decoded-frame count.
  const timer = setInterval(() => {
    if ((video.getVideoPlaybackQuality?.().totalVideoFrames ?? 0) >= n) {
      clearInterval(timer);
      done();
    }
  }, POLL_MS);
  return () => clearInterval(timer);
}

/**
 * One unblurred frame from a short live view, as a base64 JPEG at most 960 px wide. The live
 * session is ended before this resolves. The frame is never attached to the page.
 */
export function liveFrame(
  api: Pick<Api, "startLive" | "stopLive">,
  { createPeer = livePeer, signal }: LiveSnapshotOptions = {},
): Promise<string> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) return reject(new DOMException("Snapshot cancelled", "AbortError"));
    let conn: LiveConnection | null = null;
    let cancelFrames = () => {};
    let finished = false;
    let streamed = false;
    const finish = (settle: () => void) => {
      if (finished) return;
      finished = true;
      clearTimeout(timer);
      cancelFrames();
      signal?.removeEventListener("abort", onAbort);
      conn?.stop();
      settle();
    };
    const onAbort = () => finish(() => reject(new DOMException("Snapshot cancelled", "AbortError")));
    const timer = setTimeout(
      () => finish(() => reject(streamed ? new NoVideo() : new NoLiveFrame("no video track in time"))),
      FRAME_WAIT_MS,
    );
    signal?.addEventListener("abort", onAbort);

    conn = openLive(api, createPeer, {
      onStream(stream) {
        streamed = true;
        const video = document.createElement("video");
        video.muted = true;
        video.playsInline = true;
        video.srcObject = stream;
        video.play().catch(() => {});
        cancelFrames = afterFrames(video, FRAMES_NEEDED, () => {
          if (finished) return;
          grabFrame(video).then(
            (image) => finish(() => resolve(image)),
            (err) => finish(() => reject(new NoLiveFrame(String(err)))),
          );
        });
      },
      onError(message) {
        finish(() => reject(message === NO_VIDEO ? new NoVideo() : new NoLiveFrame(message)));
      },
    });
    if (!conn) finish(() => reject(new NoLiveFrame("no WebRTC")));
  });
}

/**
 * A face-blurred snapshot taken from a live frame. When the live view gives no frame, it is the
 * Ring still from `cameraSnapshot` instead; a failed blur is not retried that way.
 */
export async function liveSnapshot(
  api: Pick<Api, "camera" | "startLive" | "stopLive" | "cameraFrame" | "cameraSnapshot">,
  options: LiveSnapshotOptions = {},
): Promise<Snapshot> {
  if (await cameraOffline(api)) throw new CameraOffline();
  let frame: string;
  try {
    frame = await liveFrame(api, options);
  } catch (err) {
    if (!(err instanceof NoLiveFrame)) throw err;
    return api.cameraSnapshot();
  }
  return api.cameraFrame(frame);
}
