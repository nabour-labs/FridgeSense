import { Camera, RefreshCw, Trash2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { NoVideo } from "../camera/liveSnapshot";
import { ApiError } from "../api/client";
import type { DoorFeature, DoorReference, DoorSetup, DoorStatus, Snapshot } from "../api/types";
import { canEdit, useApp } from "../AppContext";
import { ImageMarkup } from "../components/ImageMarkup";
import { NoData } from "../components/NoData";
import { Sheet } from "../components/Sheet";
import { boxShape, shapeToBox, type Shape } from "../shapes";
import { useLoad } from "../useLoad";
import { CARD, HEADING, PRIMARY } from "./configStyles";
import { NO_FOOTAGE } from "./ReferenceImages";

const MAX_DOOR_REFERENCES = 12;
const ZONE_COLOR = "#14b8a6";
const FEATURE_LABEL: Record<DoorFeature, string> = {
  blue: "Blue light",
  color: "Color",
  brightness: "Brightness",
  change: "Change",
};

const percent = (v: number) => `${(v * 100).toFixed(1)}%`;

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

/** Door references (open/closed snapshots with a box) and the setup that tunes detection. */
export function DoorDetection() {
  const { api, report, role } = useApp();
  const editable = canEdit(role);
  const { data, setData, failed } = useLoad(
    useCallback(() => api.doorCalibration(), [api]),
    60_000,
  );
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

  const refs = data.references;
  const hasOpen = refs.some((r) => r.status === "open");
  const hasClosed = refs.some((r) => r.status === "closed");
  const full = refs.length >= MAX_DOOR_REFERENCES;
  const scoreOf = (r: DoorReference) => (tried ? (tried[r.id] ?? null) : r.score);

  return (
    <div className="space-y-6">
      <section aria-labelledby="door-refs">
        <div className="mb-2 flex items-center justify-between gap-3">
          <h2 id="door-refs" className={HEADING}>
            Door references
          </h2>
          <span className="text-xs font-medium tabular-nums text-slate-500 dark:text-slate-400">
            {refs.length} of {MAX_DOOR_REFERENCES}
          </span>
        </div>
        <p className="mb-3 px-1 text-sm text-slate-500 dark:text-slate-400">
          Snapshots from the camera with a box around a door or drawer, marked open or closed. Add each door both ways, then run setup.
        </p>
        <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {refs.map((r, i) => {
            const score = scoreOf(r);
            return (
              <li key={r.id} className={`${CARD} overflow-hidden`}>
                <ImageMarkup
                  src={`data:image/jpeg;base64,${r.image}`}
                  alt={`Door reference ${i + 1}, ${r.status}`}
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
                  {editable && (
                    <button
                      type="button"
                      aria-label={`Delete reference ${i + 1}`}
                      onClick={() => remove(r, i + 1)}
                      className="grid size-9 shrink-0 place-items-center rounded-full text-slate-500 transition hover:bg-red-50 hover:text-red-600 dark:text-slate-400 dark:hover:bg-red-950/50 dark:hover:text-red-400"
                    >
                      <Trash2 aria-hidden className="size-4" />
                    </button>
                  )}
                </div>
              </li>
            );
          })}
          {editable && (
            <li>
              <button
                type="button"
                onClick={() => setAdding(true)}
                disabled={full}
                className="flex aspect-video w-full flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-slate-300 text-sm font-semibold text-slate-600 transition hover:border-brand-400 hover:text-brand-700 disabled:opacity-50 dark:border-slate-700 dark:text-slate-300 dark:hover:border-brand-600 dark:hover:text-brand-300"
              >
                <Camera aria-hidden className="size-7" strokeWidth={1.75} />
                Add
              </button>
            </li>
          )}
        </ul>
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
                  {`Zone ${i + 1}: ${FEATURE_LABEL[z.feature]} ${z.direction} ${percent(z.threshold)}, margin ${percent(z.margin)}`}
                </p>
              ))}
              {data.setup.stale && (
                <p className="font-medium text-amber-700 dark:text-amber-300">References changed. Run setup again.</p>
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
            {!(hasOpen && hasClosed) && (
              <p className="px-1 text-sm text-slate-500 dark:text-slate-400">Add at least one open and one closed reference.</p>
            )}
            <button type="button" onClick={run} disabled={running || !(hasOpen && hasClosed)} className={PRIMARY}>
              {running ? "Running setup…" : "Run setup"}
            </button>
          </>
        )}
      </section>

      {adding && (
        <AddDoorReference
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

function AddDoorReference({ onClose, onAdded }: { onClose: () => void; onAdded: (setup: DoorSetup) => void }) {
  const { api, report } = useApp();
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [snapping, setSnapping] = useState(false);
  const [shapes, setShapes] = useState<Shape[]>([]);
  const [status, setStatus] = useState<DoorStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const valid = snap !== null && shapes.length === 1 && status !== null;

  const cancel = useRef<AbortController | null>(null);
  const takeSnapshot = useCallback(async () => {
    cancel.current?.abort();
    const controller = (cancel.current = new AbortController());
    setSnapping(true);
    setError(null);
    try {
      setSnap(await api.cameraSnapshot(controller.signal));
      setShapes([]);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) setError(NO_FOOTAGE);
      else if (err instanceof NoVideo) setError(err.message);
      else if (err instanceof ApiError && err.status === 502) setError("The camera can't be reached right now.");
      else report(err);
    } finally {
      setSnapping(false);
    }
  }, [api, report]);

  useEffect(() => {
    void takeSnapshot();
    return () => cancel.current?.abort();
  }, [takeSnapshot]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!valid) return;
    setBusy(true);
    setError(null);
    try {
      onAdded(await api.addDoorReference(snap.image, shapeToBox(shapes[0]), status));
    } catch (err) {
      if (err instanceof ApiError && (err.status === 400 || err.status === 409)) setError(err.message);
      else report(err);
    } finally {
      setBusy(false);
    }
  }

  const choice = (value: DoorStatus, label: string) => (
    <button
      type="button"
      aria-pressed={status === value}
      onClick={() => setStatus(value)}
      className={`h-11 flex-1 rounded-xl text-sm font-semibold ring-1 transition ${
        status === value
          ? "bg-brand-600 text-white ring-brand-600"
          : "bg-white text-slate-700 ring-slate-300 hover:ring-brand-400 dark:bg-slate-900 dark:text-slate-200 dark:ring-slate-700"
      }`}
    >
      {label}
    </button>
  );

  return (
    <Sheet title="Add a door reference" onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        {snap ? (
          <>
            <ImageMarkup
              src={`data:image/jpeg;base64,${snap.image}`}
              alt="Snapshot to box the door on"
              shapes={shapes}
              onChange={setShapes}
              tool="box"
              single
              color={ZONE_COLOR}
            />
            <div className="flex items-center justify-between gap-3 px-1">
              <p className="text-xs text-slate-500 dark:text-slate-400">Drag a box around one door or drawer.</p>
              <button
                type="button"
                onClick={takeSnapshot}
                disabled={snapping}
                className="inline-flex shrink-0 items-center gap-1 text-xs font-semibold text-brand-700 disabled:opacity-50 dark:text-brand-300"
              >
                <RefreshCw aria-hidden className="size-3.5" />
                New snapshot
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
                onClick={takeSnapshot}
                disabled={snapping}
                className="h-9 shrink-0 rounded-full bg-brand-50 px-4 text-sm font-semibold text-brand-700 disabled:opacity-50 dark:bg-brand-950 dark:text-brand-300"
              >
                Try again
              </button>
            )}
          </div>
        )}
        <fieldset className="space-y-2">
          <legend className="mb-2 text-sm font-medium">In this snapshot the door is</legend>
          <div className="flex gap-2">
            {choice("open", "Open")}
            {choice("closed", "Closed")}
          </div>
        </fieldset>
        <button type="submit" disabled={!valid || busy} className={PRIMARY}>
          Save
        </button>
      </form>
    </Sheet>
  );
}
