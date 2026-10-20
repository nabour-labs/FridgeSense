import type { CameraInfo, Change, DoorEvent, Item } from "../api/types";
import { activityRows, cameraLine, clockTime, fridgeRows, heatCells, opensSummary, outOfStock, recentRows, stillBase, tvIcon } from "./tv";

const TZ = "America/Toronto";
const NOW = new Date("2026-10-20T18:00:00Z"); // 14:00 in Toronto

function item(name: string, quantity: number, category: string): Item {
  return { key: name.replace(/ /g, "-"), name, category, quantity, last_changed_at: null };
}

function change(item: string, direction: "added" | "removed", quantity: number, extra: Partial<Change> = {}): Change {
  return { item, category: "dairy", direction, quantity, confidence: 0.9, applied: true, ...extra };
}

function event(opened_at: string, extra: Partial<DoorEvent> = {}): DoorEvent {
  return {
    id: opened_at,
    opened_at,
    closed_at: opened_at,
    duration_s: 20,
    status: "done",
    changes: [],
    pending_count: 0,
    stills: [],
    clip: null,
    ...extra,
  };
}

// Items by category
test("in-stock items are grouped by category in API order and out-of-stock items are left out", () => {
  const rows = fridgeRows([
    item("eggs", 6, "dairy"),
    item("apple", 3, "produce"),
    item("milk", 1, "dairy"),
    item("soda can", 0, "beverage"),
  ]);
  expect(rows.groups.map((g) => [g.category, g.items.map((i) => `${i.name} ×${i.quantity}`)])).toEqual([
    ["dairy", ["eggs ×6", "milk ×1"]],
    ["produce", ["apple ×3"]],
  ]);
  expect(rows.more).toBe(0);
  expect(rows.empty).toBe(false);
});

// More than fits
test("at most 12 items are shown, then the rest are counted", () => {
  const items = Array.from({ length: 15 }, (_, i) => item(`item ${i + 1}`, 1, i < 10 ? "dairy" : "produce"));
  const rows = fridgeRows(items);
  expect(rows.groups.flatMap((g) => g.items)).toHaveLength(12);
  expect(rows.groups.map((g) => g.items.length)).toEqual([10, 2]);
  expect(rows.more).toBe(3);
});

// Empty fridge
test("a fridge with nothing in stock is empty", () => {
  const rows = fridgeRows([item("soda can", 0, "beverage")]);
  expect(rows).toEqual({ groups: [], more: 0, empty: true });
});

// Newest five
test("the 5 newest openings are listed, newest first", () => {
  const events = [1, 7, 3, 5, 2, 6, 4].map((h) =>
    event(`2026-10-20T${String(10 + h).padStart(2, "0")}:00:00Z`, { changes: [change("milk", "added", 1)] }),
  );
  const rows = recentRows(events, NOW.getTime(), TZ);
  expect(rows.map((r) => r.id)).toEqual([
    "2026-10-20T17:00:00Z",
    "2026-10-20T16:00:00Z",
    "2026-10-20T15:00:00Z",
    "2026-10-20T14:00:00Z",
    "2026-10-20T13:00:00Z",
  ]);
});

// Time and duration
test("a row shows how long ago, the local clock time and whole seconds open", () => {
  const rows = recentRows([event("2026-10-20T17:58:00Z", { duration_s: 12.4, changes: [change("milk", "added", 1)] })], NOW.getTime(), TZ);
  expect(rows[0].when).toBe("2 min ago · 1:58 pm · 12 s");
});

test("clock time is lower-case 12-hour time in the given time zone", () => {
  expect(clockTime("2026-10-21T00:42:00Z", TZ)).toBe("8:42 pm");
  expect(clockTime("2026-10-20T04:05:00Z", TZ)).toBe("12:05 am");
});

