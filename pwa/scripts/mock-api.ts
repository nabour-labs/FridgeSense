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
    ["apple", "Apple", "produce", 5, 5 * HOUR],
    ["baby spinach", "Baby spinach", "produce", 1, 30 * HOUR],
    ["soda can", "Soda can", "beverage", 0, 50 * MIN],
    ["orange juice", "Orange juice", "beverage", 1, 2 * 24 * HOUR],
    ["leftover pasta", "Leftover pasta", "leftovers", 2, 20 * HOUR],
  ].map(([key, name, category, quantity, ago]) => ({
    key, name, category, quantity, last_changed_at: iso(ago as number),
  }));
  let pending = [
    { id: "p1", door_event_id: "e1", item: "chocolate bar", category: "snack", direction: "removed",
      quantity: 1, confidence: 0.62, opened_at: iso(50 * MIN) },
    { id: "p2", door_event_id: "e2", item: "bottle", category: "beverage", direction: "added",
      quantity: 1, confidence: 0.48, opened_at: iso(5 * HOUR) },
  ];
  const stills = [1, 2, 3, 4].map(() => "/icon-512.png");
  const events = [
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
    ...Array.from({ length: 18 }, (_, i) => ({
      id: `old${i}`, opened_at: iso((14 + i * 7) * HOUR), duration_s: 15 + ((i * 7) % 30),
      status: "done", pending_count: 0, stills: [], changes: [],
    })),
  ];
  const inventory = () => ({ items, pending_count: pending.length });
  return {
    name: "fridgesense-mock-api",
    apply: "serve",
    configureServer(server) {
      server.middlewares.use("/api", (req, res) => {
        const send = (status: number, body: unknown) => {
          res.statusCode = status;
          res.setHeader("content-type", "application/json");
          res.end(JSON.stringify(body));
        };
        const url = req.url ?? "";
        if (req.method === "POST" && url === "/session") return send(200, { token: "mock", expires_at: iso(-30 * 24 * HOUR), role: process.env.FRIDGESENSE_MOCK === "viewer" ? "viewer" : "owner" });
        if (url === "/inventory") return send(200, inventory());
        if (url.startsWith("/events")) return send(200, { events });
        if (url === "/pending") return send(200, { pending });
        const m = url.match(/^\/pending\/(\w+)\/(confirm|reject)$/);
        if (m) {
          pending = pending.filter((p) => p.id !== m[1]);
          return send(200, inventory());
        }
        const put = url.match(/^\/items\/(.+)$/);
        if (req.method === "PUT" && put) {
          let body = "";
          req.on("data", (c) => (body += c));
          req.on("end", () => {
            const key = decodeURIComponent(put[1]);
            items = items.map((i) => (i.key === key ? { ...i, quantity: JSON.parse(body).quantity } : i));
            send(200, inventory());
          });
          return;
        }
        send(404, { error: "not found" });
      });
    },
  };
}
