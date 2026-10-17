import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, Unauthorized } from "../api/client";
import { useApp, type Api } from "../AppContext";
import { ClipLive } from "../debug/ClipLive";
import { useDebug } from "../debug/DebugContext";
import { Sheet } from "./Sheet";

const ICE_WAIT_MS = 3_000;
const STATS_EVERY_MS = 1_000;
/** How long after the answer the camera has to deliver a decoded video frame. */
const VIDEO_WAIT_MS = 15_000;
const NO_WEBRTC = "This browser can't play live video.";
const NO_CONNECTION = "Could not connect to the camera.";
/** The session connected but no video came: Ring still answers for an unplugged camera. */
export const NO_VIDEO = "The camera isn't sending video. Check that it's plugged in.";
export const CAMERA_OFFLINE = "The camera is offline. Check that it's plugged in and connected to Wi-Fi.";

/** True only when Ring reports the camera offline. An unknown status (Ring unreachable, a
 * failed check) counts as online, so a working camera is never hidden; a 401 is rethrown. */
export async function cameraOffline(api: Pick<Api, "camera">): Promise<boolean> {
  try {
    return (await api.camera()).online === false;
  } catch (err) {
    if (err instanceof Unauthorized) throw err;
    return false;
  }
}
const UNAVAILABLE = "The camera is not available right now.";
const NO_CAMERA = "No camera is linked yet.";

type State =
  | { kind: "connecting" }
  | { kind: "live"; left: number }
  | { kind: "ended" }
  | { kind: "error"; message: string };

/** How this browser decodes the live video, from WebRTC stats; a field is null if the
 * browser does not report it (Safari leaves out the decoder implementation). */
export interface DecoderStats {
  codec: string | null;
  decoder: string | null;
  width: number | null;
  height: number | null;
  fps: number | null;
}

/** The inbound video's decoder stats, or null before any video report. */
export async function decoderStats(peer: RTCPeerConnection): Promise<DecoderStats | null> {
  const report = (await peer.getStats()) as Map<string, Record<string, unknown>>;
  const video = [...report.values()].find((r) => r.type === "inbound-rtp" && r.kind === "video");
  if (!video) return null;
  const str = (v: unknown) => (typeof v === "string" && v ? v : null);
  const num = (v: unknown) => (typeof v === "number" ? v : null);
  return {
    codec: str(report.get(String(video.codecId))?.mimeType),
    decoder: str(video.decoderImplementation),
    width: num(video.frameWidth),
    height: num(video.frameHeight),
    fps: num(video.framesPerSecond),
  };
}

/** Video frames the browser has decoded so far; 0 before any video report. */
async function decoderFrames(peer: RTCPeerConnection): Promise<number> {
  const report = (await peer.getStats()) as Map<string, Record<string, unknown>>;
  const video = [...report.values()].find((r) => r.type === "inbound-rtp" && r.kind === "video");
  return typeof video?.framesDecoded === "number" ? video.framesDecoded : 0;
}

/** A real peer, or null when the browser has no WebRTC. */
export function livePeer(): RTCPeerConnection | null {
  if (typeof RTCPeerConnection === "undefined") return null;
  return new RTCPeerConnection({ iceServers: [{ urls: "stun:stun.l.google.com:19302" }] });
}

/** Resolves once ICE gathering is complete, or after `ms` with what was gathered so far. */
function iceGathered(peer: RTCPeerConnection, ms: number): Promise<void> {
  return new Promise((resolve) => {
    if (peer.iceGatheringState === "complete") return resolve();
    const timer = setTimeout(resolve, ms);
    peer.onicegatheringstatechange = () => {
      if (peer.iceGatheringState !== "complete") return;
      clearTimeout(timer);
      resolve();
    };
  });
}

/** What a live connection reports back. `onError` gets one of the dialog's messages and,
 * when an API call failed, its error. */
export interface LiveCallbacks {
  onStream: (stream: MediaStream, maxSeconds: number) => void;
  onError: (message: string, err?: unknown) => void;
}

