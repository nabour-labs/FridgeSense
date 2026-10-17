import { useEffect, useId, useState } from "react";
import type { Snapshot } from "../api/types";
import { grabFrame, type GrabFrame } from "../image";
import { Select } from "../components/Select";
import { FramePicker } from "../camera/FramePicker";

export { grabFrame };

export interface Clip {
  name: string;
  size: number;
  url: string;
}

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
  return (
    <FramePicker
      title="Snapshot from a clip"
      clips={list && list.clips.map((c) => ({ value: c.url, label: c.name, url: c.url }))}
      empty={NO_CLIPS}
      notice={list?.upload && <p className="mt-2 text-xs font-medium text-warm-800 dark:text-warm-200">{UPLOAD_NOTICE}</p>}
      onUse={async (video) => onPick({ image: await grab(video), captured_at: new Date().toISOString() })}
      onCancel={onCancel}
    />
  );
}
