import type { DoorEvent, Inventory, Pending, Session } from "./types";

/** The session is missing, expired or no longer valid: sign in again. */
export class Unauthorized extends Error {}
/** The demo viewer tried to change something. */
export class ReadOnly extends Error {}
/** FridgeSense could not be reached. */
export class Offline extends Error {}
export class ApiError extends Error {
  constructor(readonly status: number) {
    super(`HTTP ${status}`);
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
    if (!resp.ok) throw new ApiError(resp.status);
    return (await resp.json()) as T;
  }
}
