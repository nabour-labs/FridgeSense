import { createContext, useContext } from "react";
import type { ApiClient } from "./api/client";
import type { Role } from "./api/types";

export type Api = Pick<
  ApiClient,
  | "signIn"
  | "inventory"
  | "events"
  | "eventsOn"
  | "deleteEvent"
  | "pending"
  | "confirm"
  | "reject"
  | "setQuantity"
  | "addItem"
  | "editItem"
  | "deleteItem"
  | "ask"
  | "config"
  | "saveInstructions"
  | "addReference"
  | "deleteReference"
  | "camera"
  | "cameraSnapshot"
  | "startLive"
  | "stopLive"
  | "doorCalibration"
  | "addDoorReference"
  | "deleteDoorReference"
  | "runDoorSetup"
  | "fridgeArea"
  | "saveFridgeArea"
  | "debugMotions"
  | "debugMotion"
>;

export interface AppContextValue {
  api: Api;
  role: Role;
  /** Hand any API error to the shell: sign-out, offline banner or read-only notice. */
  report: (error: unknown) => void;
  /** A request succeeded: clear the offline banner. */
  online: () => void;
  go: (tab: Tab) => void;
}

export type Tab = "fridge" | "activity" | "review" | "stats" | "ask" | "config";

/** Everyone but the read-only demo viewer may change things. */
export const canEdit = (role: Role) => role !== "viewer";

/** Only the owner (admin) sees Debug: traces hold unblurred stills. */
export const isAdmin = (role: Role) => role === "owner";

export const AppContext = createContext<AppContextValue | null>(null);

export function useApp(): AppContextValue {
  const value = useContext(AppContext);
  if (!value) throw new Error("useApp outside AppContext");
  return value;
}
