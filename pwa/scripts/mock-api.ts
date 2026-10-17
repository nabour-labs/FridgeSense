import { readFileSync } from "node:fs";
import type { Plugin } from "vite";

/** Dev-only fake /api for layout work without a deployed backend: FRIDGESENSE_MOCK=1 npm run dev */
export function mockApi(): Plugin {
  const now = Date.now();
  const iso = (msAgo: number) => new Date(now - msAgo).toISOString();
  const MIN = 60_000;
  const HOUR = 60 * MIN;
  let items = [
    ["milk", "Milk", "dairy", 1, 2 * MIN],
    ["eggs", "Eggs", "dairy", 10, 3 * HOUR],
    ["greek yogurt", "Greek yogurt", "dairy", 4, 26 * HOUR],
    ["cheddar cheese", "Cheddar cheese", "dairy", 1, 3 * 24 * HOUR],
    ["butter", "Butter", "dairy", 1, 6 * 24 * HOUR],
    ["apple", "Apple", "produce", 5, 5 * HOUR],
    ["baby spinach", "Baby spinach", "produce", 1, 30 * HOUR],
    ["strawberries", "Strawberries", "produce", 1, 8 * HOUR],
    ["bell pepper", "Bell pepper", "produce", 3, 2 * 24 * HOUR],
    ["chicken breast", "Chicken breast", "meat", 2, 22 * HOUR],
    ["salmon fillet", "Salmon fillet", "seafood", 1, 28 * HOUR],
    ["soda can", "Soda can", "beverage", 0, 50 * MIN],
    ["orange juice", "Orange juice", "beverage", 1, 2 * 24 * HOUR],
    ["sparkling water", "Sparkling water", "beverage", 6, 4 * 24 * HOUR],
    ["hummus", "Hummus", "snack", 1, 3 * 24 * HOUR],
    ["ketchup", "Ketchup", "condiment", 1, 12 * 24 * HOUR],
    ["leftover pasta", "Leftover pasta", "leftovers", 2, 20 * HOUR],
    ["sourdough loaf", "Sourdough loaf", "bakery", 1, 9 * HOUR],
  ].map(([key, name, category, quantity, ago]) => ({
    key, name, category, quantity, last_changed_at: iso(ago as number),
  }));
  // Drawn stand-ins for reference photos, so the Config grid has something to show.
  const photo = (name: string) => readFileSync(new URL(`./mock/${name}.jpg`, import.meta.url)).toString("base64");
  let config: {
    instructions: string;
    references: { id: string; annotation: string; image: string; created_at: string }[];
  } = {
    instructions: "Count yogurt cups individually.",
    references: [
      { id: "ref1", annotation: "milk bag (2 L, white with blue print)", image: photo("ref-milk-bag"), created_at: iso(3 * 24 * HOUR) },
      { id: "ref2", annotation: "Greek yogurt cups, one per lid colour", image: photo("ref-yogurt-cups"), created_at: iso(2 * 24 * HOUR) },
    ],
  };
  let pending = [
    { id: "p1", door_event_id: "e1", item: "chocolate bar", category: "snack", direction: "removed",
      quantity: 1, confidence: 0.62, opened_at: iso(50 * MIN) },
    { id: "p2", door_event_id: "e2", item: "bottle", category: "beverage", direction: "added",
      quantity: 1, confidence: 0.48, opened_at: iso(5 * HOUR) },
  ];
  const grabs = [
    { item: "sparkling water", category: "beverage", direction: "removed", quantity: 1, confidence: 0.93 },
    { item: "strawberries", category: "produce", direction: "added", quantity: 1, confidence: 0.9 },
    null,
    { item: "hummus", category: "snack", direction: "removed", quantity: 1, confidence: 0.86 },
    { item: "greek yogurt", category: "dairy", direction: "removed", quantity: 1, confidence: 0.92 },
    null,
    { item: "sourdough loaf", category: "bakery", direction: "added", quantity: 1, confidence: 0.89 },
    { item: "orange juice", category: "beverage", direction: "removed", quantity: 1, confidence: 0.84 },
  ];
  const stills = [1, 2, 3, 4].map((n) => `/mock/still-${n}.svg`);
  let events = [
    { id: "e0", opened_at: iso(2 * MIN), duration_s: 18, status: "done", pending_count: 0, stills,
      changes: [{ item: "milk", category: "dairy", direction: "added", quantity: 1, confidence: 0.94, applied: true }] },
    { id: "e1", opened_at: iso(50 * MIN), duration_s: 31, status: "done", pending_count: 1, stills,
      changes: [
        { item: "soda can", category: "beverage", direction: "removed", quantity: 1, confidence: 0.88, applied: true },
        { item: "chocolate bar", category: "snack", direction: "removed", quantity: 1, confidence: 0.62, applied: false },
      ] },
    { id: "e2", opened_at: iso(5 * HOUR), duration_s: 44, status: "done", pending_count: 1, stills: [],
      changes: [
        { item: "apple", category: "produce", direction: "added", quantity: 5, confidence: 0.91, applied: true },
        { item: "eggs", category: "dairy", direction: "removed", quantity: 2, confidence: 0.79, applied: true },
      ] },
    { id: "e3", opened_at: iso(9 * HOUR), duration_s: 12, status: "analysis_failed", pending_count: 0, stills: [], changes: [] },
    // Quick grabs, so today runs past one page of 10.
    ...Array.from({ length: 8 }, (_, i) => ({
      id: `grab${i}`, opened_at: iso((8 + i * 4) * MIN), duration_s: 6 + i, status: "done", pending_count: 0,
      stills: i % 3 === 0 ? stills : [], changes: grabs[i] ? [{ ...grabs[i], applied: true }] : [],
    })),
    ...habit(),
  ];
  // Four weeks of meal-time openings (busier at weekends) so the Stats heatmap has a pattern.
  function habit() {
    const out: { id: string; opened_at: string; duration_s: number; status: string; pending_count: number; stills: string[]; changes: never[] }[] = [];
    const day0 = new Date(now);
    day0.setHours(0, 0, 0, 0);
    for (let d = 1; d < 28; d++) {
      const day = new Date(day0.getTime() - d * 24 * HOUR);
      const weekend = day.getDay() === 0 || day.getDay() === 6;
      const hours = weekend ? [9, 10, 12, 13, 15, 18, 19, 19, 21] : [7, 7, 12, 17, 18, 18, 19, 22];
      hours.forEach((h, i) => {
        if ((d * 7 + i * 3) % 5 === 0) return; // skip some for texture
        out.push({
          id: `old${d}-${i}`, opened_at: new Date(day.getTime() + h * HOUR + ((d * 13 + i * 7) % 50) * MIN).toISOString(),
          duration_s: 15 + ((d * 7 + i) % 30), status: "done", pending_count: 0, stills: [], changes: [],
        });
      });
    }
    return out;
  }
  type DoorRef = { id: string; image: string; box: { x: number; y: number; width: number; height: number }; status: "open" | "closed"; created_at: string };
  let doorRefs: DoorRef[] = [];
  let doorSetup: { zones: Record<string, unknown>[]; ran_at: string } | null = null;
  let refsChangedAt = 0;
  let snapshots = 0;
  let fridgeArea: { image: string; box: unknown; updated_at: string } | null = null;
  const doorBody = (scored = false) => ({
    device_id: "mock.device.D1",
    references: doorRefs.map((r) => ({ ...r, score: doorSetup || scored ? (r.status === "open" ? 0.12 : 0.003) : null })),
    setup: doorSetup && { ...doorSetup, stale: refsChangedAt > Date.parse(doorSetup.ran_at), tuned_at: null, tuned_from: null },
    alignment: doorSetup && {
      dx: 0.016, dy: 0, error: 0.031, failures: 0, moved: false, moved_at: null, last_moved_at: null, checked_at: iso(5 * MIN),
    },
    defaults: { zones: [{ x: 0.38, y: 0.32, width: 0.21, height: 0.3 }, { x: 0.455, y: 0.6, width: 0.12, height: 0.18 }], threshold: 0.02 },
  });
  // Two traced motions for the Debug tab: the milk opening (e0) and a walk-past.
  function debugTraces() {
    const zone = { x: 0.38, y: 0.32, width: 0.21, height: 0.3 };
    const scores = (open: boolean, n: number) => [
      { zone: 1, value: open ? 0.14 + n * 0.01 : 0.004 + n * 0.0005, threshold: 0.11, open },
    ];
    const opened = [3, 4, 5];
    const doorStills = Array.from({ length: 8 }, (_, i) => {
      const n = i + 1, open = opened.includes(n);
      return {
        n, at_ms: now - 2 * MIN + n * 2000, missing_status: n === 7 ? 416 : null,
        url: n === 7 ? null : open ? `/mock/still-${n - 2}.svg` : "/mock/closed.svg",
        zones: n === 7 ? [] : scores(open, n), best_zone: n === 7 ? null : 1, open: n === 7 ? null : open,
      };
    });
    const rule = {
      source: "setup", ran_at: iso(26 * HOUR),
      zones: [{ zone: 1, box: zone, feature: "change", direction: "above", threshold: 0.11, margin: 0.07, baseline_url: "/mock/closed.svg" }],
      references: [
        { id: "r1", status: "closed", box: zone, created_at: iso(27 * HOUR), url: "/mock/closed.svg" },
        { id: "r2", status: "open", box: zone, created_at: iso(27 * HOUR), url: "/mock/still-1.svg" },
      ],
    };
    const content = (n: number) => [
      { type: "text", text: "Reference photos of items in this fridge, with what each one is:" },
      { type: "text", text: "Reference 1: milk bag (2 L, white with blue print)" },
      { type: "image", role: "reference", n: 1, url: `data:image/jpeg;base64,${photo("ref-milk-bag")}` },
      { type: "cache_point" },
      ...[1, 2, 3].flatMap((k) => [
        { type: "text", text: `Image ${k} of ${n}` },
        { type: "image", role: "still", n: k, url: `/mock/still-${k}.svg` },
      ]),
      { type: "cache_point" },
      { type: "text", text: "Compare the images... Current inventory: [eggs, milk]\nOwner's instructions: Count yogurt cups individually.\nCall record_fridge_changes with your answer." },
    ];
    const base = (attempt: number) => ({
      attempt, run_ms: now - MIN, model_id: "us.amazon.nova-2-lite-v1:0",
      request: { content: content(3), inferenceConfig: { maxTokens: 1024, temperature: 0 }, toolConfig: { toolChoice: { tool: { name: "record_fridge_changes" } } } },
    });
    const calls = [
      { ...base(1), outcome: "invalid", response: { output: { message: { role: "assistant", content: [{ text: "Milk was added." }] } }, stopReason: "end_turn", usage: { inputTokens: 1000, outputTokens: 50 }, metrics: { latencyMs: 1900 } },
        input_tokens: 1000, output_tokens: 50, cache_read_tokens: 0, cache_write_tokens: 1300, usd: 0.000468, latency_ms: 1900, wall_ms: 2050, error_code: null },
      { ...base(2), outcome: "ok", response: { output: { message: { role: "assistant", content: [{ toolUse: { name: "record_fridge_changes", input: { added: [{ item: "milk", category: "dairy", quantity: 1, confidence: 0.94 }], removed: [] } } }] } }, stopReason: "tool_use", usage: { inputTokens: 1180, outputTokens: 96, cacheReadInputTokens: 2000 }, metrics: { latencyMs: 2140 } },
        input_tokens: 1180, output_tokens: 96, cache_read_tokens: 2000, cache_write_tokens: 0, usd: 0.000818, latency_ms: 2140, wall_ms: 2310, error_code: null },
    ];
    const totals = (cs: typeof calls) => ({
      calls: cs.length, input_tokens: cs.reduce((a, c) => a + c.input_tokens, 0), output_tokens: cs.reduce((a, c) => a + c.output_tokens, 0),
      usd: Number(cs.reduce((a, c) => a + c.usd, 0).toFixed(6)), latency_ms: cs.reduce((a, c) => a + (c.latency_ms ?? 0), 0),
    });
    const walkStills = Array.from({ length: 5 }, (_, i) => ({
      n: i + 1, at_ms: now - 20 * MIN + i * 2000, url: "/mock/closed.svg", missing_status: null,
      zones: scores(false, i + 1), best_zone: 1, open: false,
    }));
    return [
      { id: "t0", device_id: "mock.device.D1", at: iso(2 * MIN), outcome: "door_open",
        best: { value: 0.19, zone: 1, feature: "change", threshold: 0.11 }, stills_downloaded: 7, door_event_id: "e0",
        nova: totals(calls), calls,
        door: { window: { start_ms: now - 2 * MIN, end_ms: now - 2 * MIN + 18000, ring_event_id: "evt" }, outcome: "door_open",
          door_sk: "DOOR#…", opened_at: iso(2 * MIN - 6000), closed_at: iso(2 * MIN - 12000), rule, stills: doorStills,
          open_span: [3, 4, 5, 6], picked: [3, 4, 6], stored_urls: [1, 2, 3].map((k) => `/mock/still-${k}.svg`) } },
      { id: "t1", device_id: "mock.device.D1", at: iso(20 * MIN), outcome: "not_door",
        best: { value: 0.0065, zone: 1, feature: "change", threshold: 0.11 }, stills_downloaded: 5, door_event_id: null,
        nova: totals([]), calls: [],
        door: { window: { start_ms: now - 20 * MIN, end_ms: now - 20 * MIN + 10000, ring_event_id: "evt2" }, outcome: "not_door",
          door_sk: null, opened_at: null, closed_at: null, rule, stills: walkStills, open_span: [], picked: [], stored_urls: [] } },
    ];
  }
  const eventsSince = (days: number) => events.filter((e) => Date.parse(e.opened_at) >= now - days * 24 * HOUR);
  const inventory = () => ({ items, pending_count: pending.length });
  return {
    name: "fridgesense-mock-api",
    apply: "serve",
    configureServer(server) {
      server.middlewares.use("/mock", (req, res) => {
        if (req.url === "/closed.svg") {
          res.setHeader("content-type", "image/svg+xml");
          return res.end(closedDoors());
        }
        const n = Number(req.url?.match(/^\/still-(\d)\.svg$/)?.[1]);
        if (!n) {
          res.statusCode = 404;
          return res.end();
        }
        res.setHeader("content-type", "image/svg+xml");
        res.end(fakeStill(n));
      });
      server.middlewares.use("/api", (req, res) => {
        const send = (status: number, body: unknown) => {
          res.statusCode = status;
          res.setHeader("content-type", "application/json");
          res.end(JSON.stringify(body));
        };
        const url = req.url ?? "";
        if (req.method === "POST" && url === "/session") return send(200, { token: "mock", expires_at: iso(-24 * HOUR), role: ["viewer", "user"].includes(process.env.FRIDGESENSE_MOCK ?? "") ? process.env.FRIDGESENSE_MOCK : "owner" });
        // FRIDGESENSE_MOCK=nocamera: signed in, but no Ring account linked yet.
        if (process.env.FRIDGESENSE_MOCK === "nocamera") return send(409, { error: "no camera linked" });
        if (url === "/inventory") return send(200, inventory());
        const doomed = url.match(/^\/events\/(.+)$/);
        if (req.method === "DELETE" && doomed) {
          const id = decodeURIComponent(doomed[1]);
          if (!events.some((e) => e.id === id)) return send(404, { error: "not found" });
          events = events.filter((e) => e.id !== id);
          pending = pending.filter((p) => p.door_event_id !== id);
          return send(200, { id });
        }
        if (url.startsWith("/debug/")) {
          if (process.env.FRIDGESENSE_MOCK === "viewer") return send(403, { error: "read-only" });
          if (process.env.FRIDGESENSE_MOCK === "user") return send(403, { error: "admin only" });
          const traces = debugTraces();
          const one = url.match(/^\/debug\/motions\/([^?]+)$/);
          if (one) {
            const id = decodeURIComponent(one[1]);
            const t = traces.find((m) => m.id === id || m.door_event_id === id);
            if (!t) return send(404, { error: "no trace" });
            const { nova, ...motion } = t;
            return send(200, { ...motion, nova_totals: nova, nova: t.calls, calls: undefined });
          }
          const q = new URLSearchParams(url.split("?")[1]);
          const from = Date.parse(q.get("from")!), to = Date.parse(q.get("to")!);
          const motions = traces
            .filter((m) => Date.parse(m.at) >= from && Date.parse(m.at) < to)
            .map(({ door: _door, calls: _calls, ...m }) => m);
          return send(200, { motions, next: null });
        }
        if (url.startsWith("/events")) {
          const q = new URLSearchParams(url.split("?")[1]);
          if (!q.has("from")) return send(200, { events: eventsSince(Number(q.get("days") ?? 7)), next: null });
          const from = Date.parse(q.get("from")!), to = Date.parse(q.get("to")!);
          let found = events
            .filter((e) => Date.parse(e.opened_at) >= from && Date.parse(e.opened_at) < to)
            .sort((a, b) => b.opened_at.localeCompare(a.opened_at));
          const cursor = found.findIndex((e) => e.id === q.get("cursor"));
          if (cursor >= 0) found = found.slice(cursor + 1);
          const limit = Number(q.get("limit") ?? found.length);
          return send(200, { events: found.slice(0, limit), next: found.length > limit ? found[limit - 1].id : null });
        }
        if (url === "/pending") return send(200, { pending });
        const m = url.match(/^\/pending\/(\w+)\/(confirm|reject)$/);
        if (m) {
          pending = pending.filter((p) => p.id !== m[1]);
          return send(200, inventory());
        }
        if (req.method === "POST" && url === "/ask") {
          // Canned assistant reply (no audio, so the browser's own voice reads it): the real
          // wording comes from Nova over MCP, or the backend's fridge-ask rules.
          let body = "";
          req.on("data", (c) => (body += c));
          req.on("end", () => {
            const question = String(JSON.parse(body || "{}").question ?? "");
            send(200, {
              intent: "agent",
              answer: cannedAnswer(question),
              data: { tools: ["get_inventory", "find_item", "fridge_activity"] },
              source: "agent",
              audio: null,
            });
          });
          return;
        }
        // Camera tab: Ring's documented example capabilities, and a short offline spell this morning.
        if (req.method === "GET" && url === "/camera") {
          const now = Date.now();
          const at = (msAgo: number) => new Date(now - msAgo).toISOString();
          return send(200, {
            device_id: "mock.device.D1",
            name: "Fridge Cam",
            image_url: null,
            manufacturer: "Ring",
            online: true,
            video: { codecs: ["AVC"], ratio: "16:9", max_resolution: 1080, supported_resolutions: [1080] },
            image_enhancements: [
              { name: "color_night_vision", on: false },
              { name: "hdr", on: true },
              { name: "ir_led_night_vision", on: false },
            ],
            motion_detection: true,
            e2e_encryption: false,
            location: { country: "US", state: "WA" },
            history: [
              { online: true, at: at(3 * HOUR), source: "webhook" },
              { online: false, at: at(5 * HOUR), source: "webhook" },
              { online: true, at: at(9 * 24 * HOUR), source: "poll" },
            ],
            uptime: { window_days: 30, percent: Math.round((1 - 2 / (9 * 24)) * 1000) / 10, since: at(9 * 24 * HOUR) },
            checked_at: at(0),
          });
        }
        // Live view needs a real camera: answer as if Ring were down, so the dialog's error path shows.
        if (req.method === "POST" && url === "/camera/live") return send(502, { error: "camera unavailable" });
        if (req.method === "DELETE" && url.startsWith("/camera/live/")) return send(200, { ok: true });
        // Live frame: nothing to blur in the mock, so the frame comes straight back.
        if (req.method === "POST" && url === "/camera/frame") {
          if (process.env.FRIDGESENSE_MOCK === "viewer") return send(403, { error: "read-only" });
          let body = "";
          req.on("data", (c) => (body += c));
          req.on("end", () => {
            const image = (JSON.parse(body || "{}") as { image?: unknown }).image;
            if (typeof image !== "string") return send(400, { error: "bad image" });
            send(200, { image, captured_at: new Date().toISOString() });
          });
          return;
        }
        // Door setup: snapshots alternate shut/open so both kinds of reference are easy to add.
        if (req.method === "POST" && url === "/camera/snapshot") {
          if (process.env.FRIDGESENSE_MOCK === "viewer") return send(403, { error: "read-only" });
          snapshots += 1;
          return send(200, { image: photo(snapshots % 2 ? "snapshot-closed" : "snapshot-open"), captured_at: new Date().toISOString() });
        }
        if (url === "/door-calibration" && req.method === "GET") return send(200, doorBody());
        // FRIDGESENSE_MOCK_WARNINGS=1 adds motion detection off and a moved camera.
        if (url === "/warnings" && req.method === "GET") {
          const all = !!process.env.FRIDGESENSE_MOCK_WARNINGS;
          const warnings = [
            ...(all ? [{ code: "motion_detection_off", message: "Motion detection is off on the camera, so no door openings are recorded. Turn it on in the Ring app." }] : []),
            ...(doorSetup ? [] : [{ code: "door_setup_missing", message: "Open/close detection is not set up, so the default zones are used and openings may be missed." }]),
            ...(all
              ? [{ code: "camera_moved", message: "The camera has moved or changed angle. Update the references so detection stays accurate.", since: iso(2 * HOUR), update: ["door_references", ...(fridgeArea ? ["fridge_area"] : [])] }]
              : []),
          ];
          return send(200, { warnings, checked_at: iso(0) });
        }
        if (url.startsWith("/door-calibration/") && process.env.FRIDGESENSE_MOCK === "viewer") return send(403, { error: "read-only" });
        if (req.method === "POST" && url === "/door-calibration/references") {
          let body = "";
          req.on("data", (c) => (body += c));
          req.on("end", () => {
            const { image, box, status } = JSON.parse(body);
            if (doorRefs.length >= 12) return send(409, { error: "at most 12 door references" });
            doorRefs = [...doorRefs, { id: `door${Date.now()}`, image, box, status, created_at: new Date().toISOString() }];
            refsChangedAt = Date.now();
            send(200, doorBody());
          });
          return;
        }
        const doorRef = url.match(/^\/door-calibration\/references\/(.+)$/);
        if (req.method === "DELETE" && doorRef) {
          const before = doorRefs.length;
          doorRefs = doorRefs.filter((r) => r.id !== decodeURIComponent(doorRef[1]));
          refsChangedAt = Date.now();
          return doorRefs.length < before ? send(200, doorBody()) : send(404, { error: "not found" });
        }
        if (req.method === "POST" && url === "/door-calibration/run") {
          const statuses = new Set(doorRefs.map((r) => r.status));
          if (statuses.size < 2) {
            return send(422, { error: "zone 1 needs an open and a closed reference", references: doorBody(true).references });
          }
          doorSetup = {
            zones: [{ ...doorRefs[0].box, feature: "color", direction: "above", threshold: 0.061, margin: 0.118 }],
            ran_at: new Date().toISOString(),
          };
          return send(200, doorBody());
        }
        if (url === "/fridge-area" && req.method === "GET") return send(200, { device_id: "mock.device.D1", area: fridgeArea });
        if (req.method === "PUT" && url === "/fridge-area") {
          if (process.env.FRIDGESENSE_MOCK === "viewer") return send(403, { error: "read-only" });
          let body = "";
          req.on("data", (c) => (body += c));
          req.on("end", () => {
            const { image, box } = JSON.parse(body);
            fridgeArea = { image, box, updated_at: new Date().toISOString() };
            send(200, { device_id: "mock.device.D1", area: fridgeArea });
          });
          return;
        }
        if (url === "/config" && req.method === "GET") return send(200, config);
        if (url.startsWith("/config/") && process.env.FRIDGESENSE_MOCK === "viewer") return send(403, { error: "read-only" });
        if (req.method === "PUT" && url === "/config/instructions") {
          let body = "";
          req.on("data", (c) => (body += c));
          req.on("end", () => {
            config = { ...config, instructions: String(JSON.parse(body).instructions ?? "").trim() };
            send(200, config);
          });
          return;
        }
        if (req.method === "POST" && url === "/config/references") {
          let body = "";
          req.on("data", (c) => (body += c));
          req.on("end", () => {
            const { annotation, image } = JSON.parse(body);
            if (config.references.length >= 6) return send(409, { error: "at most 6 reference images" });
            const id = `ref${Date.now()}`;
            config = {
              ...config,
              references: [...config.references, { id, annotation: String(annotation).trim(), image, created_at: new Date().toISOString() }],
            };
            send(200, config);
          });
          return;
        }
        const ref = url.match(/^\/config\/references\/(.+)$/);
        if (req.method === "DELETE" && ref) {
          const before = config.references.length;
          config = { ...config, references: config.references.filter((r) => r.id !== decodeURIComponent(ref[1])) };
          return config.references.length < before ? send(200, config) : send(404, { error: "not found" });
        }
        const itemKey = (name: string) => name.trim().split(/\s+/).join(" ").toLowerCase();
        const display = (name: string) => name.trim().split(/\s+/).join(" ");
        if (url.startsWith("/items") && process.env.FRIDGESENSE_MOCK === "viewer") return send(403, { error: "read-only" });
        if (req.method === "POST" && url === "/items") {
          let body = "";
          req.on("data", (c) => (body += c));
          req.on("end", () => {
            const { name, category, quantity } = JSON.parse(body);
            const key = itemKey(name);
            const at = new Date().toISOString();
            const old = items.find((i) => i.key === key);
            items = old
              ? items.map((i) => (i.key === key ? { ...i, category, quantity: i.quantity + quantity, last_changed_at: at } : i))
              : [...items, { key, name: display(name), category, quantity, last_changed_at: at }];
            send(200, inventory());
          });
          return;
        }
        const one = url.match(/^\/items\/(.+)$/);
        if (req.method === "PUT" && one) {
          let body = "";
          req.on("data", (c) => (body += c));
          req.on("end", () => {
            const key = decodeURIComponent(one[1]);
            const { quantity, name, category } = JSON.parse(body);
            const newKey = name === undefined ? key : itemKey(name);
            if (newKey !== key && items.some((i) => i.key === newKey)) return send(409, { error: "item exists" });
            const at = new Date().toISOString();
            items = items.map((i) =>
              i.key === key
                ? {
                    ...i,
                    key: newKey,
                    name: name === undefined ? i.name : display(name),
                    category: category ?? i.category,
                    quantity,
                    last_changed_at: at,
                  }
                : i,
            );
            send(200, inventory());
          });
          return;
        }
        if (req.method === "DELETE" && one) {
          const key = decodeURIComponent(one[1]);
          if (!items.some((i) => i.key === key)) return send(404, { error: "not found" });
          items = items.filter((i) => i.key !== key);
          return send(200, inventory());
        }
        send(404, { error: "not found" });
      });
    },
  };
}