// Change labels
test("an opening's changes are labelled, without rejected ones", () => {
  const rows = recentRows(
    [
      event("2026-10-20T17:58:00Z", {
        changes: [
          change("milk", "added", 2),
          change("eggs", "removed", 1),
          change("apple", "added", 1, { rejected: true, applied: false }),
        ],
      }),
    ],
    NOW.getTime(),
    TZ,
  );
  expect(rows).toEqual([
    { id: "2026-10-20T17:58:00Z", when: "2 min ago · 1:58 pm · 20 s", state: "changes", labels: ["+ 2 milk", "− eggs"], count: 1, proofs: [] },
  ]);
});

// Analysis running
test("an opening still being analyzed is checking and is not collapsed", () => {
  const rows = recentRows(
    [event("2026-10-20T17:59:00Z", { status: "analyzing" }), event("2026-10-20T17:00:00Z"), event("2026-10-20T16:00:00Z")],
    NOW.getTime(),
    TZ,
  );
  expect(rows.map((r) => [r.state, r.count])).toEqual([
    ["checking", 1],
    ["none", 2],
  ]);
});

// No-change openings collapse
test("back-to-back openings with no changes collapse into one row with the newest time", () => {
  const rows = recentRows(
    [
      event("2026-10-20T17:50:00Z"),
      event("2026-10-20T17:40:00Z"),
      event("2026-10-20T17:30:00Z"),
      event("2026-10-20T17:20:00Z", { changes: [change("beer", "added", 1)] }),
    ],
    NOW.getTime(),
    TZ,
  );
  expect(rows.map((r) => [r.when, r.state, r.count, r.labels])).toEqual([
    ["10 min ago · 1:50 pm · 20 s", "none", 3, []],
    ["40 min ago · 1:20 pm · 20 s", "changes", 1, ["+ beer"]],
  ]);
});

test("collapsing happens before taking 5 rows", () => {
  const events = Array.from({ length: 6 }, (_, i) => event(`2026-10-20T1${7 - i}:00:00Z`)).concat(
    Array.from({ length: 5 }, (_, i) => event(`2026-10-20T0${9 - i}:00:00Z`, { changes: [change("milk", "added", 1)] })),
  );
  const rows = recentRows(events, NOW.getTime(), TZ);
  expect(rows.map((r) => r.count)).toEqual([6, 1, 1, 1, 1]);
});

// Single no-change opening
test("a lone no-change opening is not counted", () => {
  const rows = recentRows(
    [
      event("2026-10-20T17:50:00Z", { changes: [change("milk", "added", 1)] }),
      event("2026-10-20T17:40:00Z"),
      event("2026-10-20T17:30:00Z", { changes: [change("eggs", "removed", 1)] }),
    ],
    NOW.getTime(),
    TZ,
  );
  expect(rows.map((r) => [r.state, r.count])).toEqual([
    ["changes", 1],
    ["none", 1],
    ["changes", 1],
  ]);
});

// Quiet week
test("no openings, or only older than 7 days, give no rows", () => {
  expect(recentRows([], NOW.getTime(), TZ)).toEqual([]);
  expect(recentRows([event("2026-10-10T17:00:00Z", { changes: [change("milk", "added", 1)] })], NOW.getTime(), TZ)).toEqual([]);
});

// Today's count
test("opens today and per day in the device's time zone", () => {
  const events = [
    event("2026-10-20T12:00:00Z"),
    event("2026-10-20T15:00:00Z"),
    event("2026-10-20T17:00:00Z"),
    event("2026-10-19T15:00:00Z"),
    event("2026-10-20T03:00:00Z"), // 23:00 on Oct 19 in Toronto
  ];
  const summary = opensSummary(events, NOW, TZ);
  expect(summary.today).toBe(3);
  expect(summary.label).toBe("3 opens today");
  expect(summary.days).toHaveLength(7);
  expect(summary.days.slice(-2).map((d) => d.opens)).toEqual([2, 3]);
});

// One opening today
test("one opening today is singular", () => {
  expect(opensSummary([event("2026-10-20T17:00:00Z")], NOW, TZ).label).toBe("1 open today");
});

