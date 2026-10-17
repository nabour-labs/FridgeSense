import { Camera, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { ApiError } from "../api/client";
import type { FridgeAreaBody, Snapshot } from "../api/types";
import { canEdit, useApp } from "../AppContext";
import { ImageMarkup } from "../components/ImageMarkup";
import { NoData } from "../components/NoData";
import { Sheet } from "../components/Sheet";
import { clock, dayLabel } from "../format";
import { boxShape, shapeToBox, type Shape } from "../shapes";
import { useLoad } from "../useLoad";
import { CARD, HEADING, PRIMARY } from "./configStyles";
import { NO_FOOTAGE } from "./ReferenceImages";

const AREA_COLOR = "#0ea5e9";

/** The owner's box around the fridge, drawn on a camera snapshot; used later to crop stills. */
export function FridgeArea() {
  const { api, role } = useApp();
  const editable = canEdit(role);
  const { data, setData, failed } = useLoad(
    useCallback(() => api.fridgeArea(), [api]),
    60_000,
  );
  const [editing, setEditing] = useState(false);

  if (!data) {
    if (failed) return <NoData />;
    return <div aria-hidden data-testid="loading" className="h-64 animate-pulse rounded-3xl bg-slate-200/70 dark:bg-slate-800" />;
  }

  const area = data.area;
  return (
    <section aria-labelledby="fridge-area" className="space-y-3">
      <h2 id="fridge-area" className={HEADING}>
        Fridge area
      </h2>
      <p className="px-1 text-sm text-slate-500 dark:text-slate-400">
        A box around the fridge in the camera's view. Stills will be cropped to it before analysis.
      </p>
      {area ? (
        <figure className={`${CARD} overflow-hidden`}>
          <ImageMarkup
            src={`data:image/jpeg;base64,${area.image}`}
            alt="Fridge area"
            shapes={[boxShape(area.box)]}
            color={AREA_COLOR}
            readOnly
            className="rounded-none"
          />
          <figcaption className="px-3 py-2 text-sm text-slate-600 dark:text-slate-300">
            Saved {dayLabel(area.updated_at).toLowerCase()} at {clock(area.updated_at)}
          </figcaption>
        </figure>
      ) : (
        <p className={`${CARD} p-4 text-sm`}>No fridge area yet.</p>
      )}
      {editable && (
        <button type="button" onClick={() => setEditing(true)} className={`${PRIMARY} inline-flex items-center justify-center gap-2`}>
          <Camera aria-hidden className="size-5" />
          {area ? "Change area" : "Set area"}
        </button>
      )}
      {editing && (
        <SetFridgeArea
          onClose={() => setEditing(false)}
          onSaved={(next) => {
            setData(next);
            setEditing(false);
          }}
        />
      )}
    </section>
  );
}

function SetFridgeArea({ onClose, onSaved }: { onClose: () => void; onSaved: (body: FridgeAreaBody) => void }) {
  const { api, report } = useApp();
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [snapping, setSnapping] = useState(false);
  const [shapes, setShapes] = useState<Shape[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const valid = snap !== null && shapes.length === 1;

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
      onSaved(await api.saveFridgeArea(snap.image, shapeToBox(shapes[0])));
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) setError(err.message);
      else report(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Sheet title="Set the fridge area" onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        {snap ? (
          <>
            <ImageMarkup
              src={`data:image/jpeg;base64,${snap.image}`}
              alt="Snapshot to box the fridge on"
              shapes={shapes}
              onChange={setShapes}
              tool="box"
              single
              color={AREA_COLOR}
            />
            <div className="flex items-center justify-between gap-3 px-1">
              <p className="text-xs text-slate-500 dark:text-slate-400">Drag a box around the whole fridge, doors included.</p>
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
        <div className="flex gap-2">
          <button
            type="button"
            onClick={onClose}
            className="h-12 flex-1 rounded-xl font-semibold text-slate-700 ring-1 ring-slate-300 transition hover:bg-slate-50 dark:text-slate-200 dark:ring-slate-700 dark:hover:bg-slate-800"
          >
            Cancel
          </button>
          <button type="submit" disabled={!valid || busy} className={`${PRIMARY} flex-1`}>
            Save
          </button>
        </div>
      </form>
    </Sheet>
  );
}
