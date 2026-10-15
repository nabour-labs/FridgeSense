import type { Api } from "./AppContext";
import type { Inventory } from "./api/types";

const DAY = 24 * 3600_000;

export const EMPTY: Inventory = { items: [], pending_count: 0 };

/** A fake API: every method is a vi.fn with harmless defaults; override per test. */
export function fakeApi(overrides: Partial<Record<keyof Api, unknown>> = {}): Api {
  return {
    signIn: vi.fn().mockResolvedValue({ token: "tok", expires_at: new Date(Date.now() + DAY).toISOString(), role: "owner" }),
    inventory: vi.fn().mockResolvedValue(EMPTY),
    events: vi.fn().mockResolvedValue({ events: [] }),
    pending: vi.fn().mockResolvedValue({ pending: [] }),
    confirm: vi.fn().mockResolvedValue(EMPTY),
    reject: vi.fn().mockResolvedValue(EMPTY),
    setQuantity: vi.fn().mockResolvedValue(EMPTY),
    ask: vi.fn().mockResolvedValue({ intent: "unknown", answer: "Try asking.", data: null }),
    config: vi.fn().mockResolvedValue({ instructions: "", references: [] }),
    saveInstructions: vi.fn(),
    addReference: vi.fn(),
    deleteReference: vi.fn(),
    ...overrides,
  } as Api;
}

export function signedIn(role: "owner" | "viewer" = "owner", expiresAt = Date.now() + DAY) {
  localStorage.setItem("fridgesense.token", "tok");
  localStorage.setItem("fridgesense.role", role);
  localStorage.setItem("fridgesense.expires", String(expiresAt));
}
