import { Camera, Pencil, Plus, RefreshCw, Trash2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { CameraOffline, NoVideo } from "../camera/liveSnapshot";
import { RecentClipPicker } from "../camera/RecentClipPicker";
import { ApiError } from "../api/client";
import type { DoorFeature, DoorReference, DoorSetup, DoorStatus, DoorZone, Snapshot } from "../api/types";
import { canEdit, useApp } from "../AppContext";
import { ImageMarkup } from "../components/ImageMarkup";
import { NoData } from "../components/NoData";
import { Sheet } from "../components/Sheet";
import { useDebug } from "../debug/DebugContext";
import { ago } from "../format";
import { boxShape, shapeToBox, type Shape } from "../shapes";
import { useLoad } from "../useLoad";
import { CARD, HEADING, INPUT, PRIMARY } from "./configStyles";
import { NO_FOOTAGE } from "./ReferenceImages";

const MAX_DOOR_ZONES = 6;
const MAX_DOOR_REFERENCES = 24;
const MAX_ZONE_NAME = 30;
const ZONE_COLOR = "#14b8a6";
const FEATURE_LABEL: Record<DoorFeature, string> = {
  blue: "Blue light",
  color: "Color",
  brightness: "Brightness",
  change: "Change",
};
const ICON_BUTTON =
  "grid size-9 shrink-0 place-items-center rounded-full text-slate-500 transition dark:text-slate-400";

const percent = (v: number) => `${(v * 100).toFixed(1)}%`;
/** A camera shift as a percent of the frame, without a trailing ".0": "1.6%", "0%". */
const shift = (v: number) => `${Number((v * 100).toFixed(1))}%`;

function ReplaceNote() {
  return (
    <span className="shrink-0 text-xs font-medium text-amber-700 dark:text-amber-300">Replace with a clip frame</span>
  );
}

/** What a zone still needs before setup can run, or null when it has both. */
function needs(zone: DoorZone): string | null {
  if (zone.open > 0 && zone.closed > 0) return null;
  if (zone.open === 0 && zone.closed === 0) return "Needs an open and a closed reference";
  return zone.open === 0 ? "Needs an open reference" : "Needs a closed reference";
}

function StatusBadge({ status }: { status: DoorStatus }) {
  const open = status === "open";
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ${
        open
          ? "bg-amber-50 text-amber-800 ring-amber-200 dark:bg-amber-950/60 dark:text-amber-200 dark:ring-amber-900"
          : "bg-slate-100 text-slate-700 ring-slate-200 dark:bg-slate-800 dark:text-slate-200 dark:ring-slate-700"
      }`}
    >
      {open ? "Open" : "Closed"}
    </span>
  );
}

/** Door setup in two steps: name and box each door zone, then add open and closed references
 * for each zone, then run setup. */
export function DoorDetection() {
  const { api, report, role } = useApp();
  const editable = canEdit(role);
  const { data, setData, failed } = useLoad(
    useCallback(() => api.doorCalibration(), [api]),
    60_000,
  );
  /** The zone sheet: "new", the zone being edited, or closed. */
  const [zoneSheet, setZoneSheet] = useState<DoorZone | "new" | null>(null);
  const [adding, setAdding] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  /** Scores measured by a failed setup run, shown until the next change. */
  const [tried, setTried] = useState<Record<string, number | null> | null>(null);

  if (!data) {
    if (failed) return <NoData />;
    return <div aria-hidden data-testid="loading" className="h-64 animate-pulse rounded-3xl bg-slate-200/70 dark:bg-slate-800" />;
  }

  function changed(next: DoorSetup) {
    setData(next);
    setTried(null);
    setError(null);
  }

  async function removeZone(zone: DoorZone) {
    const n = zone.open + zone.closed;
    const question = n === 0 ? `Delete ${zone.name}?` : `Delete ${zone.name} and its ${n} reference${n === 1 ? "" : "s"}?`;
    if (!confirm(question)) return;
    try {
      changed(await api.deleteDoorZone(zone.id));
    } catch (err) {
      report(err);
    }
  }

  async function remove(ref: DoorReference, n: number) {
    if (!confirm(`Delete door reference ${n}?`)) return;
    try {
      changed(await api.deleteDoorReference(ref.id));
    } catch (err) {
      report(err);
    }
  }

  async function run() {
    setRunning(true);
    setError(null);
    try {
      changed(await api.runDoorSetup());
    } catch (err) {
      if (err instanceof ApiError && err.status === 422) {
        setError(err.message);
        const refs = (err.body as { references?: DoorReference[] } | null)?.references ?? [];
        setTried(Object.fromEntries(refs.map((r) => [r.id, r.score])));
      } else report(err);
    } finally {
      setRunning(false);
    }
  }

  const { zones, references: refs } = data;
  // Pictures from the live view are framed unlike the recorded clips: setup refuses them.
  const live = zones.some((z) => z.source === "live") || refs.some((r) => r.source === "live");
  const ready = zones.length > 0 && zones.every((z) => needs(z) === null) && !live;
  const scoreOf = (r: DoorReference) => (tried ? (tried[r.id] ?? null) : r.score);
  // References are numbered in the order they are shown: zone by zone.
  const shown = zones.flatMap((z) => refs.filter((r) => r.zone_id === z.id));
  const number = (r: DoorReference) => shown.indexOf(r) + 1;

  return (
    <div className="space-y-6">
      <section aria-labelledby="door-zones">
        <div className="mb-2 flex items-center justify-between gap-3">
          <h2 id="door-zones" className={HEADING}>
            1. Door zones
          </h2>
          <span className="text-xs font-medium tabular-nums text-slate-500 dark:text-slate-400">
            {zones.length} of {MAX_DOOR_ZONES}
          </span>
        </div>
        <p className="mb-3 px-1 text-sm text-slate-500 dark:text-slate-400">
          Draw one box around each door or drawer to watch, big enough to cover it open and closed.
        </p>
        <ul className="space-y-2">
          {zones.map((z) => (
            <li key={z.id} className={`${CARD} flex items-center gap-2 py-1 pl-4 pr-1`}>
              <span className="flex-1 truncate text-sm font-semibold">{z.name}</span>
              {z.source === "live" && <ReplaceNote />}
              {editable && (
                <>
                  <button
                    type="button"
                    aria-label={`Edit ${z.name}`}
                    onClick={() => setZoneSheet(z)}
                    className={`${ICON_BUTTON} hover:bg-brand-50 hover:text-brand-700 dark:hover:bg-brand-950 dark:hover:text-brand-300`}
                  >
                    <Pencil aria-hidden className="size-4" />
                  </button>
                  <button
                    type="button"
                    aria-label={`Delete ${z.name}`}
                    onClick={() => removeZone(z)}
                    className={`${ICON_BUTTON} hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950/50 dark:hover:text-red-400`}
                  >
                    <Trash2 aria-hidden className="size-4" />
                  </button>
                </>
              )}
            </li>
          ))}
        </ul>
        {editable && (
          <button
            type="button"
            onClick={() => setZoneSheet("new")}
            disabled={zones.length >= MAX_DOOR_ZONES}
            className="mt-2 inline-flex h-10 items-center gap-1.5 rounded-full bg-brand-50 px-4 text-sm font-semibold text-brand-700 disabled:opacity-50 dark:bg-brand-950 dark:text-brand-300"
          >
            <Plus aria-hidden className="size-4" />
            Add zone
          </button>
        )}
      </section>

      <section aria-labelledby="door-refs">
        <div className="mb-2 flex items-center justify-between gap-3">
          <h2 id="door-refs" className={HEADING}>
            2. References
          </h2>
          <span className="text-xs font-medium tabular-nums text-slate-500 dark:text-slate-400">
            {refs.length} of {MAX_DOOR_REFERENCES}
          </span>
        </div>
        <p className="mb-3 px-1 text-sm text-slate-500 dark:text-slate-400">
          {zones.length === 0
            ? "Add a door zone first."
            : "Snapshots of each zone, marked open or closed. Each zone needs at least one of each."}
        </p>
        <div className="space-y-4">
          {zones.map((z) => (
            <ZoneReferences key={z.id} zone={z}>
              {refs
                .filter((r) => r.zone_id === z.id)
                .map((r) => {
                  const score = scoreOf(r);
                  const n = number(r);
                  return (
                    <li key={r.id} className={`${CARD} overflow-hidden`}>
                      <ImageMarkup
                        src={`data:image/jpeg;base64,${r.image}`}
                        alt={`Door reference ${n}, ${r.status}`}
                        shapes={[boxShape(r.box)]}
                        color={ZONE_COLOR}
                        readOnly
                        className="rounded-none"
                      />
                      <div className="flex items-center gap-2 py-2 pl-3 pr-1">
                        <StatusBadge status={r.status} />
                        <span className="flex-1 text-sm font-medium tabular-nums text-slate-600 dark:text-slate-300">
                          {score === null ? "–" : percent(score)}
                        </span>
                        {r.source === "live" && <ReplaceNote />}
                        {editable && (
                          <button
                            type="button"
                            aria-label={`Delete reference ${n}`}
                            onClick={() => remove(r, n)}
                            className={`${ICON_BUTTON} hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950/50 dark:hover:text-red-400`}
                          >
                            <Trash2 aria-hidden className="size-4" />
                          </button>
                        )}
                      </div>
                    </li>
                  );
                })}
            </ZoneReferences>
          ))}
        </div>
        {editable && (
          <button
            type="button"
            onClick={() => setAdding(true)}
            disabled={zones.length === 0 || refs.length >= MAX_DOOR_REFERENCES}
            className="mt-3 inline-flex h-10 items-center gap-1.5 rounded-full bg-brand-50 px-4 text-sm font-semibold text-brand-700 disabled:opacity-50 dark:bg-brand-950 dark:text-brand-300"
          >
            <Camera aria-hidden className="size-4" />
            Add reference
          </button>
        )}
      </section>

      <section aria-labelledby="door-setup" className="space-y-3">
        <h2 id="door-setup" className={HEADING}>
          Setup
        </h2>
        <div className={`${CARD} space-y-1 p-4 text-sm`}>
          {data.setup === null ? (
            <p>Not set up yet. Using default zones.</p>
          ) : (
            <>
              {data.setup.zones.map((z, i) => (
                <p key={i} className="font-medium">
                  {`${z.name || `Zone ${i + 1}`}: ${FEATURE_LABEL[z.feature]} ${z.direction} ${percent(z.threshold)}, margin ${percent(z.margin)}`}
                </p>
              ))}
              {data.setup.stale && (
                <p className="font-medium text-amber-700 dark:text-amber-300">Zones or references changed. Run setup again.</p>
              )}
              {data.alignment?.moved && (
                <p className="font-medium text-amber-700 dark:text-amber-300">
                  Camera moved: add new references and run setup.
                </p>
              )}
              {data.alignment?.checked_at && (
                <p className="text-slate-500 dark:text-slate-400">
                  {`Adjusted for camera shift of ${shift(data.alignment.dx)} across, ${shift(data.alignment.dy)} down (checked ${ago(data.alignment.checked_at)})`}
                </p>
              )}
              {data.setup.tuned_at && (
                <p className="text-slate-500 dark:text-slate-400">
                  {`Tuned from ${data.setup.tuned_from} recent openings, ${ago(data.setup.tuned_at)}`}
                </p>
              )}
            </>
          )}
        </div>
        {error && (
          <p role="alert" className="px-1 text-sm font-medium text-red-600 dark:text-red-400">
            {error}
          </p>
        )}
        {editable && (
          <>
            {live ? (
              <p className="px-1 text-sm text-slate-500 dark:text-slate-400">
                Replace the zones and references marked 'Replace with a clip frame' first.
              </p>
            ) : (
              zones.length > 0 &&
              !ready && (
                <p className="px-1 text-sm text-slate-500 dark:text-slate-400">
                  Each zone needs at least one open and one closed reference.
                </p>
              )
            )}
            <button type="button" onClick={run} disabled={running || !ready} className={PRIMARY}>
              {running ? "Running setup…" : "Run setup"}
            </button>
          </>
        )}
      </section>

      {zoneSheet && (
        <ZoneSheet
          zone={zoneSheet === "new" ? null : zoneSheet}
          onClose={() => setZoneSheet(null)}
          onSaved={(next) => {
            changed(next);
            setZoneSheet(null);
          }}
        />
      )}
      {adding && (
        <AddDoorReference
          zones={zones}
          onClose={() => setAdding(false)}
          onAdded={(next) => {
            changed(next);
            setAdding(false);
          }}
        />
      )}
    </div>
  );
}

function ZoneReferences({ zone, children }: { zone: DoorZone; children: ReactNode }) {
  const missing = needs(zone);
  const id = `door-zone-${zone.id}`;
  return (
    <div role="group" aria-labelledby={id}>
      <div className="mb-2 flex flex-wrap items-baseline gap-x-2 px-1">
        <h3 id={id} className="text-sm font-semibold">
          {zone.name}
        </h3>
        <span className="text-xs tabular-nums text-slate-500 dark:text-slate-400">
          {`${zone.open} open · ${zone.closed} closed`}
        </span>
        {missing && <span className="text-xs font-medium text-amber-700 dark:text-amber-300">{missing}</span>}
      </div>
      <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3">{children}</ul>
    </div>
  );
}

/**
 * The picture a door sheet is drawn on: a frame of a recent recorded clip, so zones and
 * references are framed exactly like the clips the door check scores. The recent-clip picker
 * opens with the sheet; cancelling it before any frame closes the sheet (`onCancel`). With
 * Mock video on, the frame comes from the mock clip picker through `cameraSnapshot` instead.
 */
function useClipFrame(onSnap: () => void, onCancel: () => void) {
  const { api, report } = useApp();
  const { mockVideo } = useDebug();
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [picking, setPicking] = useState(!mockVideo);
  const [snapping, setSnapping] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const onSnapRef = useRef(onSnap);
  onSnapRef.current = onSnap;

  const cancel = useRef<AbortController | null>(null);
  const takeSnapshot = useCallback(async () => {
    cancel.current?.abort();
    const controller = (cancel.current = new AbortController());
    setSnapping(true);
    setError(null);
    try {
      setSnap(await api.cameraSnapshot(controller.signal));
      onSnapRef.current();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) setError(NO_FOOTAGE);
      else if (err instanceof NoVideo || err instanceof CameraOffline) setError(err.message);
      else if (err instanceof ApiError && err.status === 502) setError("The camera can't be reached right now.");
      else report(err);
    } finally {
      setSnapping(false);
    }
  }, [api, report]);

  useEffect(() => {
    if (mockVideo) void takeSnapshot();
    return () => cancel.current?.abort();
  }, [mockVideo, takeSnapshot]);

  const another = mockVideo ? takeSnapshot : () => setPicking(true);
  const picker = picking ? (
    <RecentClipPicker
      api={api}
      report={report}
      onPick={(frame) => {
        setPicking(false);
        setError(null);
        setSnap(frame);
        onSnapRef.current();
      }}
      onCancel={() => {
        setPicking(false);
        if (!snap) onCancel();
      }}
    />
  ) : null;

  return { snap, snapping, error, setError, another, picker };
}

function SnapshotView({
  snapshot,
  hint,
  children,
}: {
  snapshot: ReturnType<typeof useClipFrame>;
  hint: string;
  children: (snap: Snapshot) => ReactNode;
}) {
  const { snap, snapping, error, another } = snapshot;
  return (
    <>
      {snap ? (
        <>
          {children(snap)}
          <div className="flex items-center justify-between gap-3 px-1">
            <p className="text-xs text-slate-500 dark:text-slate-400">{hint}</p>
            <button
              type="button"
              onClick={another}
              disabled={snapping}
              className="inline-flex shrink-0 items-center gap-1 text-xs font-semibold text-brand-700 disabled:opacity-50 dark:text-brand-300"
            >
              <RefreshCw aria-hidden className="size-3.5" />
              Another frame
            </button>
          </div>
        </>
      ) : (
        snapping && (
          <div aria-hidden data-testid="snapshot-loading" className="aspect-video animate-pulse rounded-xl bg-slate-200/70 dark:bg-slate-800" />
        )
      )}
      {error && (
        <div className="flex items-center justify-between gap-3">
          <p role="alert" className="text-sm font-medium text-red-600 dark:text-red-400">
            {error}
          </p>
          {!snap && (
            <button
              type="button"
              onClick={another}
              disabled={snapping}
              className="h-9 shrink-0 rounded-full bg-brand-50 px-4 text-sm font-semibold text-brand-700 disabled:opacity-50 dark:bg-brand-950 dark:text-brand-300"
            >
              Try again
            </button>
          )}
        </div>
      )}
    </>
  );
}

function Choice({ pressed, onClick, children }: { pressed: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      onClick={onClick}
      className={`h-11 min-w-0 flex-1 truncate rounded-xl px-3 text-sm font-semibold ring-1 transition ${
        pressed
          ? "bg-brand-600 text-white ring-brand-600"
          : "bg-white text-slate-700 ring-slate-300 hover:ring-brand-400 dark:bg-slate-900 dark:text-slate-200 dark:ring-slate-700"
      }`}
    >
      {children}
    </button>
  );
}

/** Add a door zone, or rename and redraw one. */
function ZoneSheet({
  zone,
  onClose,
  onSaved,
}: {
  zone: DoorZone | null;
  onClose: () => void;
  onSaved: (setup: DoorSetup) => void;
}) {
  const { api, report } = useApp();
  const initial = zone ? [boxShape(zone.box)] : [];
  const [shapes, setShapes] = useState<Shape[]>(initial);
  const [name, setName] = useState(zone?.name ?? "");
  const [busy, setBusy] = useState(false);
  const snapshot = useClipFrame(() => setShapes(initial), onClose);
  const { snap, setError } = snapshot;
  const trimmed = name.trim();
  const valid = snap !== null && shapes.length === 1 && trimmed.length > 0;

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!valid) return;
    setBusy(true);
    setError(null);
    const box = shapeToBox(shapes[0]);
    try {
      onSaved(zone ? await api.updateDoorZone(zone.id, { name: trimmed, box }) : await api.addDoorZone(trimmed, box));
    } catch (err) {
      if (err instanceof ApiError && [400, 404, 409].includes(err.status)) setError(err.message);
      else report(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Sheet title={zone ? `Edit ${zone.name}` : "Add a door zone"} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <SnapshotView snapshot={snapshot} hint="Draw around the door or drawer, open and closed.">
          {(s) => (
            <ImageMarkup
              src={`data:image/jpeg;base64,${s.image}`}
              alt="Snapshot to box the zone on"
              shapes={shapes}
              onChange={setShapes}
              tool="box"
              single
              color={ZONE_COLOR}
            />
          )}
        </SnapshotView>
        <label className="block space-y-1.5">
          <span className="text-sm font-medium">Name</span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={MAX_ZONE_NAME}
            placeholder="Fridge doors, Freezer drawer…"
            className={`${INPUT} h-11`}
          />
        </label>
        <button type="submit" disabled={!valid || busy} className={PRIMARY}>
          Save
        </button>
      </form>
      {snapshot.picker}
    </Sheet>
  );
}

function AddDoorReference({
  zones,
  onClose,
  onAdded,
}: {
  zones: DoorZone[];
  onClose: () => void;
  onAdded: (setup: DoorSetup) => void;
}) {
  const { api, report } = useApp();
  const [zoneId, setZoneId] = useState<string | null>(zones.length === 1 ? zones[0].id : null);
  const [status, setStatus] = useState<DoorStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const snapshot = useClipFrame(() => {}, onClose);
  const { snap, setError } = snapshot;
  const zone = zones.find((z) => z.id === zoneId) ?? null;
  const valid = snap !== null && zone !== null && status !== null;

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!valid) return;
    setBusy(true);
    setError(null);
    try {
      onAdded(await api.addDoorReference(snap.image, zone.id, status));
    } catch (err) {
      if (err instanceof ApiError && (err.status === 400 || err.status === 409)) setError(err.message);
      else report(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Sheet title="Add a door reference" onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <SnapshotView
          snapshot={snapshot}
          hint={zone ? `${zone.name}'s box is shown on the snapshot.` : "Pick the zone this snapshot is for."}
        >
          {(s) => (
            <ImageMarkup
              src={`data:image/jpeg;base64,${s.image}`}
              alt="Snapshot of the door zone"
              shapes={zone ? [boxShape(zone.box)] : []}
              color={ZONE_COLOR}
              readOnly
            />
          )}
        </SnapshotView>
        <fieldset className="space-y-2">
          <legend className="mb-2 text-sm font-medium">Door zone</legend>
          <div className="flex flex-wrap gap-2">
            {zones.map((z) => (
              <Choice key={z.id} pressed={zoneId === z.id} onClick={() => setZoneId(z.id)}>
                {z.name}
              </Choice>
            ))}
          </div>
        </fieldset>
        <fieldset className="space-y-2">
          <legend className="mb-2 text-sm font-medium">In this snapshot the door is</legend>
          <div className="flex gap-2">
            <Choice pressed={status === "open"} onClick={() => setStatus("open")}>
              Open
            </Choice>
            <Choice pressed={status === "closed"} onClick={() => setStatus("closed")}>
              Closed
            </Choice>
          </div>
        </fieldset>
        <button type="submit" disabled={!valid || busy} className={PRIMARY}>
          Save
        </button>
      </form>
      {snapshot.picker}
    </Sheet>
  );
}
