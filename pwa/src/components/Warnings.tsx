import { TriangleAlert } from "lucide-react";
import { useEffect, useState } from "react";
import type { SetupWarning } from "../api/types";
import { isAdmin, useApp } from "../AppContext";

type Fix = { label: string; href: string };

function fixes(w: SetupWarning): Fix[] {
  switch (w.code) {
    case "needs_relink":
      return []; // re-linking happens in the Ring app
    case "monitoring_paused":
      return [{ label: "Resume on Camera tab", href: "#config" }];
    case "motion_detection_off":
      return [{ label: "Open Camera", href: "#config" }];
    case "door_setup_missing":
      return [{ label: "Set up detection", href: "#config/doors" }];
    case "door_setup_mismatch":
      return [{ label: "Update door references", href: "#config/doors" }];
    case "privacy_mask_changed":
      return [{ label: "Update door zones", href: "#config/doors" }];
    case "camera_moved":
      return w.update.map((u) =>
        u === "door_references"
          ? { label: "Update door references", href: "#config/doors" }
          : { label: "Update fridge area", href: "#config/fridge" },
      );
  }
}

/**
 * Setup problems that stop door openings being recorded or detected well, each with a link
 * to its fix. Owner only: other roles can't make the fixes, so they see nothing and nothing is
 * requested. Loaded once per visit; a failed request shows nothing, since these are hints.
 */
export function Warnings() {
  const { api, role } = useApp();
  const owner = isAdmin(role);
  const [warnings, setWarnings] = useState<SetupWarning[]>([]);

  useEffect(() => {
    if (!owner) return;
    let live = true;
    api.warnings().then(
      (body) => live && setWarnings(body.warnings),
      () => {},
    );
    return () => {
      live = false;
    };
  }, [api, owner]);

  if (!owner || warnings.length === 0) return null;
  return (
    <div className="space-y-2">
      {warnings.map((w) => (
        <div
          key={w.code}
          role="alert"
          className="flex gap-3 rounded-2xl bg-amber-50 p-3 text-sm text-amber-900 ring-1 ring-amber-200 dark:bg-amber-950/60 dark:text-amber-100 dark:ring-amber-900"
        >
          <TriangleAlert aria-hidden className="mt-0.5 size-5 shrink-0 text-amber-600 dark:text-amber-300" />
          <div className="min-w-0 space-y-1.5">
            <p>{w.message}</p>
            <p className="flex flex-wrap gap-x-4 gap-y-1">
              {fixes(w).map((f) => (
                <a key={f.href} href={f.href} className="font-semibold underline underline-offset-2">
                  {f.label}
                </a>
              ))}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}
