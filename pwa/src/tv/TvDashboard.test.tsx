import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { ApiError } from "../api/client";
import type { CameraInfo, DoorEvent, Item } from "../api/types";
import { AppContext, type Api } from "../AppContext";
import { fakeApi } from "../test-utils";
import { deviceTimeZone } from "../stats";
import { TvDashboard } from "./TvDashboard";
import { clockTime } from "./tv";

function item(name: string, quantity: number, category: string): Item {
  return { key: name, name, category, quantity, last_changed_at: null };
}

function event(minutesAgo: number, extra: Partial<DoorEvent> = {}): DoorEvent {
  const at = new Date(Date.now() - minutesAgo * 60_000).toISOString();
  return {
    id: `e${minutesAgo}`,
    opened_at: at,
    closed_at: at,
    duration_s: 20,
    status: "done",
    changes: [],
    pending_count: 0,
    stills: [],
    clip: null,
    ...extra,
  };
}

const ITEMS = [item("eggs", 6, "dairy"), item("milk", 1, "dairy"), item("apple", 3, "produce"), item("soda can", 0, "beverage")];

const MILK_EVENT = event(2, {
  changes: [
    { item: "milk", category: "dairy", direction: "added", quantity: 2, confidence: 0.9, applied: true, proof: ["https://s3/proof-1.jpg"] },
    { item: "eggs", category: "dairy", direction: "removed", quantity: 1, confidence: 0.9, applied: true },
  ],
  stills: ["https://s3/still-1.jpg"],
  clip: "https://s3/clip.mp4#t=1,3",
});

const CAMERA: CameraInfo = {
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
  checked_at: new Date().toISOString(),
  monitoring: { paused: false, since: null },
};

function renderTv(overrides: Partial<Record<keyof Api, unknown>> = {}) {
  const api = fakeApi({
    inventory: vi.fn().mockResolvedValue({ items: ITEMS, pending_count: 0 }),
    events: vi.fn().mockResolvedValue({ events: [MILK_EVENT] }),
    camera: vi.fn().mockResolvedValue(CAMERA),
    ...overrides,
  });
  const report = vi.fn();
  render(
    <AppContext.Provider value={{ api, role: "viewer", report, online: vi.fn(), go: vi.fn() }}>
      <TvDashboard />
    </AppContext.Provider>,
  );
  return { api, report };
}

const panel = (name: string) => screen.findByRole("region", { name });

// Items by category
test("In the fridge lists in-stock items by category", async () => {
  renderTv();
  const fridge = await panel("In the fridge");
  const dairy = await within(fridge).findByRole("list", { name: "Dairy" });
  expect(within(dairy).getAllByRole("listitem").map((li) => li.textContent)).toEqual([
    expect.stringMatching(/eggs.*×6/),
    expect.stringMatching(/milk.*×1/),
  ]);
  expect(within(fridge).getByRole("list", { name: "Produce" })).toHaveTextContent(/apple.*×3/);
  for (const list of within(fridge).getAllByRole("list")) expect(list).not.toHaveTextContent(/soda can/);
});

// More than fits
test("more than 12 items shows +N more", async () => {
  const many = Array.from({ length: 15 }, (_, i) => item(`item ${i + 1}`, 1, "dairy"));
  renderTv({ inventory: vi.fn().mockResolvedValue({ items: many, pending_count: 0 }) });
  const fridge = await panel("In the fridge");
  expect(await within(fridge).findByText("+3 more")).toBeInTheDocument();
  expect(within(fridge).getAllByRole("listitem")).toHaveLength(12);
});

// Empty fridge
test("an empty fridge says so", async () => {
  renderTv({ inventory: vi.fn().mockResolvedValue({ items: [item("soda can", 0, "beverage")], pending_count: 0 }) });
  expect(await within(await panel("In the fridge")).findByText("The fridge is empty")).toBeInTheDocument();
});

// Change labels
test("Recent changes shows when each opening happened and what changed", async () => {
  renderTv();
  const recent = await panel("Recent changes");
  const row = await within(recent).findByRole("listitem");
  expect(row).toHaveTextContent("2 min ago");
  expect(row).toHaveTextContent("+ 2 milk");
  expect(row).toHaveTextContent("− eggs");
});