// Open time today
test("today's average and longest open time", () => {
  const events = [
    event("2026-10-20T15:00:00Z", { duration_s: 10 }),
    event("2026-10-20T16:00:00Z", { duration_s: 14 }),
    event("2026-10-20T17:00:00Z", { duration_s: 40 }),
    event("2026-10-19T17:00:00Z", { duration_s: 90 }),
  ];
  expect(opensSummary(events, NOW, TZ).openTime).toBe("Avg 21 s · Longest 40 s");
});

// No openings today
test("no openings today: zero opens and no open time", () => {
  const summary = opensSummary([event("2026-10-19T17:00:00Z")], NOW, TZ);
  expect(summary.label).toBe("0 opens today");
  expect(summary.openTime).toBeNull();
});

test("the 7-day bars ignore openings older than a week", () => {
  const summary = opensSummary([event("2026-10-01T17:00:00Z"), event("2026-10-20T17:00:00Z")], NOW, TZ);
  expect(summary.days.reduce((n, d) => n + d.opens, 0)).toBe(1);
});

// Heatmap
test("heatmap cells by weekday and hour, labelled and shaded", () => {
  const mondays = ["2026-10-19", "2026-10-12", "2026-10-05", "2026-09-28"].map((d) => event(`${d}T12:00:00Z`)); // 8 am Mon
  const tuesday = event("2026-10-13T22:00:00Z"); // 6 pm Tue
  const grid = heatCells([...mondays, tuesday], TZ);
  expect(grid).toHaveLength(7);
  expect(grid.every((row) => row.length === 24)).toBe(true);
  expect(grid[1][8]).toEqual({ label: "Mon 8 am: 4 opens", level: 4 });
  expect(grid[2][18]).toEqual({ label: "Tue 6 pm: 1 open", level: 1 });
  expect(grid[0][0]).toEqual({ label: "Sun 12 am: 0 opens", level: 0 });
  expect(grid.flat().filter((c) => c.level > 0)).toHaveLength(2);
});

// Out of stock
test("out-of-stock items are named in inventory order", () => {
  expect(outOfStock([item("milk", 0, "dairy"), item("eggs", 0, "dairy"), item("cheese", 2, "dairy")])).toBe("Out: milk, eggs");
});

// Many out of stock
test("at most 6 out-of-stock names, then a count", () => {
  const items = Array.from({ length: 8 }, (_, i) => item(`item ${i + 1}`, 0, "dairy"));
  expect(outOfStock(items)).toBe("Out: item 1, item 2, item 3, item 4, item 5, item 6, +2 more");
});

// Nothing out of stock
test("nothing out of stock gives no line", () => {
  expect(outOfStock([item("cheese", 2, "dairy")])).toBeNull();
});

function camera(extra: Partial<CameraInfo> = {}): CameraInfo {
  return {
    device_id: "d1",
    name: "Fridge Cam",
    image_url: "https://ring/cam.png",
    manufacturer: "Ring",
    online: true,
    video: null,
    image_enhancements: null,
    motion_detection: true,
    e2e_encryption: false,
    location: null,
    history: [],
    uptime: { window_days: 30, percent: 99.2, since: null },
    checked_at: "2026-10-20T18:00:00Z",
    monitoring: { paused: false, since: null },
    ...extra,
  };
}

// Camera online
test("camera line for an online camera", () => {
  expect(cameraLine(camera())).toBe("Fridge Cam · Online · 99.2% uptime · Motion detection on");
});

// Camera offline
test("camera line for an offline camera", () => {
  const line = cameraLine(camera({ online: false, motion_detection: false, uptime: { window_days: 30, percent: 75, since: null } }));
  expect(line).toBe("Fridge Cam · Offline · 75.0% uptime · Motion detection off");
});

