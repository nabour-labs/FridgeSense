import type { AskResult, Config, DoorEvent, Inventory, Pending, Session } from "./types";

/** The session is missing, expired or no longer valid: sign in again. */
export class Unauthorized extends Error {}
/** The demo viewer tried to change something. */
export class ReadOnly extends Error {}
/** FridgeSense could not be reached. */
export class Offline extends Error {}
export class ApiError extends Error {
  /** `message` is the server's `error` text when it sent one. */
  constructor(
    readonly status: number,
    message?: string,
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

  pending(): Promise<{ pending: Pending[] }> {
    return this.request("GET", "/api/pending");
  }

  confirm(id: string, correction?: { item?: string; quantity?: number }): Promise<Inventory> {
    return this.request("POST", `/api/pending/${encodeURIComponent(id)}/confirm`, correction ?? {});
  }

  reject(id: string): Promise<Inventory> {
    return this.request("POST", `/api/pending/${encodeURIComponent(id)}/reject`);
  }

  setQuantity(key: string, quantity: number): Promise<Inventory> {
    return this.request("PUT", `/api/items/${encodeURIComponent(key)}`, { quantity });
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
      throw new ApiError(resp.status, typeof body?.error === "string" ? body.error : undefined);
    }
    return (await resp.json()) as T;
  }
}