// Analysis running
test("an opening being analyzed shows Checking…", async () => {
  renderTv({ events: vi.fn().mockResolvedValue({ events: [event(1, { status: "analyzing" }), event(30)] }) });
  const recent = await panel("Recent changes");
  expect(await within(recent).findByText("Checking…")).toBeInTheDocument();
  expect(within(recent).getByText("No changes")).toBeInTheDocument();
});

// Quiet week
test("no openings says no door openings this week", async () => {
  renderTv({ events: vi.fn().mockResolvedValue({ events: [] }) });
  expect(await within(await panel("Recent changes")).findByText("No door openings this week")).toBeInTheDocument();
});

// Today's count
test("Opens shows today's count from the same openings, last 7 days", async () => {
  const { api } = renderTv({ events: vi.fn().mockResolvedValue({ events: [event(1), event(2), event(3)] }) });
  const opens = await panel("Opens");
  expect(await within(opens).findByText("3 opens today")).toBeInTheDocument();
  expect(api.events).toHaveBeenCalledTimes(1);
});

// Four weeks requested
test("the dashboard loads 28 days of openings", async () => {
  const { api } = renderTv();
  await panel("Opens");
  expect(api.events).toHaveBeenCalledWith(28);
});

// Inventory refresh
test("inventory refreshes every 10 s and openings every 30 s", async () => {
  vi.useFakeTimers();
  try {
    const { api } = renderTv();
    await act(async () => void vi.advanceTimersByTime(30_000));
    expect(api.inventory).toHaveBeenCalledTimes(4);
    expect(api.events).toHaveBeenCalledTimes(2);
  } finally {
    vi.useRealTimers();
  }
});

// Camera refresh
test("the camera refreshes every 5 minutes, not sooner", async () => {
  vi.useFakeTimers();
  try {
    const { api } = renderTv();
    await act(async () => void vi.advanceTimersByTime(30_000));
    expect(api.camera).toHaveBeenCalledTimes(1);
    await act(async () => void vi.advanceTimersByTime(270_000));
    expect(api.camera).toHaveBeenCalledTimes(2);
  } finally {
    vi.useRealTimers();
  }
});

// Events fail, inventory loads
test("a failed events load shows No Data in its panels only", async () => {
  const { report } = renderTv({ events: vi.fn().mockRejectedValue(new ApiError(500)) });
  expect(await within(await panel("Recent changes")).findByText("No Data")).toBeInTheDocument();
  expect(within(await panel("Opens")).getByText("No Data")).toBeInTheDocument();
  expect(await within(await panel("In the fridge")).findByText(/eggs/)).toBeInTheDocument();
  expect(report).toHaveBeenCalled();
});

// No clips or video
test("no clip or video is shown", async () => {
  renderTv();
  await within(await panel("Recent changes")).findByText(/2 min ago/);
  const dashboard = screen.getByRole("region", { name: "TV dashboard" });
  expect(dashboard.querySelectorAll("video")).toHaveLength(0);
  expect(dashboard.innerHTML).not.toContain("clip.mp4");
});

// Only opening pictures and the icon shown
test("the only pictures are the icon and the openings' proof photos", async () => {
  renderTv();
  await within(await panel("Recent changes")).findByText(/2 min ago/);
  const dashboard = screen.getByRole("region", { name: "TV dashboard" });
  const srcs = [...dashboard.querySelectorAll("img")].map((img) => img.getAttribute("src"));
  expect(srcs.sort()).toEqual(["/icon.svg", "https://s3/proof-1.jpg"]);
});

// Camera image not shown
test("the camera's image is not shown", async () => {
  renderTv();
  expect(await screen.findByText(/Fridge Cam/)).toBeInTheDocument();
  await within(await panel("Recent changes")).findByText(/2 min ago/);
  const dashboard = screen.getByRole("region", { name: "TV dashboard" });
  expect(dashboard.querySelector('img[src*="ring/cam.png"]')).toBeNull();
  expect(dashboard.innerHTML).not.toContain("ring/cam.png");
});

