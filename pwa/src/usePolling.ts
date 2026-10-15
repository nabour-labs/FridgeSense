import { useEffect, useRef } from "react";

/** Calls `fn` now and every `intervalMs` while the page is visible. */
export function usePolling(fn: () => void, intervalMs: number) {
  const latest = useRef(fn);
  latest.current = fn;

  useEffect(() => {
    let timer: ReturnType<typeof setInterval> | undefined;
    const start = () => {
      stop();
      latest.current();
      timer = setInterval(() => latest.current(), intervalMs);
    };
    const stop = () => {
      if (timer !== undefined) clearInterval(timer);
      timer = undefined;
    };
    const onVisibility = () => (document.visibilityState === "visible" ? start() : stop());

    if (document.visibilityState === "visible") start();
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      stop();
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [intervalMs]);
}
