import { useId, useRef, useState, type ReactNode } from "react";
import { Select, type Option } from "../components/Select";
import { Sheet } from "../components/Sheet";
import { PRIMARY } from "../screens/configStyles";

export interface PickableClip extends Option {
  url: string;
}

/**
 * A sheet that plays one of `clips` with a scrubber and hands the video to `onUse` on "Use this
 * frame". `clips` is null while loading; `empty` is shown when there are none.
 */
export function FramePicker({
  title,
  clips,
  empty,
  notice,
  error,
  crossOrigin,
  onUse,
  onCancel,
}: {
  title: string;
  clips: PickableClip[] | null;
  empty: string;
  notice?: ReactNode;
  error?: string | null;
  crossOrigin?: "anonymous";
  onUse: (video: HTMLVideoElement) => Promise<void>;
  onCancel: () => void;
}) {
  const selectId = useId();
  const [chosen, setChosen] = useState("");
  const [duration, setDuration] = useState(0);
  const [position, setPosition] = useState(0);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const video = useRef<HTMLVideoElement>(null);

  const selected = clips?.find((c) => c.value === chosen) ?? clips?.[0];
  const url = selected?.url ?? "";

  function choose(next: string) {
    setChosen(next);
    setReady(false);
    setFailed(false);
    setDuration(0);
    setPosition(0);
  }

  function seek(seconds: number) {
    setPosition(seconds);
    if (video.current) video.current.currentTime = seconds;
  }

  async function use() {
    if (!video.current) return;
    setBusy(true);
    try {
      await onUse(video.current);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Sheet title={title} onClose={onCancel}>
      {clips && clips.length === 0 && <p className="mb-3 text-sm text-slate-500 dark:text-slate-400">{empty}</p>}
      {clips && clips.length > 0 && (
        <>
          <div className="mb-3">
            <label htmlFor={selectId} className="mb-1 block text-sm font-medium">
              Clip
            </label>
            <Select id={selectId} value={selected?.value ?? ""} onChange={choose} options={clips} />
          </div>
          <div className="relative grid aspect-video place-items-center overflow-hidden rounded-2xl bg-black text-sm text-slate-300">
            {url && (
              <video
                key={url}
                ref={video}
                data-testid="clip-video"
                src={url}
                crossOrigin={crossOrigin}
                muted
                playsInline
                preload="auto"
                onLoadedMetadata={(e) => setDuration(e.currentTarget.duration || 0)}
                onLoadedData={() => setReady(true)}
                onTimeUpdate={(e) => setPosition(e.currentTarget.currentTime)}
                onError={() => setFailed(true)}
                className="absolute inset-0 size-full object-contain"
              />
            )}
            {failed && <p className="relative px-6 text-center">This clip can't be played</p>}
          </div>
          <input
            type="range"
            aria-label="Position"
            min={0}
            max={duration || 0}
            step={0.1}
            value={position}
            disabled={!duration || failed}
            onChange={(e) => seek(Number(e.target.value))}
            className="mt-3 w-full accent-brand-600"
          />
          <p className="text-right text-xs tabular-nums text-slate-500 dark:text-slate-400">
            {position.toFixed(1)} / {duration.toFixed(1)} s
          </p>
        </>
      )}
      {notice}
      {error && (
        <p role="alert" className="mt-2 text-sm font-medium text-red-600 dark:text-red-400">
          {error}
        </p>
      )}
      <div className="mt-4 grid grid-cols-2 gap-3">
        <button
          type="button"
          onClick={onCancel}
          className="h-12 rounded-xl font-semibold text-slate-700 ring-1 ring-slate-300 transition hover:bg-slate-100 dark:text-slate-200 dark:ring-slate-700 dark:hover:bg-slate-800"
        >
          Cancel
        </button>
        <button type="button" onClick={() => void use()} disabled={!ready || failed || busy} className={PRIMARY}>
          Use this frame
        </button>
      </div>
    </Sheet>
  );
}
