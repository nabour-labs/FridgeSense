import { Camera, ImagePlus, Trash2, Undo2 } from "lucide-react";
import { useCallback, useState, type FormEvent } from "react";
import { ApiError } from "../api/client";
import type { Config as ConfigData } from "../api/types";
import { useApp } from "../AppContext";
import { ImageMarkup } from "../components/ImageMarkup";
import { NoData } from "../components/NoData";
import { Sheet } from "../components/Sheet";
import { toJpeg, type Resize } from "../image";
import type { Shape, ShapeKind } from "../shapes";
import { useLoad } from "../useLoad";
import { CARD, HEADING, INPUT, PRIMARY } from "./configStyles";

const MAX_REFERENCES = 6;
const MAX_ANNOTATION = 80;
const MAX_INSTRUCTIONS = 1000;
/** The owner's reference images and custom instructions for the analysis. */
export function ReferenceImages({ resize = toJpeg }: { resize?: Resize }) {
  const { api, report, role } = useApp();
  const canEdit = role === "owner";
  const {
    data: config,
    setData: setConfig,
    failed,
  } = useLoad(
    useCallback(() => api.config(), [api]),
    60_000,
  );
  const [adding, setAdding] = useState(false);

  if (!config) {
    if (failed) return <NoData />;
    return <div aria-hidden data-testid="loading" className="h-64 animate-pulse rounded-3xl bg-slate-200/70 dark:bg-slate-800" />;
  }

  async function remove(id: string, annotation: string) {
    if (!confirm(`Delete the reference "${annotation}"?`)) return;
    try {
      setConfig(await api.deleteReference(id));
    } catch (err) {
      report(err);
    }
  }

  const full = config.references.length >= MAX_REFERENCES;
  return (
    <div className="space-y-6">
      <section aria-labelledby="cfg-refs">
        <div className="mb-2 flex items-center justify-between gap-3">
          <h2 id="cfg-refs" className={HEADING}>
            Reference images
          </h2>
          <span className="text-xs font-medium tabular-nums text-slate-500 dark:text-slate-400">
            {config.references.length} of {MAX_REFERENCES}
          </span>
        </div>
        <p className="mb-3 px-1 text-sm text-slate-500 dark:text-slate-400">
          Photos of items in this fridge, each with a short note, help the camera tell similar things apart.
        </p>
        <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {config.references.map((r) => (
            <li key={r.id} className={`${CARD} overflow-hidden`}>
              <img src={`data:image/jpeg;base64,${r.image}`} alt={r.annotation} className="aspect-square w-full object-cover" />
              <div className="flex items-start gap-1 py-2 pl-3 pr-1">
                <p className="min-w-0 flex-1 break-words py-1.5 text-sm font-medium">{r.annotation}</p>
                {canEdit && (
                  <button
                    type="button"
                    aria-label={`Delete ${r.annotation}`}
                    onClick={() => remove(r.id, r.annotation)}
                    className="grid size-9 shrink-0 place-items-center rounded-full text-slate-500 transition hover:bg-red-50 hover:text-red-600 dark:text-slate-400 dark:hover:bg-red-950/50 dark:hover:text-red-400"
                  >
                    <Trash2 aria-hidden className="size-4" />
                  </button>
                )}
              </div>
            </li>
          ))}
          {canEdit && (
            <li>
              <button
                type="button"
                onClick={() => setAdding(true)}
                disabled={full}
                className="flex aspect-square w-full flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-slate-300 text-sm font-semibold text-slate-600 transition hover:border-brand-400 hover:text-brand-700 disabled:opacity-50 disabled:hover:border-slate-300 disabled:hover:text-slate-600 dark:border-slate-700 dark:text-slate-300 dark:hover:border-brand-600 dark:hover:text-brand-300"
              >
                <ImagePlus aria-hidden className="size-7" strokeWidth={1.75} />
                Add
              </button>
            </li>
          )}
        </ul>
      </section>
      <section aria-labelledby="cfg-instructions">
        <h2 id="cfg-instructions" className={`${HEADING} mb-2`}>
          Custom instructions
        </h2>
        {canEdit ? (
          <Instructions saved={config.instructions} onSaved={setConfig} />
        ) : (
          <p className={`${CARD} whitespace-pre-wrap p-4 text-sm`}>{config.instructions || "None yet."}</p>
        )}
      </section>
      {adding && (
        <AddReference
          resize={resize}
          onClose={() => setAdding(false)}
          onAdded={(next) => {
            setConfig(next);
            setAdding(false);
          }}
        />
      )}
    </div>
  );
}

