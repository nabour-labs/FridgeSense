import { useEffect, useState } from "react";
import type { Resize } from "../image";
import { toJpeg } from "../image";
import { isAdmin, useApp } from "../AppContext";
import { Debug } from "./Debug";
import { DoorDetection } from "./DoorDetection";
import { FridgeArea } from "./FridgeArea";
import { ReferenceImages } from "./ReferenceImages";

type Section = "refs" | "doors" | "fridge" | "debug";

const SECTIONS: { id: Section; label: string; hash: string }[] = [
  { id: "refs", label: "Reference images", hash: "#config" },
  { id: "doors", label: "Open/close detection", hash: "#config/doors" },
  { id: "fridge", label: "Fridge area", hash: "#config/fridge" },
  { id: "debug", label: "Debug", hash: "#config/debug" },
];
/** Debug traces hold unblurred stills: the owner's only. */
const OWNER_ONLY: Section[] = ["debug"];

function sectionFromHash(owner: boolean): Section {
  const found =
    SECTIONS.find((s) => s.hash === location.hash)?.id ??
    (location.hash.startsWith("#config/debug/") ? "debug" : "refs");
  return !owner && OWNER_ONLY.includes(found) ? "refs" : found;
}

/** Config: what guides the item analysis, and how door openings are detected. */
export function Config({ resize = toJpeg }: { resize?: Resize }) {
  const owner = isAdmin(useApp().role);
  const sections = SECTIONS.filter((s) => owner || !OWNER_ONLY.includes(s.id));
  const [section, setSection] = useState<Section>(() => sectionFromHash(owner));

  useEffect(() => {
    const onHash = () => setSection(sectionFromHash(owner));
    addEventListener("hashchange", onHash);
    return () => removeEventListener("hashchange", onHash);
  }, [owner]);

  return (
    <div className="space-y-5">
      <div role="tablist" aria-label="Config" className={`grid ${sections.length === 4 ? "grid-cols-4" : "grid-cols-3"} gap-1 rounded-2xl bg-slate-200/70 p-1 dark:bg-slate-800/70`}>
        {sections.map((s) => (
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
        {section === "debug" && <Debug />}
      </div>
    </div>
  );
}