// No controls
test("the dashboard has no buttons, links or inputs", async () => {
  renderTv();
  await within(await panel("Recent changes")).findByText(/2 min ago/);
  await screen.findByText(/Fridge Cam/);
  const dashboard = screen.getByRole("region", { name: "TV dashboard" });
  expect(within(dashboard).queryAllByRole("button")).toHaveLength(0);
  expect(within(dashboard).queryAllByRole("link")).toHaveLength(0);
  expect(within(dashboard).queryAllByRole("textbox")).toHaveLength(0);
});

// Only three endpoints
test("only the inventory, events and camera endpoints are called", async () => {
  const { api } = renderTv();
  await within(await panel("Recent changes")).findByText(/2 min ago/);
  const called = Object.entries(api)
    .filter(([, fn]) => vi.isMockFunction(fn) && fn.mock.calls.length > 0)
    .map(([name]) => name)
    .sort();
  expect(called).toEqual(["camera", "events", "inventory"]);
  expect(api.cameraSnapshot).not.toHaveBeenCalled();
});

// Back is left to the TV app
test("Escape is not handled by the dashboard", async () => {
  location.hash = "#tv";
  renderTv();
  await panel("In the fridge");
  const notHandled = fireEvent.keyDown(document.body, { key: "Escape", keyCode: 27 });
  expect(notHandled).toBe(true);
  expect(location.hash).toBe("#tv");
  location.hash = "";
});

// Camera online
test("the camera line is shown under the title", async () => {
  renderTv();
  expect(await screen.findByText("Fridge Cam · Online · 99.2% uptime · Motion detection on")).toBeInTheDocument();
});

// Camera fails, panels load
test("a failed camera load shows No Data for the camera only", async () => {
  renderTv({ camera: vi.fn().mockRejectedValue(new ApiError(500)) });
  expect(await screen.findByText("Camera: No Data")).toBeInTheDocument();
  expect(await within(await panel("In the fridge")).findByText(/eggs/)).toBeInTheDocument();
  expect(await within(await panel("Recent changes")).findByText(/2 min ago/)).toBeInTheDocument();
  expect(within(await panel("Opens")).getByText("1 open today")).toBeInTheDocument();
});

// Updated after load
test("the header shows when data last loaded", async () => {
  renderTv();
  await within(await panel("In the fridge")).findByText(/eggs/);
  const now = new Date().toISOString();
  expect(await screen.findByText(`Updated ${clockTime(now, deviceTimeZone())}`)).toBeInTheDocument();
});

// Nothing loaded yet
test("no Updated text before anything loads", async () => {
  renderTv({ inventory: vi.fn().mockReturnValue(new Promise(() => {})), events: vi.fn().mockReturnValue(new Promise(() => {})) });
  await screen.findByText(/Fridge Cam/);
  expect(screen.queryByText(/Updated/)).not.toBeInTheDocument();
});

// Pointer hidden
test("the mouse pointer is hidden over the dashboard", async () => {
  renderTv();
  const dashboard = screen.getByRole("region", { name: "TV dashboard" });
  expect(getComputedStyle(dashboard).cursor).toBe("none");
});

// Out of stock
test("out-of-stock items are listed at the end of In the fridge", async () => {
  renderTv();
  expect(await within(await panel("In the fridge")).findByText("Out: soda can")).toBeInTheDocument();
});

// Condiment on the TV
test("condiments show a salt shaker on the TV", async () => {
  renderTv({ inventory: vi.fn().mockResolvedValue({ items: [item("ketchup", 1, "condiment")], pending_count: 0 }) });
  const row = await within(await panel("In the fridge")).findByRole("listitem");
  expect(row).toHaveTextContent("🧂");
  expect(row).not.toHaveTextContent("🫙");
});

