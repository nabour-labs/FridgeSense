import { createContext, useContext } from "react";
import type { ApiClient } from "./api/client";
import type { Role } from "./api/types";

export type Api = Pick<
  ApiClient,
  "signIn" | "inventory" | "events" | "pending" | "confirm" | "reject" | "setQuantity"
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

export type Tab = "fridge" | "activity" | "review" | "stats";

export const AppContext = createContext<AppContextValue | null>(null);

export function useApp(): AppContextValue {
  const value = useContext(AppContext);
  if (!value) throw new Error("useApp outside AppContext");
  return value;
}
