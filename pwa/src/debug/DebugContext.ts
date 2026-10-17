import { createContext, useContext } from "react";

/** Debug-mode state screens may read; outside the dev server Mock video is always off. */
export const DebugContext = createContext<{ mockVideo: boolean }>({ mockVideo: false });

export const useDebug = () => useContext(DebugContext);
