import { Maximize2, Minimize2, X } from "lucide-react";
import { useEffect, useId, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

/** A bottom sheet on phones, a centered card on wider screens. */
export function Sheet({
  title,
  onClose,
  size = "default",
  children,
}: {
  title: string;
  onClose: () => void;
  /** "wide" lets the card grow to 768 px on larger screens, for video. */
  size?: "default" | "wide";
  children: ReactNode;
}) {
  const id = useId();
  const [maximized, setMaximized] = useState(false);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  }, [onClose]);

  // Portalled to <body> so an animated ancestor can't become its containing block.
  return createPortal(
    <div className="fixed inset-0 z-30 flex items-end justify-center sm:items-center">
      <button
        aria-label="Close"
        className="absolute inset-0 animate-fade-in bg-slate-950/50 backdrop-blur-sm"
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={id}
        className={`${maximized ? "fixed inset-0 overflow-y-auto pt-[max(1.5rem,env(safe-area-inset-top))]" : `relative w-full ${size === "wide" ? "sm:max-w-3xl" : "max-w-md"} rounded-t-3xl ring-1 ring-slate-200 sm:rounded-3xl dark:ring-slate-800`} animate-sheet-up bg-white p-6 pb-[max(1.5rem,env(safe-area-inset-bottom))] shadow-2xl dark:bg-slate-900`}
      >
        {!maximized && (
          <div
            aria-hidden
            className="mx-auto -mt-3 mb-3 h-1.5 w-10 rounded-full bg-slate-200 sm:hidden dark:bg-slate-700"
          />
        )}
        <div className="mb-4 flex items-center justify-between gap-3">
          <h2 id={id} className="text-lg font-semibold">
            {title}
          </h2>
          <div className="flex items-center">
            <button
              onClick={() => setMaximized((m) => !m)}
              aria-label={maximized ? "Restore" : "Maximize"}
              className="grid size-11 place-items-center rounded-full text-slate-500 transition hover:bg-slate-100 active:scale-95 dark:hover:bg-slate-800"
            >
              {maximized ? (
                <Minimize2 aria-hidden className="size-4" />
              ) : (
                <Maximize2 aria-hidden className="size-4" />
              )}
            </button>
            <button
              onClick={onClose}
              aria-label="Close"
              className="grid size-11 place-items-center rounded-full text-slate-500 transition hover:bg-slate-100 active:scale-95 dark:hover:bg-slate-800"
            >
              <X aria-hidden className="size-5" />
            </button>
          </div>
        </div>
        {children}
      </div>
    </div>,
    document.body,
  );
}
