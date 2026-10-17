import { Bug } from "lucide-react";

/** Dev-server only: the Mock video switch, under the header. */
export function DebugBar({ mockVideo, onChange }: { mockVideo: boolean; onChange: (on: boolean) => void }) {
  return (
    <section
      aria-label="Debug"
      className="mx-4 mb-3 flex items-center justify-between gap-3 rounded-xl bg-warm-50 px-3 py-1.5 text-xs font-semibold text-warm-800 ring-1 ring-warm-200 dark:bg-warm-950/50 dark:text-warm-200 dark:ring-warm-900"
    >
      <span className="flex items-center gap-1.5">
        <Bug aria-hidden className="size-3.5" />
        Debug
      </span>
      <label className="flex cursor-pointer items-center gap-2">
        Mock video
        <button
          type="button"
          role="switch"
          aria-checked={mockVideo}
          aria-label="Mock video"
          onClick={() => onChange(!mockVideo)}
          className={`relative h-6 w-10 rounded-full transition-colors ${
            mockVideo ? "bg-warm-500" : "bg-slate-300 dark:bg-slate-700"
          }`}
        >
          <span
            aria-hidden
            className={`absolute top-0.5 size-5 rounded-full bg-white shadow transition-[left] ${mockVideo ? "left-[1.125rem]" : "left-0.5"}`}
          />
        </button>
      </label>
    </section>
  );
}
