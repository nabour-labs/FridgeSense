import type {
  AskResult,
  Box,
  Config,
  DoorEvent,
  DoorSetup,
  DoorStatus,
  EventPage,
  FridgeAreaBody,
  Inventory,
  MotionPage,
  MotionTrace,
  Pending,
  Session,
  Snapshot,
} from "./types";

/** The session is missing, expired or no longer valid: sign in again. */
export class Unauthorized extends Error {}
/** The demo viewer tried to change something. */
export class ReadOnly extends Error {}
/** FridgeSense could not be reached. */
export class Offline extends Error {}
export class ApiError extends Error {
  /** `message` is the server's `error` text when it sent one; `body` is the parsed response. */
  constructor(
    readonly status: number,
    message?: string,
    readonly body: unknown = null,
  ) {
    super(message || `HTTP ${status}`);
  }
}

type Fetch = typeof fetch;

export class ApiClient {
  constructor(
    private readonly token: () => string | null,
    private readonly fetchImpl: Fetch = (...args) => fetch(...args),
  ) {}

  signIn(passcode: string): Promise<Session> {
    return this.request("POST", "/api/session", { passcode }, false);
  }

  inventory(): Promise<Inventory> {
    return this.request("GET", "/api/inventory");
  }

  events(days: number): Promise<{ events: DoorEvent[] }> {
    return this.request("GET", `/api/events?days=${days}`);
  }

  /** Door openings in [from, to), newest first, `limit` at a time; pass `next` back as `cursor`. */
  eventsOn(from: Date, to: Date, limit: number, cursor?: string): Promise<EventPage> {
    const query = new URLSearchParams({ from: from.toISOString(), to: to.toISOString(), limit: String(limit) });
    if (cursor) query.set("cursor", cursor);
    return this.request("GET", `/api/events?${query}`);
  }

  deleteEvent(id: string): Promise<{ id: string }> {
    return this.request("DELETE", `/api/events/${encodeURIComponent(id)}`);
  }

  pending(): Promise<{ pending: Pending[] }> {
    return this.request("GET", "/api/pending");
  }

  confirm(id: string, correction?: { item?: string; quantity?: number }): Promise<Inventory> {
    return this.request("POST", `/api/pending/${encodeURIComponent(id)}/confirm`, correction ?? {});
  }

  reject(id: string): Promise<Inventory> {
    return this.request("POST", `/api/pending/${encodeURIComponent(id)}/reject`);
  }

  addItem(item: { name: string; category: string; quantity: number }): Promise<Inventory> {
    return this.request("POST", "/api/items", item);
  }

  /** Sends `name` and `category` only when given; a new name renames the item. */
  editItem(key: string, changes: { quantity: number; name?: string; category?: string }): Promise<Inventory> {
    return this.request("PUT", `/api/items/${encodeURIComponent(key)}`, changes);
  }

  deleteItem(key: string): Promise<Inventory> {
    return this.request("DELETE", `/api/items/${encodeURIComponent(key)}`);
  }

  setQuantity(key: string, quantity: number): Promise<Inventory> {
    return this.editItem(key, { quantity });
  }

  ask(question: string): Promise<AskResult> {
    return this.request("POST", "/api/ask", { question });
  }

  config(): Promise<Config> {
    return this.request("GET", "/api/config");
  }

  saveInstructions(instructions: string): Promise<Config> {
    return this.request("PUT", "/api/config/instructions", { instructions });
  }

  /** `image` is a base64 JPEG. */
  addReference(annotation: string, image: string): Promise<Config> {
    return this.request("POST", "/api/config/references", { annotation, image });
  }

  deleteReference(id: string): Promise<Config> {
    return this.request("DELETE", `/api/config/references/${encodeURIComponent(id)}`);
  }

  /** A face-blurred still from the camera, not stored. */
  cameraSnapshot(): Promise<Snapshot> {
    return this.request("POST", "/api/camera/snapshot");
  }

  doorCalibration(): Promise<DoorSetup> {
    return this.request("GET", "/api/door-calibration");
  }

  /** `image` is a base64 JPEG; `box` is in fractions of it. */
  addDoorReference(image: string, box: Box, status: DoorStatus): Promise<DoorSetup> {
    return this.request("POST", "/api/door-calibration/references", { image, box, status });
  }

  deleteDoorReference(id: string): Promise<DoorSetup> {
    return this.request("DELETE", `/api/door-calibration/references/${encodeURIComponent(id)}`);
  }

  /** Works out each zone's rule; a 422 ApiError carries `references` with scores in `body`. */
  runDoorSetup(): Promise<DoorSetup> {
    return this.request("POST", "/api/door-calibration/run");
  }

  fridgeArea(): Promise<FridgeAreaBody> {
    return this.request("GET", "/api/fridge-area");
  }

  /** Replaces the fridge area. `image` is a base64 JPEG; `box` is in fractions of it. */
  saveFridgeArea(image: string, box: Box): Promise<FridgeAreaBody> {
    return this.request("PUT", "/api/fridge-area", { image, box });
  }

  /** Traced motions in [from, to), newest first, `limit` at a time (owner only). */
  debugMotions(from: Date, to: Date, limit: number, cursor?: string): Promise<MotionPage> {
    const query = new URLSearchParams({ from: from.toISOString(), to: to.toISOString(), limit: String(limit) });
    if (cursor) query.set("cursor", cursor);
    return this.request("GET", `/api/debug/motions?${query}`);
  }

  /** One motion's trace, by motion id or door event id (owner only). */
  debugMotion(id: string): Promise<MotionTrace> {
    return this.request("GET", `/api/debug/motions/${encodeURIComponent(id)}`);
  }

  private async request<T>(method: string, path: string, body?: unknown, auth = true): Promise<T> {
    const headers = new Headers();
    if (body !== undefined) headers.set("content-type", "application/json");
    const token = auth ? this.token() : null;
    if (token) headers.set("authorization", `Bearer ${token}`);
    let resp: Response;
    try {
      resp = await this.fetchImpl(path, {
        method,
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch {
      throw new Offline("FridgeSense can't be reached");
    }
    if (resp.status === 401) throw new Unauthorized();
    if (resp.status === 403) throw new ReadOnly();
    if (!resp.ok) {
      const body = await resp.json().catch(() => null);
      throw new ApiError(resp.status, typeof body?.error === "string" ? body.error : undefined, body);
    }
    return (await resp.json()) as T;
  }
}