// Ring unavailable
test("camera line when Ring can't be reached", () => {
  const line = cameraLine(
    camera({ ring: "unavailable", online: null, motion_detection: null, uptime: { window_days: 30, percent: null, since: null } }),
  );
  expect(line).toBe("Fridge Cam · Status unknown");
});

test("unavailable Ring is unknown even if online is set", () => {
  expect(cameraLine(camera({ ring: "unavailable" }))).toContain("Status unknown");
});

// Monitoring paused
test("camera line says when monitoring is paused", () => {
  expect(cameraLine(camera({ monitoring: { paused: true, since: null } }))).toBe(
    "Fridge Cam · Online · Paused · 99.2% uptime · Motion detection on",
  );
});

// Condiment on the TV
test("condiments get a salt shaker on the TV", () => {
  expect(tvIcon("condiment", "condiment")).toBe("🧂");
  expect(tvIcon("ketchup", "condiment")).toBe("🧂");
});

// Pepper on the TV
test("peppers get a chili on the TV", () => {
  expect(tvIcon("bell pepper", "produce")).toBe("🌶️");
});

test("other icons are unchanged on the TV", () => {
  expect(tvIcon("milk", "dairy")).toBe("🥛");
});

// Proof under the labels
test("a row's proofs are each change's first proof link, in label order", () => {
  const e = event("2026-10-20T17:58:00Z", {
    changes: [
      change("milk", "added", 2, { proof: ["https://s3/a.jpg", "https://s3/b.jpg"] }),
      change("eggs", "removed", 1, { proof: ["https://s3/c.jpg"] }),
    ],
  });
  expect(recentRows([e], NOW.getTime(), TZ)[0].proofs).toEqual(["https://s3/a.jpg", "https://s3/c.jpg"]);
});

// At most three photos
test("a row has at most 3 proofs, from its first changes", () => {
  const changes = ["a", "b", "c", "d", "e"].map((n) => change(n, "added", 1, { proof: [`https://s3/${n}.jpg`] }));
  const rows = recentRows([event("2026-10-20T17:58:00Z", { changes })], NOW.getTime(), TZ);
  expect(rows[0].proofs).toEqual(["https://s3/a.jpg", "https://s3/b.jpg", "https://s3/c.jpg"]);
});

// Change without proof
test("a change without proof adds no photo", () => {
  const e = event("2026-10-20T17:58:00Z", {
    changes: [change("milk", "added", 1), change("eggs", "removed", 1, { proof: ["https://s3/c.jpg"] })],
  });
  expect(recentRows([e], NOW.getTime(), TZ)[0].proofs).toEqual(["https://s3/c.jpg"]);
});

// Rejected change has no photo
test("a rejected change's proof is left out", () => {
  const e = event("2026-10-20T17:58:00Z", {
    changes: [change("milk", "added", 1), change("apple", "added", 1, { rejected: true, proof: ["https://s3/r.jpg"] })],
  });
  expect(recentRows([e], NOW.getTime(), TZ)[0].proofs).toEqual([]);
});

// No photos without changes
test("checking, no-change and collapsed rows have no proofs", () => {
  const stills = ["https://s3/1.jpg"];
  const rows = recentRows(
    [
      event("2026-10-20T17:58:00Z", { status: "analyzing", stills }),
      event("2026-10-20T17:50:00Z", { stills }),
      event("2026-10-20T17:40:00Z", { stills }),
    ],
    NOW.getTime(),
    TZ,
  );
  expect(rows.map((r) => [r.state, r.count, r.proofs])).toEqual([
    ["checking", 1, []],
    ["none", 2, []],
  ]);
});

// Re-signed link kept (the key it is kept by)
test("a still's base is its link without the query string", () => {
  expect(stillBase("https://s3/a.jpg?X-Amz-Signature=1")).toBe("https://s3/a.jpg");
  expect(stillBase("https://s3/a.jpg")).toBe("https://s3/a.jpg");
  expect(stillBase("/mock/still-1.svg")).toBe("/mock/still-1.svg");
});

