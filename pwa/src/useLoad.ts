import { useCallback, useState } from "react";
import { useApp } from "./AppContext";
import { usePolling } from "./usePolling";

/**
 * Polls `fetch` and tracks its result. `data` stays null until the first success;
 * `failed` is true while nothing has loaded and the last attempt failed, so a screen
 * can show "No Data" instead of an endless skeleton. Data already shown survives
 * a failed poll.
 */
export function useLoad<T>(fetch: () => Promise<T>, intervalMs: number) {
  const { report, online } = useApp();
  const [data, setData] = useState<T | null>(null);
  const [failed, setFailed] = useState(false);

  const load = useCallback(() => {
    fetch().then(
      (value) => {
        setData(value);
        setFailed(false);
        online();
      },
      (error) => {
        report(error);
        setFailed(true);
      },
    );
  }, [fetch, report, online]);
  usePolling(load, intervalMs);

  return { data, setData, failed };
}
