import { ApiClient, ApiError, Offline, ReadOnly, Unauthorized } from "./client";

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

test("ask posts the question", async () => {
  const fetch = respond(200, {
    intent: "agent",
    answer: "Yes.",
    data: { tools: ["find_item"] },
    source: "agent",
    audio: "SUQz",
  });
  const result = await new ApiClient(() => "tok", fetch).ask("do I have milk?");
  expect(result).toEqual({
    intent: "agent",
    answer: "Yes.",
    data: { tools: ["find_item"] },
    source: "agent",
    audio: "SUQz",
  });
  const [url, init] = fetch.mock.calls[0];
  expect(url).toBe("/api/ask");
  expect(init.method).toBe("POST");
  expect(JSON.parse(init.body)).toEqual({ question: "do I have milk?" });
  expect(new Headers(init.headers).get("authorization")).toBe("Bearer tok");
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

test("eventsOn asks for one range and page", async () => {
  const page = () => respond(200, { events: [], next: null });
  const from = new Date("2026-10-15T04:00:00.000Z");
  const to = new Date("2026-10-16T04:00:00.000Z");
  const first = page();
  await new ApiClient(() => "t", first).eventsOn(from, to, 10);
  expect(first.mock.calls[0][0]).toBe(
    "/api/events?from=2026-10-15T04%3A00%3A00.000Z&to=2026-10-16T04%3A00%3A00.000Z&limit=10",
  );
  const second = page();
  await new ApiClient(() => "t", second).eventsOn(from, to, 10, "ab/c");
  expect(second.mock.calls[0][0]).toBe(
    "/api/events?from=2026-10-15T04%3A00%3A00.000Z&to=2026-10-16T04%3A00%3A00.000Z&limit=10&cursor=ab%2Fc",
  );
});

test("deleteEvent sends DELETE with the token", async () => {
  const fetch = respond(200, { id: "e/1" });
  await new ApiClient(() => "t", fetch).deleteEvent("e/1");
  const [path, init] = fetch.mock.calls[0];
  expect(path).toBe("/api/events/e%2F1");
  expect(init.method).toBe("DELETE");
  expect(new Headers(init.headers).get("authorization")).toBe("Bearer t");
});

const CONFIG = { instructions: "", references: [] };

test.each([
  ["config", (api: ApiClient) => api.config(), "GET", "/api/config", undefined],
  [
    "saveInstructions",
    (api: ApiClient) => api.saveInstructions("Count yogurt cups individually."),
    "PUT",
    "/api/config/instructions",
    { instructions: "Count yogurt cups individually." },
  ],
  [
    "addReference",
    (api: ApiClient) => api.addReference("soda can", "/9j/AAA="),
    "POST",
    "/api/config/references",
    { annotation: "soda can", image: "/9j/AAA=" },
  ],
  ["deleteReference", (api: ApiClient) => api.deleteReference("UkVGIzE="), "DELETE", "/api/config/references/UkVGIzE%3D", undefined],
])("%s sends the right request", async (_, callApi, method, path, body) => {
  const fetch = respond(200, CONFIG);
  await expect(callApi(new ApiClient(() => "t", fetch))).resolves.toEqual(CONFIG);
  const [url, init] = fetch.mock.calls[0];
  expect(url).toBe(path);
  expect(init.method).toBe(method);
  expect(init.body === undefined ? undefined : JSON.parse(init.body)).toEqual(body);
});

test("ApiError carries the server's error text", async () => {
  const api = new ApiClient(() => "t", respond(409, { error: "at most 6 reference images" }));
  const err = await api.addReference("x", "y").catch((e) => e);
  expect(err).toBeInstanceOf(ApiError);
  expect(err.status).toBe(409);
  expect(err.message).toBe("at most 6 reference images");
});

test("ApiError falls back to the status when the body has no error text", async () => {
  const fetch = vi.fn().mockResolvedValue(new Response("oops", { status: 500 }));
  const err = await new ApiClient(() => "t", fetch).inventory().catch((e) => e);
  expect(err).toBeInstanceOf(ApiError);
  expect(err.message).toBe("HTTP 500");
});

const INVENTORY = { items: [], pending_count: 0 };

test.each([
  [
    "addItem",
    (api: ApiClient) => api.addItem({ name: "Butter", category: "dairy", quantity: 2 }),
    "POST",
    "/api/items",
    { name: "Butter", category: "dairy", quantity: 2 },
  ],
  [
    "editItem with every field",
    (api: ApiClient) => api.editItem("bottle", { quantity: 1, name: "Oat Milk", category: "dairy" }),
    "PUT",
    "/api/items/bottle",
    { quantity: 1, name: "Oat Milk", category: "dairy" },
  ],
  [
    "editItem with only the quantity",
    (api: ApiClient) => api.editItem("oat milk", { quantity: 3 }),
    "PUT",
    "/api/items/oat%20milk",
    { quantity: 3 },
  ],
  ["deleteItem", (api: ApiClient) => api.deleteItem("mystery jar"), "DELETE", "/api/items/mystery%20jar", undefined],
])("%s sends the right request", async (_, callApi, method, path, body) => {
  const fetch = respond(200, INVENTORY);
  await expect(callApi(new ApiClient(() => "t", fetch))).resolves.toEqual(INVENTORY);
  const [url, init] = fetch.mock.calls[0];
  expect(url).toBe(path);
  expect(init.method).toBe(method);
  expect(init.body === undefined ? undefined : JSON.parse(init.body)).toEqual(body);
});

const BOX = { x: 0.38, y: 0.32, width: 0.21, height: 0.3 };

test.each([
  ["camera", (api: ApiClient) => api.camera(), "GET", "/api/camera", undefined],
  ["cameraSnapshot", (api: ApiClient) => api.cameraSnapshot(), "POST", "/api/camera/snapshot", undefined],
  ["cameraFrame", (api: ApiClient) => api.cameraFrame("/9j/FRAME"), "POST", "/api/camera/frame", { image: "/9j/FRAME" }],
  ["faceBlur", (api: ApiClient) => api.faceBlur(), "GET", "/api/settings/face-blur", undefined],
  ["setFaceBlur", (api: ApiClient) => api.setFaceBlur(false), "PUT", "/api/settings/face-blur", { enabled: false }],
  ["doorCalibration", (api: ApiClient) => api.doorCalibration(), "GET", "/api/door-calibration", undefined],
  [
    "addDoorZone",
    (api: ApiClient) => api.addDoorZone("Freezer drawer", BOX),
    "POST",
    "/api/door-calibration/zones",
    { name: "Freezer drawer", box: BOX },
  ],
  [
    "updateDoorZone",
    (api: ApiClient) => api.updateDoorZone("Wk/1", { name: "Doors", box: BOX }),
    "PATCH",
    "/api/door-calibration/zones/Wk%2F1",
    { name: "Doors", box: BOX },
  ],
  [
    "deleteDoorZone",
    (api: ApiClient) => api.deleteDoorZone("Wk/1"),
    "DELETE",
    "/api/door-calibration/zones/Wk%2F1",
    undefined,
  ],
  [
    "addDoorReference",
    (api: ApiClient) => api.addDoorReference("/9j/SNAP", "Wk/1", "open"),
    "POST",
    "/api/door-calibration/references",
    { image: "/9j/SNAP", zone_id: "Wk/1", status: "open" },
  ],
  [
    "deleteDoorReference",
    (api: ApiClient) => api.deleteDoorReference("RE9PUlJFRiM/a"),
    "DELETE",
    "/api/door-calibration/references/RE9PUlJFRiM%2Fa",
    undefined,
  ],
  ["runDoorSetup", (api: ApiClient) => api.runDoorSetup(), "POST", "/api/door-calibration/run", undefined],
  ["startLive", (api: ApiClient) => api.startLive("v=0\r\n"), "POST", "/api/camera/live", { offer: "v=0\r\n" }],
  ["stopLive", (api: ApiClient) => api.stopLive("S/1"), "DELETE", "/api/camera/live/S%2F1", undefined],
  ["fridgeArea", (api: ApiClient) => api.fridgeArea(), "GET", "/api/fridge-area", undefined],
  ["warnings", (api: ApiClient) => api.warnings(), "GET", "/api/warnings", undefined],
  [
    "saveFridgeArea",
    (api: ApiClient) => api.saveFridgeArea("/9j/SNAP", BOX),
    "PUT",
    "/api/fridge-area",
    { image: "/9j/SNAP", box: BOX },
  ],
])("%s sends the right request", async (_, callApi, method, path, body) => {
  const fetch = respond(200, { ok: true });
  await expect(callApi(new ApiClient(() => "t", fetch))).resolves.toEqual({ ok: true });
  const [url, init] = fetch.mock.calls[0];
  expect(url).toBe(path);
  expect(init.method).toBe(method);
  expect(init.body === undefined ? undefined : JSON.parse(init.body)).toEqual(body);
});

test("an API error keeps the response body", async () => {
  const body = { error: "zone 1: open and closed references overlap", references: [{ id: "a", score: 0.05 }] };
  const err = await new ApiClient(() => "t", respond(422, body)).runDoorSetup().catch((e) => e);
  expect(err).toBeInstanceOf(ApiError);
  expect(err.status).toBe(422);
  expect(err.message).toBe("zone 1: open and closed references overlap");
  expect(err.body).toEqual(body);
});

test("debug motions are listed by day and page", async () => {
  const fetch = vi.fn().mockImplementation(async () => new Response(JSON.stringify({ motions: [], next: null })));
  const api = new ApiClient(() => "t", fetch);
  const from = new Date("2026-10-16T04:00:00.000Z");
  const to = new Date("2026-10-17T04:00:00.000Z");
  await api.debugMotions(from, to, 10, "abc");
  const url = new URL(fetch.mock.calls[0][0], "http://x");
  expect(url.pathname).toBe("/api/debug/motions");
  expect(Object.fromEntries(url.searchParams)).toEqual({
    from: "2026-10-16T04:00:00.000Z",
    to: "2026-10-17T04:00:00.000Z",
    limit: "10",
    cursor: "abc",
  });
  await api.debugMotions(from, to, 10);
  expect(new URL(fetch.mock.calls[1][0], "http://x").searchParams.has("cursor")).toBe(false);
});

test("one debug motion is read by id", async () => {
  const fetch = respond(200, { id: "a/b" });
  await new ApiClient(() => "t", fetch).debugMotion("a/b");
  expect(fetch.mock.calls[0][0]).toBe("/api/debug/motions/a%2Fb");
  expect(fetch.mock.calls[0][1].method).toBe("GET");
});

test("setMonitoring sends the paused state", async () => {
  const fetch = respond(200, { paused: true, since: "2026-10-18T14:05:00.000Z" });
  const result = await new ApiClient(() => "t", fetch).setMonitoring(true);
  expect(result).toEqual({ paused: true, since: "2026-10-18T14:05:00.000Z" });
  const [url, init] = fetch.mock.calls[0];
  expect(url).toBe("/api/camera/monitoring");
  expect(init.method).toBe("PUT");
  expect(JSON.parse(init.body)).toEqual({ paused: true });
});
