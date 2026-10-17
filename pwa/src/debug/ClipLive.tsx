import { useState } from "react";
import { Sheet } from "../components/Sheet";
import { ClipSelect, NO_CLIPS, useClips } from "./ClipPicker";

/** Debug: the Livestream dialog playing a local recording on a loop, in place of the camera. */
export function ClipLive({ onClose }: { onClose: () => void }) {
  const list = useClips();
  const [chosen, setChosen] = useState("");
  const url = chosen || list?.clips[0]?.url || "";

  return (
    <Sheet title="Livestream" size="wide" onClose={onClose}>
      {list && list.clips.length > 0 && <ClipSelect clips={list.clips} value={url} onChange={setChosen} />}
      <div className="relative grid aspect-video place-items-center overflow-hidden rounded-2xl bg-black text-sm text-slate-300">
        {url && (
          <video
            key={url}
            data-testid="clip-live"
            src={url}
            autoPlay
            muted
            loop
            playsInline
            className="absolute inset-0 size-full object-contain"
          />
        )}
        {list && list.clips.length === 0 && <p>{NO_CLIPS}</p>}
        <span className="absolute left-2 top-2 rounded-full bg-warm-500/90 px-2.5 py-1 text-xs font-semibold text-white">
          Mock video
        </span>
      </div>
    </Sheet>
  );
}
