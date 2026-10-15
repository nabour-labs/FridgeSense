import { ImagePlus, Trash2 } from "lucide-react";
import { useCallback, useState, type FormEvent } from "react";
import { ApiError } from "../api/client";
import type { Config as ConfigData } from "../api/types";
import { useApp } from "../AppContext";
import { NoData } from "../components/NoData";
import { Sheet } from "../components/Sheet";
import { toJpeg, type Resize } from "../image";
import { useLoad } from "../useLoad";

const MAX_REFERENCES = 6;
const MAX_ANNOTATION = 80;
const MAX_INSTRUCTIONS = 1000;
const HEADING = "px-1 text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400";
const CARD =
  "rounded-2xl bg-white shadow-sm shadow-slate-900/5 ring-1 ring-slate-200 dark:bg-slate-900 dark:shadow-none dark:ring-slate-800";
const INPUT =
  "w-full rounded-xl border border-slate-300 bg-white px-3 outline-none focus:border-brand-500 focus:ring-4 focus:ring-brand-500/15 dark:border-slate-700 dark:bg-slate-950";
const PRIMARY =
  "h-12 w-full rounded-xl bg-brand-600 font-semibold text-white transition hover:bg-brand-700 active:scale-[0.98] disabled:opacity-50";

/** The owner's reference images and custom instructions for the analysis. */
export function Config({ resize = toJpeg }: { resize?: Resize }) {
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
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [annotation, setAnnotation] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const valid = file !== null && annotation.trim().length > 0;

  function pick(next: File | null) {
    setFile(next);
    setError(null);
    if (preview) URL.revokeObjectURL(preview);
    setPreview(next && typeof URL.createObjectURL === "function" ? URL.createObjectURL(next) : null);
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!valid) return;
    setBusy(true);
    setError(null);
    try {
      onAdded(await api.addReference(annotation.trim(), await resize(file)));
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
        <div>
          <label htmlFor="ref-photo" className="mb-2 block text-sm font-medium">
            Photo
          </label>
          {preview && <img src={preview} alt="" className="mb-3 aspect-square w-32 rounded-xl object-cover" />}
          <input
            id="ref-photo"
            type="file"
            accept="image/*"
            onChange={(e) => pick(e.target.files?.[0] ?? null)}
            className="block w-full text-sm file:mr-3 file:rounded-full file:border-0 file:bg-brand-50 file:px-4 file:py-2 file:font-semibold file:text-brand-700 dark:file:bg-brand-950 dark:file:text-brand-300"
          />
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