// No-change openings collapse
test("back-to-back openings with no changes show as one row", async () => {
  renderTv({ events: vi.fn().mockResolvedValue({ events: [event(10), event(20), MILK_EVENT] }) });
  const recent = await panel("Recent changes");
  expect(await within(recent).findByText("2 openings · No changes")).toBeInTheDocument();
  expect(within(recent).getAllByRole("listitem")).toHaveLength(2);
});

// Time and duration
test("each row shows the clock time and seconds open", async () => {
  renderTv();
  const row = await within(await panel("Recent changes")).findByRole("listitem");
  expect(row).toHaveTextContent(`2 min ago · ${clockTime(MILK_EVENT.opened_at, deviceTimeZone())} · 20 s`);
});

// Open time today
test("Opens shows today's open time and the heatmap", async () => {
  renderTv();
  const opens = await panel("Opens");
  expect(await within(opens).findByText("Avg 20 s · Longest 20 s")).toBeInTheDocument();
  const heatmap = within(opens).getByRole("figure", { name: "Opens by day and hour" });
  expect(within(heatmap).getAllByRole("img")).toHaveLength(168);
  expect(within(heatmap).getAllByRole("img", { name: /: 1 open$/ })).toHaveLength(1);
});

const PROOF_EVENT = event(2, {
  changes: [
    { item: "milk", category: "dairy", direction: "added", quantity: 2, confidence: 0.9, applied: true, proof: ["https://s3/a.jpg", "https://s3/b.jpg"] },
    { item: "eggs", category: "dairy", direction: "removed", quantity: 1, confidence: 0.9, applied: true, proof: ["https://s3/c.jpg"] },
  ],
  stills: ["https://s3/1.jpg", "https://s3/2.jpg", "https://s3/3.jpg"],
});

const proofImages = (row: HTMLElement) => [...row.querySelectorAll("img")];

// Proof under the labels
test("a row shows each change's first proof photo, in label order, with empty alt", async () => {
  renderTv({ events: vi.fn().mockResolvedValue({ events: [PROOF_EVENT] }) });
  const row = await within(await panel("Recent changes")).findByRole("listitem");
  await within(row).findByText("+ 2 milk, − eggs");
  const imgs = proofImages(row);
  expect(imgs.map((i) => i.getAttribute("src"))).toEqual(["https://s3/a.jpg", "https://s3/c.jpg"]);
  for (const img of imgs) expect(img).toHaveAttribute("alt", "");
});

// No photos without changes
test("Checking… and No changes rows show no photos", async () => {
  const stills = ["https://s3/1.jpg"];
  renderTv({ events: vi.fn().mockResolvedValue({ events: [event(1, { status: "analyzing", stills }), event(30, { stills })] }) });
  const recent = await panel("Recent changes");
  await within(recent).findByText("Checking…");
  for (const row of within(recent).getAllByRole("listitem")) expect(proofImages(row)).toHaveLength(0);
});

// Broken link hidden
test("a proof photo that fails to load is removed, and the row stays", async () => {
  renderTv({ events: vi.fn().mockResolvedValue({ events: [PROOF_EVENT] }) });
  const row = await within(await panel("Recent changes")).findByRole("listitem");
  await within(row).findByText("+ 2 milk, − eggs");
  fireEvent.error(proofImages(row)[0]);
  expect(proofImages(row).map((i) => i.getAttribute("src"))).toEqual(["https://s3/c.jpg"]);
  expect(row).toHaveTextContent("+ 2 milk, − eggs");
});

function signed(sig: number): DoorEvent {
  return event(2, {
    changes: [{ item: "milk", category: "dairy", direction: "added", quantity: 1, confidence: 0.9, applied: true, proof: [`https://s3/a.jpg?X-Amz-Signature=${sig}`] }],
    stills: [`https://s3/3.jpg?sig=${sig}`],
  });
}

const recentImages = () => proofImages(within(screen.getByRole("region", { name: "Recent changes" })).getByRole("listitem"));

async function withRefresh(first: DoorEvent[], second: DoorEvent[], check: () => void) {
  vi.useFakeTimers();
  try {
    renderTv({ events: vi.fn().mockResolvedValueOnce({ events: first }).mockResolvedValue({ events: second }) });
    await act(async () => void vi.advanceTimersByTime(0));
    await act(async () => void vi.advanceTimersByTime(30_000));
    check();
  } finally {
    vi.useRealTimers();
  }
}

