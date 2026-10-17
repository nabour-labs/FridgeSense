import { Cpu, Video } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "../api/client";
import type { CameraInfo, Monitoring as MonitoringState, StatusChange } from "../api/types";
import { canEdit, isAdmin, useApp } from "../AppContext";
import { EmptyState } from "../components/EmptyState";
import { LiveStream, type DecoderStats } from "../components/LiveStream";
import { NoData } from "../components/NoData";
import { clock, dayLabel } from "../format";
import { useLoad } from "../useLoad";
import { CARD, HEADING, PRIMARY } from "./configStyles";

const NOT_REPORTED = "Not reported";
const NO_CAMERA = "none" as const;
const DAY_MS = 86_400_000;

const ENHANCEMENTS: Record<string, string> = {
  color_night_vision: "Color night vision",
  hdr: "HDR",
  ir_led_night_vision: "IR night vision",
  auto_zoom_track: "Auto zoom and track",
};

function enhancementLabel(name: string) {
  return ENHANCEMENTS[name] ?? name.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
}

function onOff(value: boolean | null | undefined) {
  return value == null ? NOT_REPORTED : value ? "On" : "Off";
}

function resolution(p: number) {
  return `${p}p`;
}

function locationText(location: Record<string, string> | null) {
  if (!location) return NOT_REPORTED;
  const order = ["city", "state", "country"];
  const keys = [...order.filter((k) => location[k]), ...Object.keys(location).filter((k) => !order.includes(k))];
  return keys.map((k) => location[k]).join(", ") || NOT_REPORTED;
}

/** The connected camera: Ring's details, its status now, and its recorded online history. */
export function Camera({ createPeer }: { createPeer?: () => RTCPeerConnection | null } = {}) {
  const { api, role } = useApp();
  const { data, failed } = useLoad(
    useCallback(
      () =>
        api.camera().catch((err: unknown) => {
          if (err instanceof ApiError && err.status === 409) return NO_CAMERA;
          throw err;
        }),
      [api],
    ),
    60_000,
  );

  let camera;
  if (data === NO_CAMERA) camera = <EmptyState Icon={Video} title="No camera is linked yet." />;
  else if (!data) {
    camera = failed ? (
      <NoData />
    ) : (
      <div aria-hidden data-testid="loading" className="h-64 animate-pulse rounded-3xl bg-slate-200/70 dark:bg-slate-800" />
    );
  } else {
    camera = (
      <>
        <Monitoring state={data.monitoring} />
        <Overview info={data} />
        <Details info={data} />
        <History info={data} />
        {canEdit(role) && <Decoder createPeer={createPeer} />}
      </>
    );
  }

  return (
    <div className="space-y-5">
      {camera}
      <BlurFaces />
    </div>
  );
}

