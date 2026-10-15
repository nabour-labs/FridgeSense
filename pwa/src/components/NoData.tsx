import { DatabaseZap } from "lucide-react";
import { EmptyState } from "./EmptyState";

/** Shown in place of a skeleton when a screen's data could not be loaded. */
export function NoData() {
  return <EmptyState Icon={DatabaseZap} title="No Data" />;
}
