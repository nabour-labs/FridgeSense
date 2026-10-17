import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, Unauthorized } from "../api/client";
import { useApp } from "../AppContext";
import { ClipLive } from "../debug/ClipLive";
import { useDebug } from "../debug/DebugContext";
import { Sheet } from "./Sheet";

const ICE_WAIT_MS = 3_000;
const STATS_EVERY_MS = 1_000;
const TRACK_WAIT_MS = 15_000;
const NO_WEBRTC = "This browser can't play live video.";
const NO_CONNECTION = "Could not connect to the camera.";
const UNAVAILABLE = "The camera is not available right now.";
const NO_CAMERA = "No camera is linked yet.";

type State =
  | { kind: "connecting" }
  | { kind: "live"; left: number }
  | { kind: "ended" }
  | { kind: "error"; message: string };

/** One attempt: its peer, the camera's session once known, and its timers. */
interface Run {
  peer: RTCPeerConnection;
  sessionId: string | null;
  stopped: boolean;
  timers: ReturnType<typeof setTimeout>[];
}

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

function useLiveStream(createPeer: () => RTCPeerConnection | null, onStats?: (stats: DecoderStats) => void) {
  const { api, report } = useApp();
  const statsListener = useRef(onStats);
  statsListener.current = onStats;
  const [state, setState] = useState<State>({ kind: "connecting" });
  const [stream, setStream] = useState<MediaStream | null>(null);
  const current = useRef<Run | null>(null);

  /** Ends the current attempt: closes the peer and ends the camera session, once. */
  const stop = useCallback(() => {
    const run = current.current;
    if (!run || run.stopped) return;
    run.stopped = true;
    run.timers.forEach((t) => clearTimeout(t));
    run.peer.close();
    setStream(null);
    if (run.sessionId) api.stopLive(run.sessionId).catch(() => {});
  }, [api]);

  const start = useCallback(async () => {
    stop();
    const peer = createPeer();
    if (!peer) return setState({ kind: "error", message: NO_WEBRTC });
    const run: Run = { peer, sessionId: null, stopped: false, timers: [] };
    current.current = run;
    setState({ kind: "connecting" });
    const fail = (message: string) => {
      if (run.stopped) return;
      stop();
      setState({ kind: "error", message });
    };

    peer.addTransceiver("video", { direction: "recvonly" });
    peer.addTransceiver("audio", { direction: "recvonly" });
    peer.onconnectionstatechange = () => peer.connectionState === "failed" && fail(NO_CONNECTION);
    let maxSeconds = 0;
    peer.ontrack = (e) => {
      if (run.stopped || !e.streams[0]) return;
      run.timers.forEach((t) => clearTimeout(t));
      setStream(e.streams[0]);
      setState({ kind: "live", left: maxSeconds });
      const readStats = () => {
        run.timers.push(
          setTimeout(() => {
            if (run.stopped) return;
            decoderStats(peer)
              .then((stats) => stats && !run.stopped && statsListener.current?.(stats))
              .catch(() => {})
              .finally(() => !run.stopped && readStats());
          }, STATS_EVERY_MS),
        );
      };
      if (statsListener.current) readStats();
      for (let s = 1; s <= maxSeconds; s++) {
        run.timers.push(
          setTimeout(() => {
            if (s < maxSeconds) return setState({ kind: "live", left: maxSeconds - s });
            stop();
            setState({ kind: "ended" });
          }, s * 1000),
        );
      }
    };

    try {
      await peer.setLocalDescription(await peer.createOffer());
      await iceGathered(peer, ICE_WAIT_MS);
      if (run.stopped) return;
      const live = await api.startLive(peer.localDescription!.sdp!);
      run.sessionId = live.session_id;
      if (run.stopped) {
        api.stopLive(live.session_id).catch(() => {});
        return;
      }
      maxSeconds = live.max_seconds;
      await peer.setRemoteDescription({ type: "answer", sdp: live.answer });
      run.timers.push(setTimeout(() => fail(NO_CONNECTION), TRACK_WAIT_MS));
    } catch (err) {
      if (err instanceof Unauthorized) report(err);
      if (!(err instanceof ApiError)) return fail(NO_CONNECTION);
      fail(err.status === 409 ? NO_CAMERA : UNAVAILABLE);
    }
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
  useEffect(() => {
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
            className="absolute inset-0 size-full object-contain"
          />
        )}
        {state.kind === "connecting" && <p>Connecting…</p>}
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