/** The FridgeSense on/off switch: paused, door openings are neither recorded nor analyzed. */
function Monitoring({ state: loaded }: { state: MonitoringState }) {
  const { api, role } = useApp();
  const [state, setState] = useState(loaded);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  useEffect(() => setState(loaded), [loaded]); // each poll brings the stored state

  async function toggle() {
    setBusy(true);
    setFailed(false);
    try {
      setState(await api.setMonitoring(!state.paused));
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  }

  const active = !state.paused;
  return (
    <section aria-label="FridgeSense" className={`${CARD} space-y-1.5 p-4`}>
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <h2 className="font-bold tracking-tight">FridgeSense</h2>
          <p className={`text-sm font-semibold ${active ? "text-emerald-700 dark:text-emerald-300" : "text-amber-700 dark:text-amber-300"}`}>
            {active ? "Active" : state.since ? `Paused since ${dayLabel(state.since)} ${clock(state.since)}` : "Paused"}
          </p>
        </div>
        {canEdit(role) && (
          <button
            type="button"
            role="switch"
            aria-checked={active}
            aria-label="FridgeSense"
            disabled={busy}
            onClick={toggle}
            className={`relative h-7 w-12 shrink-0 rounded-full transition-colors disabled:opacity-60 ${
              active ? "bg-brand-600" : "bg-slate-300 dark:bg-slate-700"
            }`}
          >
            <span
              aria-hidden
              className={`absolute top-0.5 size-6 rounded-full bg-white shadow transition-[left] ${active ? "left-[1.375rem]" : "left-0.5"}`}
            />
          </button>
        )}
      </div>
      <p className="text-sm text-slate-500 dark:text-slate-400">
        Pause while you clean, service or renovate. Door openings are not recorded or analyzed while paused.
      </p>
      {failed && <p className="text-sm font-medium text-rose-700 dark:text-rose-300">Could not change it. Try again.</p>}
    </section>
  );
}

/** The owner's face-blur switch; everyone else sees it read-only. On until the API says otherwise. */
function BlurFaces() {
  const { api, role, report } = useApp();
  const [enabled, setEnabled] = useState(true);
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let live = true;
    api.faceBlur().then(
      (body) => {
        if (!live) return;
        setEnabled(body.enabled);
        setLoaded(true);
      },
      (err: unknown) => live && report(err),
    );
    return () => {
      live = false;
    };
  }, [api, report]);

  const toggle = () => {
    const previous = enabled;
    setEnabled(!previous);
    setSaving(true);
    api.setFaceBlur(!previous).then(
      (body) => setEnabled(body.enabled),
      (err: unknown) => {
        setEnabled(previous);
        report(err);
      },
    ).finally(() => setSaving(false));
  };

  const canChange = isAdmin(role) && loaded && !saving;
  return (
    <section aria-labelledby="camera-blur" className="space-y-2">
      <h3 id="camera-blur" className={HEADING}>
        Privacy
      </h3>
      <div className={`${CARD} space-y-2 p-4`}>
        <div className="flex items-center justify-between gap-4">
          <span id="camera-blur-label" className="font-semibold">
            Blur faces
          </span>
          <button
            type="button"
            role="switch"
            aria-checked={enabled}
            aria-labelledby="camera-blur-label"
            disabled={!canChange}
            onClick={toggle}
            className={`relative h-6 w-10 shrink-0 rounded-full transition-colors disabled:opacity-50 ${
              enabled ? "bg-brand-600" : "bg-slate-300 dark:bg-slate-700"
            }`}
          >
            <span
              aria-hidden
              className={`absolute top-0.5 size-5 rounded-full bg-white shadow transition-[left] ${enabled ? "left-[1.125rem]" : "left-0.5"}`}
            />
          </button>
        </div>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Blurs faces in stored stills, snapshots and debug traces. Livestream is never blurred.
        </p>
        {!enabled && <p className="text-sm font-medium text-warm-600 dark:text-warm-400">Faces are stored as recorded for 7 days.</p>}
      </div>
    </section>
  );
}

