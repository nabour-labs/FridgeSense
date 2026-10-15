import type { Api } from "./AppContext";
import type { Inventory } from "./api/types";

export const EMPTY: Inventory = { items: [], pending_count: 0 };

/** A fake API: every method is a vi.fn with harmless defaults; override per test. */
export function fakeApi(overrides: Partial<Record<keyof Api, unknown>> = {}): Api {
  return {
    signIn: vi.fn().mockResolvedValue({ token: "tok", expires_at: "x", role: "owner" }),
    inventory: vi.fn().mockResolvedValue(EMPTY),
    events: vi.fn().mockResolvedValue({ events: [] }),
    pending: vi.fn().mockResolvedValue({ pending: [] }),
    confirm: vi.fn().mockResolvedValue(EMPTY),
    reject: vi.fn().mockResolvedValue(EMPTY),
    setQuantity: vi.fn().mockResolvedValue(EMPTY),
    ask: vi.fn().mockResolvedValue({ intent: "unknown", answer: "Try asking.", data: null }),
    ...overrides,
  } as Api;
}

export function signedIn(role: "owner" | "viewer" = "owner") {
  localStorage.setItem("fridgesense.token", "tok");
  localStorage.setItem("fridgesense.role", role);
}
