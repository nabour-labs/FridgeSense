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
  const eventsSince = (days: number) => events.filter((e) => Date.parse(e.opened_at) >= now - days * 24 * HOUR);
  const inventory = () => ({ items, pending_count: pending.length });
  return {
    name: "fridgesense-mock-api",
    apply: "serve",
    configureServer(server) {
      server.middlewares.use("/mock", (req, res) => {
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
        if (req.method === "POST" && url === "/session") return send(200, { token: "mock", expires_at: iso(-24 * HOUR), role: process.env.FRIDGESENSE_MOCK === "viewer" ? "viewer" : "owner" });
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