function StatusBadge({ online }: { online: boolean | null }) {
  const [label, tone] =
    online == null
      ? ["Unknown", "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300"]
      : online
        ? ["Online", "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300"]
        : ["Offline", "bg-rose-100 text-rose-800 dark:bg-rose-500/15 dark:text-rose-300"];
  const dot = online == null ? "bg-slate-400" : online ? "bg-emerald-500" : "bg-rose-500";
  return (
    <span data-testid="camera-status" className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${tone}`}>
      <span aria-hidden className={`size-2 rounded-full ${dot}`} />
      {label}
    </span>
  );
}

function Overview({ info }: { info: CameraInfo }) {
  return (
    <section aria-label="Camera" className={`${CARD} flex items-center gap-4 p-4`}>
      {info.image_url ? (
        <img src={info.image_url} alt={info.name} className="size-16 shrink-0 rounded-xl bg-slate-100 object-contain dark:bg-slate-800" />
      ) : (
        <div aria-hidden className="grid size-16 shrink-0 place-items-center rounded-xl bg-slate-100 dark:bg-slate-800">
          <Video className="size-7 text-slate-400" />
        </div>
      )}
      <div className="min-w-0 flex-1 space-y-1.5">
        <h2 className="truncate text-lg font-bold tracking-tight">{info.name}</h2>
        <StatusBadge online={info.online} />
        {info.ring === "unavailable" && (
          <p className="text-sm text-slate-500 dark:text-slate-400">Could not reach the camera service. Showing saved details.</p>
        )}
      </div>
    </section>
  );
}

function Rows({ rows }: { rows: [string, string][] }) {
  return (
    <dl className={`${CARD} divide-y divide-slate-100 dark:divide-slate-800`}>
      {rows.map(([label, value]) => (
        <div key={label} className="flex items-baseline justify-between gap-4 px-4 py-2.5 text-sm">
          <dt className="text-slate-500 dark:text-slate-400">{label}</dt>
          <dd className={`text-right font-medium ${value === NOT_REPORTED ? "text-slate-400 dark:text-slate-500" : ""}`}>{value}</dd>
        </div>
      ))}
    </dl>
  );
}

function Details({ info }: { info: CameraInfo }) {
  const v = info.video;
  const video: [string, string][] = [
    ["Video codecs", v?.codecs.length ? v.codecs.join(", ") : NOT_REPORTED],
    ["Aspect ratio", v?.ratio ?? NOT_REPORTED],
    ["Max resolution", v?.max_resolution ? resolution(v.max_resolution) : NOT_REPORTED],
    ["Supported resolutions", v?.supported_resolutions.length ? v.supported_resolutions.map(resolution).join(", ") : NOT_REPORTED],
  ];
  const features: [string, string][] = [
    ...(info.image_enhancements ?? []).map((e): [string, string] => [enhancementLabel(e.name), onOff(e.on)]),
    ["Motion detection", onOff(info.motion_detection)],
    ["End-to-end encryption", onOff(info.e2e_encryption)],
  ];
  return (
    <>
      <section aria-labelledby="camera-device" className="space-y-2">
        <h3 id="camera-device" className={HEADING}>
          Device
        </h3>
        <Rows rows={[["Manufacturer", info.manufacturer], ["Location", locationText(info.location)]]} />
      </section>
      <section aria-labelledby="camera-video" className="space-y-2">
        <h3 id="camera-video" className={HEADING}>
          Video
        </h3>
        <Rows rows={video} />
      </section>
      <section aria-labelledby="camera-features" className="space-y-2">
        <h3 id="camera-features" className={HEADING}>
          Features
        </h3>
        <Rows rows={features} />
      </section>
    </>
  );
}

interface Span {
  from: number;
  to: number;
  state: "online" | "offline" | "unknown";
}

/** The 30-day window as spans: unknown before the first known time, then each change's state.
 * The state before the window's first change is taken as the opposite of that change. */
export function timeline(info: CameraInfo): Span[] {
  const end = Date.parse(info.checked_at);
  const start = end - info.uptime.window_days * DAY_MS;
  const since = info.uptime.since ? Date.parse(info.uptime.since) : null;
  if (since == null) return [{ from: start, to: end, state: "unknown" }];
  const changes = [...info.history].sort((a, b) => Date.parse(a.at) - Date.parse(b.at));
  const spans: Span[] = [];
  if (since > start) spans.push({ from: start, to: since, state: "unknown" });
  let at = since;
  let state: boolean | null = changes.length
    ? Date.parse(changes[0].at) <= since
      ? changes[0].online
      : !changes[0].online
    : info.uptime.percent == null
      ? null
      : info.uptime.percent >= 50;
  for (const c of changes) {
    const t = Math.max(Date.parse(c.at), since);
    if (t > at) spans.push({ from: at, to: t, state: state == null ? "unknown" : state ? "online" : "offline" });
    at = t;
    state = c.online;
  }
  if (end > at) spans.push({ from: at, to: end, state: state == null ? "unknown" : state ? "online" : "offline" });
  return spans;
}

const MIN_SPAN_PCT = 1.5;
const SPAN_COLOR = { online: "bg-emerald-500", offline: "bg-rose-500", unknown: "bg-slate-200 dark:bg-slate-700" };

function History({ info }: { info: CameraInfo }) {
  const end = Date.parse(info.checked_at);
  const start = end - info.uptime.window_days * DAY_MS;
  const pct = (t: number) => ((t - start) / (end - start)) * 100;
  return (
    <section aria-labelledby="camera-history" className="space-y-2">
      <h3 id="camera-history" className={HEADING}>
        Online history
      </h3>
      <div className={`${CARD} space-y-3 p-4`}>
        <div className="flex items-baseline justify-between gap-2">
          <p className="text-2xl font-bold tracking-tight tabular-nums">
            {info.uptime.percent == null ? "–" : `${info.uptime.percent.toFixed(1)}% online`}
          </p>
          <p className="text-xs text-slate-500 dark:text-slate-400">Last {info.uptime.window_days} days</p>
        </div>
        <div aria-hidden className="relative h-3 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
          {timeline(info).map((s) => {
            // Short outages get a visible minimum width, kept inside the bar and drawn on top.
            const width = Math.max(pct(s.to) - pct(s.from), MIN_SPAN_PCT);
            return (
              <span
                key={s.from}
                data-testid={`timeline-${s.state}`}
                className={`absolute inset-y-0 ${SPAN_COLOR[s.state]} ${s.state === "offline" ? "z-10" : ""}`}
                style={{ left: `${Math.min(pct(s.from), 100 - width)}%`, width: `${width}%` }}
              />
            );
          })}
        </div>
        <div aria-hidden className="flex justify-between text-[11px] text-slate-400">
          <span>{info.uptime.window_days} d ago</span>
          <span>Now</span>
        </div>
        {info.history.length ? (
          <ul aria-label="Status changes" className="divide-y divide-slate-100 text-sm dark:divide-slate-800">
            {info.history.map((c) => (
              <ChangeRow key={c.at} change={c} />
            ))}
          </ul>
        ) : (
          <p className="text-sm text-slate-500 dark:text-slate-400">No status changes recorded yet.</p>
        )}
      </div>
    </section>
  );
}

function ChangeRow({ change }: { change: StatusChange }) {
  return (
    <li className="flex items-center justify-between gap-3 py-2">
      <span className="inline-flex items-center gap-2 font-medium">
        <span aria-hidden className={`size-2 rounded-full ${change.online ? "bg-emerald-500" : "bg-rose-500"}`} />
        {change.online ? "Online" : "Offline"}
      </span>
      <span className="text-slate-500 tabular-nums dark:text-slate-400">
        {dayLabel(change.at)} {clock(change.at)}
        {change.source === "poll" && <span className="ml-1 text-xs">(seen)</span>}
      </span>
    </li>
  );
}

/** How this browser decodes the camera's live video: read during a Livestream run, shown after. */
function Decoder({ createPeer }: { createPeer?: () => RTCPeerConnection | null }) {
  const [open, setOpen] = useState(false);
  const [shown, setShown] = useState<DecoderStats | null>(null);
  const latest = useRef<DecoderStats | null>(null);
  const onStats = useCallback((stats: DecoderStats) => {
    latest.current = stats;
  }, []);
  const close = () => {
    setOpen(false);
    if (latest.current) setShown(latest.current);
  };
  const text = (v: string | null) => v ?? NOT_REPORTED;
  return (
    <section aria-labelledby="camera-decoder" className="space-y-2">
      <h3 id="camera-decoder" className={HEADING}>
        Decoder
      </h3>
      {shown ? (
        <Rows
          rows={[
            ["Codec", text(shown.codec)],
            ["Decoder", text(shown.decoder)],
            ["Frame size", shown.width && shown.height ? `${shown.width} × ${shown.height}` : NOT_REPORTED],
            ["Frame rate", shown.fps != null ? `${Math.round(shown.fps)} fps` : NOT_REPORTED],
          ]}
        />
      ) : (
        <p className={`${CARD} p-4 text-sm text-slate-500 dark:text-slate-400`}>
          Run a check to see how this browser decodes the camera's video.
        </p>
      )}
      <button type="button" onClick={() => setOpen(true)} className={`${PRIMARY} inline-flex items-center justify-center gap-2`}>
        <Cpu aria-hidden className="size-5" />
        Check decoder
      </button>
      {open && <LiveStream onClose={close} createPeer={createPeer} onStats={onStats} />}
    </section>
  );
}
