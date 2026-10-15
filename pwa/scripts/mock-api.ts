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
  const stills = [1, 2, 3, 4].map((n) => `/mock/still-${n}.svg`);
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
  <text x="10" y="172" font-family="monospace" font-size="9" fill="#475569">MOCK STILL ${n}/4</text>
</svg>`;
}
