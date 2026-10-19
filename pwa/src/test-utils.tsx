import { fireEvent, screen } from "@testing-library/react";
import type { Api } from "./AppContext";
import type { Inventory, Role } from "./api/types";

const DAY = 24 * 3600_000;

export const EMPTY: Inventory = { items: [], pending_count: 0 };

/** A fake API: every method is a vi.fn with harmless defaults; override per test. */
export function fakeApi(overrides: Partial<Record<keyof Api, unknown>> = {}): Api {
  return {
    signIn: vi.fn().mockResolvedValue({ token: "tok", expires_at: new Date(Date.now() + DAY).toISOString(), role: "owner" }),
    inventory: vi.fn().mockResolvedValue(EMPTY),
    events: vi.fn().mockResolvedValue({ events: [] }),
    eventsOn: vi.fn().mockResolvedValue({ events: [], next: null }),
    deleteEvent: vi.fn().mockImplementation(async (id: string) => ({ id })),
    pending: vi.fn().mockResolvedValue({ pending: [] }),
    confirm: vi.fn().mockResolvedValue(EMPTY),
    reject: vi.fn().mockResolvedValue(EMPTY),
    setQuantity: vi.fn().mockResolvedValue(EMPTY),
    addItem: vi.fn().mockResolvedValue(EMPTY),
    editItem: vi.fn().mockResolvedValue(EMPTY),
    deleteItem: vi.fn().mockResolvedValue(EMPTY),
    ask: vi.fn().mockResolvedValue({ intent: "unknown", answer: "Try asking.", data: null }),
    config: vi.fn().mockResolvedValue({ instructions: "", references: [] }),
    saveInstructions: vi.fn(),
    addReference: vi.fn(),
    deleteReference: vi.fn(),
    camera: vi.fn().mockReturnValue(new Promise(() => {})),
    setMonitoring: vi.fn(),
    cameraSnapshot: vi.fn(),
    cameraFrame: vi.fn(),
    faceBlur: vi.fn().mockResolvedValue({ enabled: true }),
    setFaceBlur: vi.fn().mockImplementation(async (enabled: boolean) => ({ enabled })),
    startLive: vi.fn().mockReturnValue(new Promise(() => {})),
    stopLive: vi.fn().mockResolvedValue({ ok: true }),
    doorCalibration: vi.fn().mockResolvedValue({
      device_id: "ava1.ring.device.D1",
      zones: [],
      references: [],
      setup: null,
      defaults: { zones: [], threshold: 0.02 },
    }),
    addDoorZone: vi.fn(),
    updateDoorZone: vi.fn(),
    deleteDoorZone: vi.fn(),
    addDoorReference: vi.fn(),
    deleteDoorReference: vi.fn(),
    runDoorSetup: vi.fn(),
    fridgeArea: vi.fn().mockResolvedValue({ device_id: "ava1.ring.device.D1", area: null }),
    saveFridgeArea: vi.fn(),
    warnings: vi.fn().mockResolvedValue({ warnings: [], checked_at: "2026-10-17T12:00:00.000Z" }),
    debugMotions: vi.fn().mockResolvedValue({ motions: [], next: null }),
    debugMotion: vi.fn().mockReturnValue(new Promise(() => {})),
    debugUsage: vi.fn().mockResolvedValue({
      day: "2026-10-20",
      calls: 0,
      input_tokens: 0,
      output_tokens: 0,
      total_tokens: 0,
      usd: 0,
    }),
    ...overrides,
  } as Api;
}

export function signedIn(role: Role = "owner", expiresAt = Date.now() + DAY) {
  localStorage.setItem("fridgesense.token", "tok");
  localStorage.setItem("fridgesense.role", role);
  localStorage.setItem("fridgesense.expires", String(expiresAt));
}

/**
 * Drag across the (first) drawing surface, which is mocked as 400x225 px at (0, 0);
 * `from` and `to` are percent of it.
 */
export function drag(from: [number, number], to: [number, number], index = 0) {
  const el = screen.getAllByTestId("markup-surface")[index];
  el.getBoundingClientRect = () =>
    ({ left: 0, top: 0, width: 400, height: 225, right: 400, bottom: 225, x: 0, y: 0, toJSON() {} }) as DOMRect;
  const at = ([px, py]: [number, number]) => ({ clientX: (px / 100) * 400, clientY: (py / 100) * 225, pointerId: 1 });
  fireEvent.pointerDown(el, at(from));
  fireEvent.pointerMove(el, at(to));
  fireEvent.pointerUp(el, at(to));
}
