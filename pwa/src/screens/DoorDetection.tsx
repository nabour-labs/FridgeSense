import { useCallback } from "react";
import { useApp } from "../AppContext";
import { NoData } from "../components/NoData";
import { useLoad } from "../useLoad";

/** Door references (open/closed snapshots with a box) and the setup that tunes detection. */
export function DoorDetection() {
  const { api } = useApp();
  const { data, failed } = useLoad(
    useCallback(() => api.doorCalibration(), [api]),
    60_000,
  );
  if (!data) {
    if (failed) return <NoData />;
    return <div aria-hidden data-testid="loading" className="h-64 animate-pulse rounded-3xl bg-slate-200/70 dark:bg-slate-800" />;
  }
  return <section aria-label="Door references" />;
}
