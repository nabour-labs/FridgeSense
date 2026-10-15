import { useCallback, useRef, useState, type SetStateAction } from "react";
import { useApp } from "./AppContext";
import { usePolling } from "./usePolling";

/**
 * Polls `fetch` and tracks its result. `data` stays null until the first success;
 * `failed` is true while nothing has loaded and the last attempt failed, so a screen
 * can show "No Data" instead of an endless skeleton. Data already shown survives
 * a failed poll. A response is dropped if a newer poll or a local `setData` came
 * after its request started, so older data never replaces newer.
 */
export function useLoad<T>(fetch: () => Promise<T>, intervalMs: number) {
  const { report, online } = useApp();
  const [data, setState] = useState<T | null>(null);
  const [failed, setFailed] = useState(false);
  const generation = useRef(0);

  const load = useCallback(() => {
    const gen = ++generation.current;
    fetch().then(
      (value) => {
        if (gen !== generation.current) return;
        setState(value);
        setFailed(false);
        online();
      },
      (error) => {
        if (gen !== generation.current) return;
        report(error);
        setFailed(true);
      },
    );
  }, [fetch, report, online]);
  usePolling(load, intervalMs);

  const setData = useCallback((value: SetStateAction<T | null>) => {
    generation.current++;
    setState(value);
  }, []);

  return { data, setData, failed };
}