/** One live connection: its peer, and `stop()`, which closes the peer and ends the camera
 * session, once. */
export interface LiveConnection {
  peer: RTCPeerConnection;
  stop: () => void;
  readonly stopped: boolean;
}

/** Opens a live view through the app API, or returns null when the browser has no WebRTC.
 * Video arrives through `onStream`; any failure stops the connection and calls `onError`. */
export function openLive(
  api: Pick<Api, "startLive" | "stopLive">,
  createPeer: () => RTCPeerConnection | null,
  callbacks: LiveCallbacks,
): LiveConnection | null {
  const peer = createPeer();
  if (!peer) return null;
  let sessionId: string | null = null;
  let stopped = false;
  let videoTimer: ReturnType<typeof setTimeout> | undefined;
  const conn: LiveConnection = {
    peer,
    get stopped() {
      return stopped;
    },
    stop() {
      if (stopped) return;
      stopped = true;
      clearTimeout(videoTimer);
      peer.close();
      if (sessionId) api.stopLive(sessionId).catch(() => {});
    },
  };
  const fail = (message: string, err?: unknown) => {
    if (stopped) return;
    conn.stop();
    callbacks.onError(message, err);
  };

  peer.addTransceiver("video", { direction: "recvonly" });
  peer.addTransceiver("audio", { direction: "recvonly" });
  peer.onconnectionstatechange = () => peer.connectionState === "failed" && fail(NO_CONNECTION);
  let maxSeconds = 0;
  peer.ontrack = (e) => {
    if (stopped || !e.streams[0]) return;
    callbacks.onStream(e.streams[0], maxSeconds);
  };

  void (async () => {
    try {
      await peer.setLocalDescription(await peer.createOffer());
      await iceGathered(peer, ICE_WAIT_MS);
      if (stopped) return;
      const live = await api.startLive(peer.localDescription!.sdp!);
      sessionId = live.session_id;
      if (stopped) {
        api.stopLive(live.session_id).catch(() => {});
        return;
      }
      // Set before the answer: browsers fire the track while it is being applied.
      maxSeconds = live.max_seconds;
      videoTimer = setTimeout(() => {
        decoderFrames(peer)
          .catch(() => 0)
          .then((frames) => frames === 0 && fail(NO_VIDEO));
      }, VIDEO_WAIT_MS);
      await peer.setRemoteDescription({ type: "answer", sdp: live.answer });
    } catch (err) {
      if (!(err instanceof ApiError)) return fail(NO_CONNECTION, err);
      fail(err.status === 409 ? NO_CAMERA : UNAVAILABLE, err);
    }
  })();
  return conn;
}

