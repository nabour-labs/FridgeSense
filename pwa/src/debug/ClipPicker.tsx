import { useEffect, useId, useRef, useState } from "react";
import type { Snapshot } from "../api/types";
import { Select } from "../components/Select";
import { Sheet } from "../components/Sheet";
import { PRIMARY } from "../screens/configStyles";

export interface Clip {
  name: string;
  size: number;
  url: string;
}

/** Same width limit as a camera snapshot from the backend (camera.MAX_WIDTH). */
const MAX_WIDTH = 960;
export const NO_CLIPS = "No clips in the videos folder";
const UPLOAD_NOTICE = "Frames are not face-blurred and will be uploaded if you save them.";

/** The dev server's local recordings, newest first; null while loading. */
export function useClips() {
  const [list, setList] = useState<{ clips: Clip[]; upload: boolean } | null>(null);
  useEffect(() => {
    let live = true;
    fetch("/__dev/videos")
      .then((r) => r.json())
      .then((body) => live && setList(body))
      .catch(() => live && setList({ clips: [], upload: false }));
    return () => {
      live = false;
    };
  }, []);
  return list;
}

/** The clip dropdown shared by the picker and the mocked livestream. */
export function ClipSelect({ clips, value, onChange }: { clips: Clip[]; value: string; onChange: (url: string) => void }) {
  const id = useId();
  return (
    <div className="mb-3">
      <label htmlFor={id} className="mb-1 block text-sm font-medium">
        Clip
      </label>
      <Select id={id} value={value} onChange={onChange} options={clips.map((c) => ({ value: c.url, label: c.name }))} />
    </div>
  );
}

export type GrabFrame = (video: HTMLVideoElement) => Promise<string>;

/** The frame the video shows now, as a base64 JPEG at most 960 px wide. */
export const grabFrame: GrabFrame = async (video) => {
  const scale = Math.min(1, MAX_WIDTH / video.videoWidth);
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(video.videoWidth * scale);
  canvas.height = Math.round(video.videoHeight * scale);
  canvas.getContext("2d")!.drawImage(video, 0, 0, canvas.width, canvas.height);
  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.85));
  if (!blob) throw new Error("frame could not be encoded");
  const url = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
  return url.slice(url.indexOf(",") + 1);
};

/** Debug: pick a frame from a local recording in place of a camera snapshot. */
export function ClipPicker({
  onPick,
  onCancel,
  grab = grabFrame,
}: {
  onPick: (snapshot: Snapshot) => void;
  onCancel: () => void;
  grab?: GrabFrame;
}) {
  const list = useClips();
  const [chosen, setChosen] = useState("");
  const [duration, setDuration] = useState(0);
  const [position, setPosition] = useState(0);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const video = useRef<HTMLVideoElement>(null);

  const url = chosen || list?.clips[0]?.url || "";

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
      onPick({ image: await grab(video.current), captured_at: new Date().toISOString() });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Sheet title="Snapshot from a clip" onClose={onCancel}>
      {list && list.clips.length === 0 && <p className="mb-3 text-sm text-slate-500 dark:text-slate-400">{NO_CLIPS}</p>}
      {list && list.clips.length > 0 && (
        <>
          <ClipSelect clips={list.clips} value={url} onChange={choose} />
          <div className="relative grid aspect-video place-items-center overflow-hidden rounded-2xl bg-black text-sm text-slate-300">
            {url && (
              <video
                key={url}
                ref={video}
                data-testid="clip-video"
                src={url}
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
      {list?.upload && <p className="mt-2 text-xs font-medium text-warm-800 dark:text-warm-200">{UPLOAD_NOTICE}</p>}
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
