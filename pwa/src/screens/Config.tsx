import { useEffect, useState } from "react";
import type { Resize } from "../image";
import { toJpeg } from "../image";
import { DoorDetection } from "./DoorDetection";
import { FridgeArea } from "./FridgeArea";
import { ReferenceImages } from "./ReferenceImages";

type Section = "refs" | "doors" | "fridge";

const SECTIONS: { id: Section; label: string; hash: string }[] = [
  { id: "refs", label: "Reference images", hash: "#config" },
  { id: "doors", label: "Open/close detection", hash: "#config/doors" },
  { id: "fridge", label: "Fridge area", hash: "#config/fridge" },
];

function sectionFromHash(): Section {
  return SECTIONS.find((s) => s.hash === location.hash)?.id ?? "refs";
}

/** Config: what guides the item analysis, and how door openings are detected. */
export function Config({ resize = toJpeg }: { resize?: Resize }) {
  const [section, setSection] = useState<Section>(sectionFromHash);

  useEffect(() => {
    const onHash = () => setSection(sectionFromHash());
    addEventListener("hashchange", onHash);
    return () => removeEventListener("hashchange", onHash);
  }, []);

  return (
    <div className="space-y-5">
      <div role="tablist" aria-label="Config" className="grid grid-cols-3 gap-1 rounded-2xl bg-slate-200/70 p-1 dark:bg-slate-800/70">
        {SECTIONS.map((s) => (
          <button
            key={s.id}
            type="button"
            role="tab"
            id={`cfg-tab-${s.id}`}
            aria-selected={section === s.id}
            aria-controls={`cfg-panel-${s.id}`}
            onClick={() => {
              history.replaceState(null, "", s.hash);
              setSection(s.id);
            }}
            className={`min-h-10 rounded-xl px-1 py-1 text-[13px] font-semibold leading-tight tracking-tight transition sm:text-sm ${
              section === s.id
                ? "bg-white text-slate-900 shadow-sm dark:bg-slate-950 dark:text-white"
                : "text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white"
            }`}
          >
            {s.label}
          </button>
        ))}
      </div>
      <div role="tabpanel" id={`cfg-panel-${section}`} aria-labelledby={`cfg-tab-${section}`}>
        {section === "refs" && <ReferenceImages resize={resize} />}
        {section === "doors" && <DoorDetection />}
        {section === "fridge" && <FridgeArea />}
      </div>
    </div>
  );
}