function useLiveStream(createPeer: () => RTCPeerConnection | null, onStats?: (stats: DecoderStats) => void) {
  const { api, report } = useApp();
  const statsListener = useRef(onStats);
  statsListener.current = onStats;
  const [state, setState] = useState<State>({ kind: "connecting" });
  const [stream, setStream] = useState<MediaStream | null>(null);
  const current = useRef<{ conn: LiveConnection; timers: ReturnType<typeof setTimeout>[] } | null>(null);
  /** Bumped by every start and stop, so an online check that answers late is ignored. */
  const attempt = useRef(0);

  /** Ends the current attempt and its countdown, once. */
  const stop = useCallback(() => {
    attempt.current += 1;
    const run = current.current;
    if (!run || run.conn.stopped) return;
    run.timers.forEach((t) => clearTimeout(t));
    run.conn.stop();
    setStream(null);
  }, []);

  const start = useCallback(async () => {
    stop();
    const mine = ++attempt.current;
    setState({ kind: "connecting" });
    let offline: boolean;
    try {
      offline = await cameraOffline(api);
    } catch (err) {
      if (mine === attempt.current) report(err);
      return;
    }
    if (mine !== attempt.current) return;
    if (offline) return setState({ kind: "error", message: CAMERA_OFFLINE });
    const timers: ReturnType<typeof setTimeout>[] = [];
    const conn = openLive(api, createPeer, {
      onStream(stream, maxSeconds) {
        setStream(stream);
        setState({ kind: "live", left: maxSeconds });
        const readStats = () => {
          timers.push(
            setTimeout(() => {
              if (conn!.stopped) return;
              decoderStats(conn!.peer)
                .then((stats) => stats && !conn!.stopped && statsListener.current?.(stats))
                .catch(() => {})
                .finally(() => !conn!.stopped && readStats());
            }, STATS_EVERY_MS),
          );
        };
        if (statsListener.current) readStats();
        for (let s = 1; s <= maxSeconds; s++) {
          timers.push(
            setTimeout(() => {
              if (s < maxSeconds) return setState({ kind: "live", left: maxSeconds - s });
              stop();
              setState({ kind: "ended" });
            }, s * 1000),
          );
        }
      },
      onError(message, err) {
        if (err instanceof Unauthorized) report(err);
        timers.forEach((t) => clearTimeout(t));
        setStream(null);
        setState({ kind: "error", message });
      },
    });
    if (!conn) return setState({ kind: "error", message: NO_WEBRTC });
    current.current = { conn, timers };
  }, [api, createPeer, report, stop]);

  useEffect(() => {
    void start();
    return stop;
    // One attempt per dialog; "Watch again" / "Try again" call start themselves.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { state, stream, start };
}

/** The Livestream dialog; in debug mode with Mock video on, a local clip plays instead of the camera. */
export function LiveStream(props: {
  onClose: () => void;
  createPeer?: () => RTCPeerConnection | null;
  /** Called about once a second with the browser's decoder stats while video plays. */
  onStats?: (stats: DecoderStats) => void;
}) {
  const { mockVideo } = useDebug();
  return import.meta.env.DEV && mockVideo ? <ClipLive onClose={props.onClose} /> : <RealLiveStream {...props} />;
}

/** The camera's live video for up to its session limit. */
function RealLiveStream({
  onClose,
  createPeer = livePeer,
  onStats,
}: {
  onClose: () => void;
  createPeer?: () => RTCPeerConnection | null;
  onStats?: (stats: DecoderStats) => void;
}) {
  const { state, stream, start } = useLiveStream(createPeer, onStats);
  const video = useRef<HTMLVideoElement>(null);
  // The track arrives before any picture; until the video plays, say so instead of showing black.
  const [playing, setPlaying] = useState(false);
  useEffect(() => {
    setPlaying(false);
    if (video.current) video.current.srcObject = stream;
  }, [stream]);

  const again = (label: string) => (
    <button
      onClick={() => void start()}
      className="mt-4 h-12 w-full rounded-xl bg-brand-600 font-semibold text-white transition hover:bg-brand-700 active:scale-[0.98]"
    >
      {label}
    </button>
  );

  return (
    <Sheet title="Livestream" size="wide" onClose={onClose}>
      <div className="relative grid aspect-video place-items-center overflow-hidden rounded-2xl bg-black text-sm text-slate-300">
        {stream && (
          <video
            ref={video}
            data-testid="live-video"
            autoPlay
            muted
            playsInline
            onPlaying={() => setPlaying(true)}
            className="absolute inset-0 size-full object-contain"
          />
        )}
        {(state.kind === "connecting" || (state.kind === "live" && !playing)) && <p className="relative">Connecting…</p>}
        {state.kind === "ended" && <p>Stream ended</p>}
        {state.kind === "error" && <p className="px-6 text-center">{state.message}</p>}
        {state.kind === "live" && (
          <span className="absolute right-2 top-2 rounded-full bg-black/60 px-2.5 py-1 text-xs font-semibold text-white tabular-nums">
            {state.left} s left
          </span>
        )}
      </div>
      {state.kind === "ended" && again("Watch again")}
      {state.kind === "error" && state.message !== NO_WEBRTC && again("Try again")}
    </Sheet>
  );
}
