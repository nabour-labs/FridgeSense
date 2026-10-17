import { useEffect, useState } from "react";
import { ApiError } from "../api/client";
import type { Snapshot } from "../api/types";
import type { Api } from "../AppContext";
import { clock, dayLabel } from "../format";
import { grabFrame, type GrabFrame } from "../image";
import { FramePicker, type PickableClip } from "./FramePicker";

export const NO_RECENT_CLIPS = "No door openings with a clip in the last 7 days.";
const CANT_GRAB = "This frame can't be used. Try another clip.";
const CANT_BLUR = "Faces couldn't be blurred, so this frame can't be used.";

/**
 * Pick a frame from a recent door opening's clip. The frame is sent to `cameraFrame` to blur any
 * faces, and only the blurred image reaches `onPick`.
 */
export function RecentClipPicker({
  api,
  onPick,
  onCancel,
  report,
  grab = grabFrame,
}: {
  api: Pick<Api, "events" | "cameraFrame">;
  onPick: (snapshot: Snapshot) => void;
  onCancel: () => void;
  report: (err: unknown) => void;
  grab?: GrabFrame;
}) {
  const [clips, setClips] = useState<PickableClip[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    api.events(7).then(
      ({ events }) =>
        live &&
        setClips(
          events
            .filter((e) => e.clip)
            .sort((a, b) => b.opened_at.localeCompare(a.opened_at))
            .map((e) => ({
              value: e.id,
              label: `${dayLabel(e.opened_at)} ${clock(e.opened_at)} · ${e.duration_s} s`,
              url: e.clip!,
            })),
        ),
      (err) => {
        if (!live) return;
        setClips([]);
        report(err);
      },
    );
    return () => {
      live = false;
    };
  }, [api, report]);

  async function use(video: HTMLVideoElement) {
    setError(null);
    let frame: string;
    try {
      frame = await grab(video);
    } catch {
      setError(CANT_GRAB);
      return;
    }
    try {
      onPick(await api.cameraFrame(frame));
    } catch (err) {
      if (err instanceof ApiError && err.status === 502) setError(CANT_BLUR);
      else report(err);
    }
  }

  return (
    <FramePicker
      title="Snapshot from a recent clip"
      clips={clips}
      empty={NO_RECENT_CLIPS}
      error={error}
      crossOrigin="anonymous"
      onUse={use}
      onCancel={onCancel}
    />
  );
}