describe("activityRows", () => {
  const rows = (events: DoorEvent[]) => activityRows(events, NOW.getTime(), TZ);

  // Opening with changes, stills and proof
  test("a row has the day, clock time, seconds, labels, stills and proof photos", () => {
    const [row] = rows([
      event("2026-10-20T14:36:00Z", {
        duration_s: 18,
        changes: [change("bowl", "added", 1, { proof: ["https://s3/p.jpg", "https://s3/q.jpg"] })],
        stills: ["https://s3/1.jpg", "https://s3/2.jpg"],
      }),
    ]);
    expect(row).toEqual({
      id: "2026-10-20T14:36:00Z",
      when: "Today · 10:36 am · 18 s",
      state: "changes",
      labels: ["+ bowl"],
      stills: ["https://s3/1.jpg", "https://s3/2.jpg"],
      proofs: ["https://s3/p.jpg"],
    });
  });

  test("the day reads Yesterday, then the weekday, in the given time zone", () => {
    // 02:00 UTC on the 20th is 10 pm on the 19th in Toronto.
    expect(rows([event("2026-10-20T02:00:00Z")])[0].when).toBe("Yesterday · 10:00 pm · 20 s");
    expect(rows([event("2026-10-17T15:00:00Z")])[0].when).toBe("Sat · 11:00 am · 20 s");
  });

  // At most four stills
  test("at most the first four stills are kept", () => {
    const stills = [1, 2, 3, 4, 5, 6].map((i) => `https://s3/${i}.jpg`);
    expect(rows([event("2026-10-20T17:00:00Z", { stills })])[0].stills).toEqual(stills.slice(0, 4));
  });

  test("proof photos skip rejected changes and stop at three", () => {
    const proof = (i: number) => ({ proof: [`https://s3/p${i}.jpg`] });
    const [row] = rows([
      event("2026-10-20T17:00:00Z", {
        changes: [
          change("a", "added", 1, { ...proof(1), rejected: true, applied: false }),
          change("b", "added", 1, proof(2)),
          change("c", "added", 1),
          change("d", "added", 1, proof(4)),
          change("e", "added", 1, proof(5)),
          change("f", "added", 1, proof(6)),
        ],
      }),
    ]);
    expect(row.proofs).toEqual(["https://s3/p2.jpg", "https://s3/p4.jpg", "https://s3/p5.jpg"]);
  });

  // Every opening has its own row
  test("openings without changes each get their own row, newest first", () => {
    const r = rows([event("2026-10-20T15:00:00Z"), event("2026-10-20T17:00:00Z"), event("2026-10-20T16:00:00Z")]);
    expect(r.map((x) => [x.id, x.state])).toEqual([
      ["2026-10-20T17:00:00Z", "none"],
      ["2026-10-20T16:00:00Z", "none"],
      ["2026-10-20T15:00:00Z", "none"],
    ]);
  });

  // Still being analyzed
  test("an opening being analyzed is checking, keeps its stills and has no proof photos", () => {
    const [row] = rows([
      event("2026-10-20T17:00:00Z", {
        status: "analyzing",
        stills: ["https://s3/1.jpg"],
        changes: [change("milk", "added", 1, { proof: ["https://s3/p.jpg"] })],
      }),
    ]);
    expect(row.state).toBe("checking");
    expect(row.stills).toEqual(["https://s3/1.jpg"]);
    expect(row.proofs).toEqual([]);
  });

  // Older than a week left out
  test("openings older than 7 days are left out", () => {
    expect(rows([event("2026-10-11T17:00:00Z"), event("2026-10-20T17:00:00Z")]).map((r) => r.id)).toEqual(["2026-10-20T17:00:00Z"]);
  });

  // Nothing this week
  test("no openings this week gives no rows", () => {
    expect(rows([event("2026-10-11T17:00:00Z")])).toEqual([]);
    expect(rows([])).toEqual([]);
  });
});