/** A drawn stand-in for a camera still: fridge shelves with a few items; `n` shifts the scene a little. */
/** Closed steel doors: what the camera sees when nobody opens the fridge. */
function closedDoors(): string {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 180">
  <rect width="320" height="180" fill="#64748b"/>
  <rect x="100" y="20" width="58" height="150" rx="4" fill="#cbd5e1" stroke="#94a3b8"/>
  <rect x="162" y="20" width="58" height="150" rx="4" fill="#cbd5e1" stroke="#94a3b8"/>
  <rect x="150" y="70" width="4" height="40" rx="2" fill="#475569"/><rect x="166" y="70" width="4" height="40" rx="2" fill="#475569"/>
</svg>`;
}

function fakeStill(n: number): string {
  const dx = (n - 1) * 14;
  const glow = 0.35 + n * 0.08;
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 180">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f1f5f9"/><stop offset="1" stop-color="#cbd5e1"/></linearGradient>
    <radialGradient id="light" cx="0.5" cy="0" r="0.9"><stop offset="0" stop-color="#fffbeb" stop-opacity="${glow}"/><stop offset="1" stop-color="#fffbeb" stop-opacity="0"/></radialGradient>
  </defs>
  <rect width="320" height="180" fill="url(#bg)"/>
  <rect x="0" y="62" width="320" height="5" fill="#94a3b8"/>
  <rect x="0" y="124" width="320" height="5" fill="#94a3b8"/>
  <g transform="translate(${dx} 0)">
    <rect x="38" y="14" width="26" height="48" rx="5" fill="#f8fafc" stroke="#64748b"/><rect x="38" y="26" width="26" height="12" fill="#38bdf8"/>
    <rect x="78" y="32" width="54" height="30" rx="4" fill="#fde68a" stroke="#b45309"/>
    <circle cx="160" cy="50" r="12" fill="#ef4444"/><circle cx="182" cy="52" r="10" fill="#dc2626"/>
    <rect x="212" y="20" width="22" height="42" rx="4" fill="#fb923c"/>
    <ellipse cx="70" cy="110" rx="30" ry="13" fill="#fef3c7" stroke="#d97706"/>
    <rect x="120" y="86" width="60" height="38" rx="6" fill="#e2e8f0" stroke="#64748b"/><rect x="128" y="96" width="44" height="18" rx="3" fill="#fca5a5"/>
    <rect x="200" y="96" width="44" height="28" rx="5" fill="#86efac" stroke="#15803d"/>
    <rect x="50" y="146" width="80" height="26" rx="6" fill="#bbf7d0" stroke="#16a34a"/>
    <rect x="160" y="140" width="18" height="32" rx="3" fill="#a3e635"/><rect x="184" y="144" width="18" height="28" rx="3" fill="#facc15"/>
  </g>
  <rect width="320" height="180" fill="url(#light)"/>
</svg>`;
}

/** Plausible assistant replies for the example questions, so the Ask screen reads like the real thing. */
function cannedAnswer(question: string): string {
  const q = question.toLowerCase();
  if (q.includes("milk")) return "Yes, you have 1 milk. It was added 2 minutes ago.";
  if (q.includes("eat first"))
    return "Eat the salmon fillet and baby spinach first: they've been in the fridge over a day. The leftover pasta is next.";
  if (q.includes("buy")) return "You're out of soda cans, and down to 1 milk and 1 orange juice.";
  if (q.includes("last opened")) return "The fridge was last opened 2 minutes ago, for 18 seconds. Milk went in.";
  if (q.includes("what's in") || q.includes("what is in"))
    return "You have 17 kinds of items: 10 eggs, 6 sparkling waters, 5 apples, 4 Greek yogurts, 3 bell peppers, 2 chicken breasts, leftover pasta, milk, cheese and more.";
  return `I checked the fridge for "${question}" but couldn't find anything matching.`;
}