function Instructions({ saved, onSaved }: { saved: string; onSaved: (config: ConfigData) => void }) {
  const { api, report } = useApp();
  const [draft, setDraft] = useState(saved);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const over = draft.length > MAX_INSTRUCTIONS;

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (over || draft === saved) return;
    setBusy(true);
    try {
      const next = await api.saveInstructions(draft);
      setDraft(next.instructions);
      onSaved(next);
      setDone(true);
    } catch (err) {
      report(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <p className="px-1 text-sm text-slate-500 dark:text-slate-400">
        Extra rules for the camera, e.g. "Count yogurt cups individually."
      </p>
      <textarea
        aria-labelledby="cfg-instructions"
        value={draft}
        rows={5}
        onChange={(e) => {
          setDraft(e.target.value);
          setDone(false);
        }}
        className={`${INPUT} block py-3 text-sm`}
      />
      <div className="flex items-center justify-between gap-3 px-1 text-xs font-medium tabular-nums">
        <span className={over ? "text-red-600 dark:text-red-400" : "text-slate-500 dark:text-slate-400"}>
          {draft.length} / {MAX_INSTRUCTIONS}
        </span>
        {done && (
          <span role="status" className="text-brand-700 dark:text-brand-300">
            Saved
          </span>
        )}
      </div>
      <button type="submit" disabled={over || draft === saved || busy} className={PRIMARY}>
        Save
      </button>
    </form>
  );
}

export const NO_FOOTAGE = "No recent footage. Walk past the camera, then try again.";

/** The base64 JPEG as a Blob, so a snapshot goes through the same resize as a photo. */
export function jpegBlob(b64: string): Blob {
  const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
  return new Blob([bytes], { type: "image/jpeg" });
}

const TOOL =
  "h-9 rounded-full px-3 text-sm font-semibold ring-1 transition disabled:opacity-40 aria-pressed:bg-brand-600 aria-pressed:text-white aria-pressed:ring-brand-600";
const TOOL_IDLE = "bg-white text-slate-700 ring-slate-300 dark:bg-slate-900 dark:text-slate-200 dark:ring-slate-700";

function AddReference({
  resize,
  onClose,
  onAdded,
}: {
  resize: Resize;
  onClose: () => void;
  onAdded: (config: ConfigData) => void;
}) {
  const { api, report } = useApp();
  const [source, setSource] = useState<Blob | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [shapes, setShapes] = useState<Shape[]>([]);
  const [tool, setTool] = useState<ShapeKind>("box");
  const [annotation, setAnnotation] = useState("");
  const [busy, setBusy] = useState(false);
  const [snapping, setSnapping] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const valid = source !== null && annotation.trim().length > 0;

  function use(next: Blob | null, url: string | null) {
    if (preview?.startsWith("blob:")) URL.revokeObjectURL(preview);
    setSource(next);
    setPreview(url);
    setShapes([]);
    setError(null);
  }

  function pick(file: File | null) {
    use(file, file && typeof URL.createObjectURL === "function" ? URL.createObjectURL(file) : null);
  }

  async function snapshot() {
    setSnapping(true);
    setError(null);
    try {
      const snap = await api.cameraSnapshot();
      use(jpegBlob(snap.image), `data:image/jpeg;base64,${snap.image}`);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) setError(NO_FOOTAGE);
      else if (err instanceof ApiError && err.status === 502) setError("The camera can't be reached right now.");
      else report(err);
    } finally {
      setSnapping(false);
    }
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!valid) return;
    setBusy(true);
    setError(null);
    try {
      const image = shapes.length ? await resize(source, shapes) : await resize(source);
      onAdded(await api.addReference(annotation.trim(), image));
    } catch (err) {
      if (err instanceof ApiError && (err.status === 400 || err.status === 409)) setError(err.message);
      else report(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Sheet title="Add a reference" onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <label
              htmlFor="ref-photo"
              className="inline-flex h-9 cursor-pointer items-center gap-1.5 rounded-full bg-brand-50 px-3.5 text-sm font-semibold text-brand-700 transition hover:bg-brand-100 has-[:focus-visible]:ring-4 has-[:focus-visible]:ring-brand-500/30 dark:bg-brand-950 dark:text-brand-300"
            >
              <ImagePlus aria-hidden className="size-4" />
              Choose photo
              <input
                id="ref-photo"
                type="file"
                accept="image/*"
                onChange={(e) => pick(e.target.files?.[0] ?? null)}
                className="sr-only"
              />
            </label>
            <button
              type="button"
              onClick={snapshot}
              disabled={snapping}
              className="inline-flex h-9 items-center gap-1.5 rounded-full bg-brand-50 px-3.5 text-sm font-semibold text-brand-700 transition hover:bg-brand-100 disabled:opacity-50 dark:bg-brand-950 dark:text-brand-300"
            >
              <Camera aria-hidden className="size-4" />
              {snapping ? "Taking snapshot…" : "Camera snapshot"}
            </button>
          </div>
          {preview && (
            <>
              <ImageMarkup src={preview} alt="Reference to draw on" shapes={shapes} onChange={setShapes} tool={tool} />
              <div className="flex items-center gap-2">
                {(["box", "line"] as const).map((t) => (
                  <button
                    key={t}
                    type="button"
                    aria-pressed={tool === t}
                    onClick={() => setTool(t)}
                    className={`${TOOL} ${tool === t ? "" : TOOL_IDLE}`}
                  >
                    {t === "box" ? "Box" : "Line"}
                  </button>
                ))}
                <button
                  type="button"
                  onClick={() => setShapes((s) => s.slice(0, -1))}
                  disabled={shapes.length === 0}
                  className={`${TOOL} ${TOOL_IDLE} ml-auto inline-flex items-center gap-1`}
                >
                  <Undo2 aria-hidden className="size-4" />
                  Undo
                </button>
              </div>
              <p className="px-1 text-xs text-slate-500 dark:text-slate-400">Drag on the image to point out what matters.</p>
            </>
          )}
        </div>
        <div>
          <label htmlFor="ref-annotation" className="mb-2 block text-sm font-medium">
            Annotation
          </label>
          <input
            id="ref-annotation"
            value={annotation}
            maxLength={MAX_ANNOTATION}
            placeholder="e.g. milk bag (2 L, white with blue print)"
            onChange={(e) => setAnnotation(e.target.value)}
            className={`${INPUT} h-12`}
          />
        </div>
        {error && (
          <p role="alert" className="text-sm font-medium text-red-600 dark:text-red-400">
            {error}
          </p>
        )}
        <button type="submit" disabled={!valid || busy} className={PRIMARY}>
          Save
        </button>
      </form>
    </Sheet>
  );
}