// Re-signed link kept
test("a re-signed link for a photo already shown keeps the old link", async () => {
  await withRefresh([signed(1)], [signed(2)], () => {
    expect(recentImages()[0]).toHaveAttribute("src", "https://s3/a.jpg?X-Amz-Signature=1");
  });
});

// Broken link hidden (comes back with a fresh link)
test("a photo that failed comes back with the next refresh's link", async () => {
  vi.useFakeTimers();
  try {
    renderTv({ events: vi.fn().mockResolvedValueOnce({ events: [signed(1)] }).mockResolvedValue({ events: [signed(2)] }) });
    await act(async () => void vi.advanceTimersByTime(0));
    fireEvent.error(recentImages()[0]);
    expect(recentImages()).toHaveLength(0);
    await act(async () => void vi.advanceTimersByTime(30_000));
    expect(recentImages()[0]).toHaveAttribute("src", "https://s3/a.jpg?X-Amz-Signature=2");
  } finally {
    vi.useRealTimers();
  }
});

// Icon shown
test("the header shows the app icon before the title", async () => {
  renderTv();
  const title = screen.getByRole("heading", { name: "FridgeSense" });
  const header = title.closest("header")!;
  const icon = header.querySelector('img[src="/icon.svg"]')!;
  expect(icon).toHaveAttribute("alt", "");
  expect(icon.compareDocumentPosition(title) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
});

// Icon shown while data fails
test("the icon and title show even when every load fails", async () => {
  const fail = () => vi.fn().mockRejectedValue(new ApiError(500));
  renderTv({ inventory: fail(), events: fail(), camera: fail() });
  expect(await screen.findByText("Camera: No Data")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "FridgeSense" }).closest("header")!.querySelector('img[src="/icon.svg"]')).not.toBeNull();
});

const pages = () => screen.getByRole("navigation", { name: "Pages" });
const currentPage = () => within(pages()).getAllByText(/Overview|Activity/).find((el) => el.getAttribute("aria-current") === "page")?.textContent;
const press = (key: string) => fireEvent.keyDown(window, { key });
const OVERVIEW = ["In the fridge", "Recent changes", "Opens"];

async function onActivity(overrides: Parameters<typeof renderTv>[0] = {}) {
  const rendered = renderTv(overrides);
  await within(await panel("Recent changes")).findByRole("listitem").catch(() => undefined);
  act(() => void press("ArrowRight"));
  return { ...rendered, activity: await panel("Activity") };
}

// Opens on the overview
test("the dashboard opens on the overview", async () => {
  renderTv();
  for (const name of OVERVIEW) expect(await panel(name)).toBeInTheDocument();
  expect(screen.queryByRole("region", { name: "Activity" })).not.toBeInTheDocument();
  expect(currentPage()).toBe("Overview");
});

// Right shows Activity
test("ArrowRight shows the Activity page and is default-prevented", async () => {
  renderTv();
  await panel("In the fridge");
  let handled = true;
  act(() => void (handled = press("ArrowRight")));
  expect(handled).toBe(false);
  expect(await panel("Activity")).toBeInTheDocument();
  for (const name of OVERVIEW) expect(screen.queryByRole("region", { name })).not.toBeInTheDocument();
  expect(currentPage()).toBe("Activity");
  expect(screen.getByRole("heading", { name: "FridgeSense" })).toBeInTheDocument();
});

// Left goes back
test("ArrowLeft goes back to the overview", async () => {
  await onActivity();
  let handled = true;
  act(() => void (handled = press("ArrowLeft")));
  expect(handled).toBe(false);
  for (const name of OVERVIEW) expect(await panel(name)).toBeInTheDocument();
  expect(currentPage()).toBe("Overview");
});

