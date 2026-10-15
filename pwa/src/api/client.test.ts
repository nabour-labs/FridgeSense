import { ApiClient, Offline, ReadOnly, Unauthorized } from "./client";

function respond(status: number, body: unknown = {}) {
  return vi.fn().mockResolvedValue(
    new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } }),
  );
}

test("sends the bearer token and parses JSON", async () => {
  const fetch = respond(200, { items: [], pending_count: 0 });
  const api = new ApiClient(() => "tok123", fetch);
  await expect(api.inventory()).resolves.toEqual({ items: [], pending_count: 0 });
  const [url, init] = fetch.mock.calls[0];
  expect(url).toBe("/api/inventory");
  expect(new Headers(init.headers).get("authorization")).toBe("Bearer tok123");
});

test("sends JSON bodies for writes", async () => {
  const fetch = respond(200, { items: [], pending_count: 0 });
  const api = new ApiClient(() => "t", fetch);
  await api.confirm("abc", { item: "Oat Milk", quantity: 2 });
  const [url, init] = fetch.mock.calls[0];
  expect(url).toBe("/api/pending/abc/confirm");
  expect(init.method).toBe("POST");
  expect(JSON.parse(init.body)).toEqual({ item: "Oat Milk", quantity: 2 });
  expect(new Headers(init.headers).get("content-type")).toBe("application/json");
});

test("item keys are URL-encoded", async () => {
  const fetch = respond(200, { items: [], pending_count: 0 });
  await new ApiClient(() => "t", fetch).setQuantity("whole milk", 2);
  expect(fetch.mock.calls[0][0]).toBe("/api/items/whole%20milk");
  expect(fetch.mock.calls[0][1].method).toBe("PUT");
});

test("sign-in sends no token", async () => {
  const fetch = respond(200, { token: "t", expires_at: "x", role: "owner" });
  await new ApiClient(() => null, fetch).signIn("open-sesame");
  const [url, init] = fetch.mock.calls[0];
  expect(url).toBe("/api/session");
  expect(new Headers(init.headers).has("authorization")).toBe(false);
  expect(JSON.parse(init.body)).toEqual({ passcode: "open-sesame" });
});

test("401 becomes Unauthorized", async () => {
  await expect(new ApiClient(() => "t", respond(401)).inventory()).rejects.toBeInstanceOf(
    Unauthorized,
  );
});

test("403 becomes ReadOnly", async () => {
  await expect(new ApiClient(() => "t", respond(403)).reject("x")).rejects.toBeInstanceOf(
    ReadOnly,
  );
});

test("network failure becomes Offline", async () => {
  const fetch = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
  await expect(new ApiClient(() => "t", fetch).events(7)).rejects.toBeInstanceOf(Offline);
});

test("events request carries days", async () => {
  const fetch = respond(200, { events: [] });
  await new ApiClient(() => "t", fetch).events(7);
  expect(fetch.mock.calls[0][0]).toBe("/api/events?days=7");
});