// Keys at the ends do nothing
test("ArrowLeft on the overview and ArrowRight on Activity change nothing", async () => {
  renderTv();
  await panel("In the fridge");
  act(() => void press("ArrowLeft"));
  expect(currentPage()).toBe("Overview");
  act(() => void press("ArrowRight"));
  act(() => void press("ArrowRight"));
  expect(currentPage()).toBe("Activity");
});

// No extra requests when paging
test("paging makes no extra requests", async () => {
  const { api } = await onActivity();
  act(() => void press("ArrowLeft"));
  await panel("In the fridge");
  expect(api.inventory).toHaveBeenCalledTimes(1);
  expect(api.events).toHaveBeenCalledTimes(1);
  expect(api.camera).toHaveBeenCalledTimes(1);
});

// Opening with changes, stills and proof (on screen)
test("the Activity page lists each opening with its stills and proof photos", async () => {
  const { activity } = await onActivity({ events: vi.fn().mockResolvedValue({ events: [PROOF_EVENT, event(30), event(40)] }) });
  const rows = within(activity).getAllByRole("listitem");
  expect(rows).toHaveLength(3);
  expect(rows[0]).toHaveTextContent(`Today · ${clockTime(PROOF_EVENT.opened_at, deviceTimeZone())} · 20 s`);
  expect(rows[0]).toHaveTextContent("+ 2 milk, − eggs");
  expect(proofImages(rows[0]).map((i) => i.getAttribute("src"))).toEqual([
    "https://s3/1.jpg",
    "https://s3/2.jpg",
    "https://s3/3.jpg",
    "https://s3/a.jpg",
    "https://s3/c.jpg",
  ]);
  for (const img of proofImages(rows[0])) expect(img).toHaveAttribute("alt", "");
  expect(rows[1]).toHaveTextContent("No changes");
  expect(rows[2]).toHaveTextContent("No changes");
});

// Nothing this week (on screen)
test("an empty week on the Activity page says so", async () => {
  const { activity } = await onActivity({ events: vi.fn().mockResolvedValue({ events: [] }) });
  expect(within(activity).getByText("No door openings this week")).toBeInTheDocument();
});

// Events fail (Activity)
test("the Activity page shows No Data when events fail", async () => {
  const { activity } = await onActivity({ events: vi.fn().mockRejectedValue(new ApiError(500)) });
  expect(await within(activity).findByText("No Data")).toBeInTheDocument();
});

// Broken Activity still hidden
test("an Activity still that fails to load is removed, and the row stays", async () => {
  const { activity } = await onActivity({ events: vi.fn().mockResolvedValue({ events: [PROOF_EVENT] }) });
  const row = within(activity).getByRole("listitem");
  fireEvent.error(proofImages(row)[0]);
  expect(proofImages(row).map((i) => i.getAttribute("src"))).toEqual(["https://s3/2.jpg", "https://s3/3.jpg", "https://s3/a.jpg", "https://s3/c.jpg"]);
  expect(row).toHaveTextContent("+ 2 milk, − eggs");
});

// No clips or video (Activity)
test("the Activity page shows no clip or video", async () => {
  await onActivity();
  const dashboard = screen.getByRole("region", { name: "TV dashboard" });
  expect(dashboard.querySelectorAll("video")).toHaveLength(0);
  expect(dashboard.innerHTML).not.toContain("clip.mp4");
});

// Only opening pictures and the icon shown (Activity)
test("the only pictures on the Activity page are the icon, stills and proof photos", async () => {
  await onActivity();
  const dashboard = screen.getByRole("region", { name: "TV dashboard" });
  const srcs = [...dashboard.querySelectorAll("img")].map((img) => img.getAttribute("src"));
  expect(srcs.sort()).toEqual(["/icon.svg", "https://s3/proof-1.jpg", "https://s3/still-1.jpg"]);
});

// Back is left to the TV app (Activity)
test("Escape on the Activity page is not handled and the page stays", async () => {
  location.hash = "#tv";
  await onActivity();
  const notHandled = fireEvent.keyDown(window, { key: "Escape", keyCode: 27 });
  expect(notHandled).toBe(true);
  expect(location.hash).toBe("#tv");
  expect(currentPage()).toBe("Activity");
  location.hash = "";
});
