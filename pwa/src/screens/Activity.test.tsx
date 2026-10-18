import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "../App";
import type { DoorEvent, Role } from "../api/types";
import { ApiError } from "../api/client";
import type { Api } from "../AppContext";
import { fakeApi, signedIn } from "../test-utils";

const opened = new Date();
opened.setHours(18, 2, 0, 0);

function event(overrides: Partial<DoorEvent> = {}): DoorEvent {
  return {
    id: "ev1",
    opened_at: opened.toISOString(),
    closed_at: new Date(opened.getTime() + 25_000).toISOString(),
    duration_s: 25,
    status: "done",
    pending_count: 0,
    stills: [],
    clip: null,
    changes: [
      { item: "milk", category: "dairy", direction: "added", quantity: 1, confidence: 0.92, applied: true },
      { item: "eggs", category: "dairy", direction: "removed", quantity: 2, confidence: 0.81, applied: true },
    ],
    ...overrides,
  };
}

function renderActivity(
  events: DoorEvent[],
  { role = "owner", ...overrides }: { role?: Role } & Partial<Record<keyof Api, unknown>> = {},
) {
  signedIn(role);
  location.hash = "#activity";
  const api = fakeApi({ eventsOn: vi.fn().mockResolvedValue({ events, next: null }), ...overrides });
  render(<App api={api} />);
  return api;
}

function midnight(daysFromToday = 0) {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  d.setDate(d.getDate() + daysFromToday);
  return d;
}

function dateValue(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

// Door opening shown
test("a door opening shows its time, duration and changes", async () => {
  renderActivity([event()]);
  const card = await screen.findByRole("article");
  expect(within(card).getByText("18:02")).toBeInTheDocument();
  expect(within(card).getByText("25 s")).toBeInTheDocument();
  expect(within(card).getByText("+ milk")).toBeInTheDocument();
  expect(within(card).getByText("− 2 eggs")).toBeInTheDocument();
});

test("unconfirmed changes are marked", async () => {
  renderActivity([
    event({
      pending_count: 1,
      changes: [
        { item: "chocolate bar", category: "snack", direction: "removed", quantity: 1, confidence: 0.62, applied: false },
      ],
    }),
  ]);
  const card = await screen.findByRole("article");
  expect(within(card).getByText("− chocolate bar")).toBeInTheDocument();
  expect(within(card).getByText("to confirm")).toBeInTheDocument();
});

// Stills
const STILLS = [1, 2, 3, 4].map((n) => `https://stills.example.com/still-${n}.jpg?sig=x`);

test("stills show with the first one featured, and open full size", async () => {
  renderActivity([event({ stills: STILLS })]);
  const card = await screen.findByRole("article");
  const thumbs = within(card).getAllByRole("button", { name: /Still \d of 4/ });
  expect(thumbs).toHaveLength(4);
  expect(thumbs[0]).toHaveAttribute("data-featured");
  expect(thumbs[1]).not.toHaveAttribute("data-featured");
  await userEvent.click(thumbs[2]);
  const dialog = screen.getByRole("dialog");
  expect(within(dialog).getByRole("img")).toHaveAttribute("src", STILLS[2]);
});

// Step through stills
test("the viewer steps to the next and previous still", async () => {
  renderActivity([event({ stills: STILLS })]);
  const card = await screen.findByRole("article");
  await userEvent.click(within(card).getByRole("button", { name: "Still 3 of 4" }));
  const dialog = screen.getByRole("dialog");
  await userEvent.click(within(dialog).getByRole("button", { name: "Next still" }));
  expect(within(dialog).getByRole("img")).toHaveAttribute("src", STILLS[3]);
  await userEvent.click(within(dialog).getByRole("button", { name: "Previous still" }));
  expect(within(dialog).getByRole("img")).toHaveAttribute("src", STILLS[2]);
  await userEvent.click(within(dialog).getByRole("button", { name: "Previous still" }));
  expect(within(dialog).getByRole("img")).toHaveAttribute("src", STILLS[1]);
  expect(within(dialog).getByRole("heading", { name: "Still 2 of 4" })).toBeInTheDocument();
});

// Viewer at the ends
test("the viewer can't step past the first or last still", async () => {
  renderActivity([event({ stills: STILLS })]);
  const card = await screen.findByRole("article");
  await userEvent.click(within(card).getByRole("button", { name: "Still 1 of 4" }));
  expect(within(screen.getByRole("dialog")).getByRole("button", { name: "Previous still" })).toBeDisabled();
  await userEvent.keyboard("{Escape}");
  await userEvent.click(within(card).getByRole("button", { name: "Still 4 of 4" }));
  expect(within(screen.getByRole("dialog")).getByRole("button", { name: "Next still" })).toBeDisabled();
});

const CLIP = "https://stills.example.com/clip.mp4?sig=x#t=0.5,8.5";

// Clip instead of stills
test("an event with a clip plays it instead of showing stills", async () => {
  renderActivity([event({ clip: CLIP, stills: STILLS })]);
  const video = (await screen.findByLabelText("Door opening at 18:02")) as HTMLVideoElement;
  expect(video.tagName).toBe("VIDEO");
  expect(video.getAttribute("src")).toBe(CLIP);
  expect(video.muted).toBe(true);
  expect(video.controls).toBe(true);
  expect(video.hasAttribute("playsinline")).toBe(true);
  expect(video.autoplay).toBe(false);
  expect(video.getAttribute("poster")).toBe(STILLS[0]);
  expect(screen.queryByRole("button", { name: /Still \d of/ })).toBeNull();
  expect(document.querySelector("[data-stills]")).toBeNull();
});

// Clip without stills
test("a clip without stills has no poster", async () => {
  renderActivity([event({ clip: CLIP, stills: [] })]);
  const video = await screen.findByLabelText("Door opening at 18:02");
  expect(video.hasAttribute("poster")).toBe(false);
});

// Clip fails to load
test("a clip that fails to load falls back to the stills", async () => {
  renderActivity([event({ clip: CLIP, stills: STILLS })]);
  const video = await screen.findByLabelText("Door opening at 18:02");
  fireEvent.error(video);
  expect(await screen.findAllByRole("button", { name: /Still \d of 4/ })).toHaveLength(4);
  expect(screen.queryByLabelText("Door opening at 18:02")).toBeNull();
});

// No stills
test("an event without stills shows no still area", async () => {
  renderActivity([event({ stills: [], clip: null })]);
  const card = await screen.findByRole("article");
  expect(within(card).queryByRole("button", { name: /Still/ })).not.toBeInTheDocument();
  expect(card.querySelector("[data-stills]")).toBeNull();
});

// Failed analysis
test("a failed analysis says so instead of listing changes", async () => {
  renderActivity([event({ status: "analysis_failed", changes: [] })]);
  const card = await screen.findByRole("article");
  expect(within(card).getByText("Couldn't tell what changed")).toBeInTheDocument();
});

// No door openings
test("a day without door openings says so and keeps the day picker", async () => {
  renderActivity([]);
  expect(await screen.findByText("No door openings on this day.")).toBeInTheDocument();
  expect(screen.getByLabelText("Day")).toBeInTheDocument();
});

// Today by default
test("Activity shows today, 10 at a time, and can't pick a later day", async () => {
  const api = renderActivity([event()]);
  await screen.findByRole("article");
  const picker = screen.getByLabelText("Day");
  expect(picker).toHaveValue(dateValue(midnight()));
  expect(picker).toHaveAttribute("max", dateValue(midnight()));
  expect(api.eventsOn).toHaveBeenCalledWith(midnight(), midnight(1), 10, undefined);
});

// Pick a day
test("picking yesterday asks for yesterday's openings from page 1", async () => {
  const api = renderActivity([event()]);
  await screen.findByRole("article");
  fireEvent.change(screen.getByLabelText("Day"), { target: { value: dateValue(midnight(-1)) } });
  await waitFor(() => expect(api.eventsOn).toHaveBeenLastCalledWith(midnight(-1), midnight(), 10, undefined));
  expect(screen.getByLabelText("Day")).toHaveValue(dateValue(midnight(-1)));
});

// Older and newer pages
test("Older and Newer step through pages with the cursor", async () => {
  const eventsOn = vi.fn(async (_from: Date, _to: Date, _limit: number, cursor?: string) =>
    cursor === "c1"
      ? { events: [event({ id: "ev2", opened_at: new Date(opened.getTime() - 3600_000).toISOString() })], next: null }
      : { events: [event()], next: "c1" },
  );
  renderActivity([], { eventsOn });
  expect(await screen.findByText("18:02")).toBeInTheDocument();
  expect(screen.getByText("Page 1")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Newer" })).toBeDisabled();
  await userEvent.click(screen.getByRole("button", { name: "Older" }));
  expect(await screen.findByText("17:02")).toBeInTheDocument();
  expect(eventsOn).toHaveBeenLastCalledWith(midnight(), midnight(1), 10, "c1");
  expect(screen.getByText("Page 2")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Older" })).toBeDisabled();
  await userEvent.click(screen.getByRole("button", { name: "Newer" }));
  expect(await screen.findByText("18:02")).toBeInTheDocument();
  expect(screen.getByText("Page 1")).toBeInTheDocument();
  expect(eventsOn).toHaveBeenLastCalledWith(midnight(), midnight(1), 10, undefined);
});

// Single page
test("a single page disables Older and Newer", async () => {
  renderActivity([event()]);
  await screen.findByRole("article");
  expect(screen.getByRole("button", { name: "Older" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Newer" })).toBeDisabled();
});

// Delete an opening
test("the owner deletes a door opening after confirming", async () => {
  const eventsOn = vi.fn().mockResolvedValueOnce({ events: [event()], next: null }).mockResolvedValue({ events: [], next: null });
  const api = renderActivity([], { eventsOn });
  const card = await screen.findByRole("article");
  await userEvent.click(within(card).getByRole("button", { name: "Delete door opening at 18:02" }));
  const dialog = screen.getByRole("dialog", { name: "Delete this door opening?" });
  await userEvent.click(within(dialog).getByRole("button", { name: "Delete" }));
  expect(api.deleteEvent).toHaveBeenCalledWith("ev1");
  await waitFor(() => expect(screen.queryByRole("article")).not.toBeInTheDocument());
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

// Cancel delete
test("cancelling the delete keeps the door opening", async () => {
  const api = renderActivity([event()]);
  const card = await screen.findByRole("article");
  await userEvent.click(within(card).getByRole("button", { name: "Delete door opening at 18:02" }));
  await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Cancel" }));
  expect(api.deleteEvent).not.toHaveBeenCalled();
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(screen.getByRole("article")).toBeInTheDocument();
});

// Viewer can't delete
test("a viewer sees no delete button", async () => {
  renderActivity([event()], { role: "viewer" });
  const card = await screen.findByRole("article");
  expect(within(card).queryByRole("button", { name: /Delete/ })).not.toBeInTheDocument();
});

// No camera linked
test("a 409 shows No Data instead of the skeleton", async () => {
  signedIn();
  location.hash = "#activity";
  render(<App api={fakeApi({ eventsOn: vi.fn().mockRejectedValue(new ApiError(409)) })} />);
  expect(await screen.findByText("No Data")).toBeInTheDocument();
  expect(screen.queryByTestId("loading")).not.toBeInTheDocument();
});

// Later poll fails
test("door openings stay listed when a later poll fails", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.spyOn(console, "error").mockImplementation(() => {});
  try {
    signedIn();
    location.hash = "#activity";
    const events = vi.fn().mockResolvedValueOnce({ events: [event()], next: null }).mockRejectedValue(new ApiError(500));
    render(<App api={fakeApi({ eventsOn: events })} />);
    expect(await screen.findByRole("article")).toBeInTheDocument();
    await act(() => vi.advanceTimersByTimeAsync(10_000));
    expect(events).toHaveBeenCalledTimes(2);
    expect(screen.getByRole("article")).toBeInTheDocument();
    expect(screen.queryByText("No Data")).not.toBeInTheDocument();
  } finally {
    vi.useRealTimers();
  }
});

// Stable still links on Activity
describe("still links across polls", () => {
  const links = (tag: string, n = 4) =>
    Array.from({ length: n }, (_, i) => `https://stills.example.com/still-${i + 1}.jpg?sig=${tag}`);
  const shownSrcs = () =>
    Array.from(document.querySelectorAll("[data-stills] img")).map((img) => img.getAttribute("src"));

  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  async function poll(ms = 10_000) {
    await act(async () => void vi.advanceTimersByTime(ms));
  }

  function renderPolls(events: ReturnType<typeof vi.fn>) {
    signedIn();
    location.hash = "#activity";
    render(<App api={fakeApi({ eventsOn: events })} />);
  }

  // Poll with fresh links
  test("a poll with fresh links keeps the links on screen", async () => {
    const events = vi
      .fn()
      .mockResolvedValueOnce({ events: [event({ stills: links("a") })], next: null })
      .mockResolvedValue({ events: [event({ stills: links("b") })], next: null });
    renderPolls(events);
    await act(async () => {});
    expect(shownSrcs()).toEqual(links("a"));
    await poll();
    expect(events).toHaveBeenCalledTimes(2);
    expect(shownSrcs()).toEqual(links("a"));
  });

  // Links refreshed after 10 minutes
  test("links older than 10 minutes are replaced by the latest poll", async () => {
    let tag = "a";
    const events = vi.fn(async () => ({ events: [event({ stills: links(tag) })], next: null }));
    renderPolls(events);
    await act(async () => {});
    tag = "b";
    await poll(9 * 60_000);
    expect(shownSrcs()).toEqual(links("a"));
    tag = "c";
    await poll(60_000 + 10_000);
    expect(shownSrcs()).toEqual(links("c"));
  });

  // Poll with fresh proof links
  test("a poll with fresh proof links keeps the proof on screen", async () => {
    const withProof = (tag: string) =>
      event({ stills: links(tag), changes: [{ item: "soda", category: "beverage", direction: "added", quantity: 1, confidence: 0.9, applied: true, proof: links(tag, 2) }] });
    const events = vi
      .fn()
      .mockResolvedValueOnce({ events: [withProof("a")], next: null })
      .mockResolvedValue({ events: [withProof("b")], next: null });
    renderPolls(events);
    await act(async () => {});
    const proofSrcs = () =>
      Array.from(document.querySelectorAll('[aria-label="Proof"] img')).map((img) => img.getAttribute("src"));
    expect(proofSrcs()).toEqual(links("a", 2));
    await poll();
    expect(events).toHaveBeenCalledTimes(2);
    expect(proofSrcs()).toEqual(links("a", 2));
  });

  // Poll with a fresh clip link
  test("a poll with a fresh clip link keeps the clip on screen", async () => {
    const clip = (tag: string) => `https://stills.example.com/clip.mp4?sig=${tag}#t=0.5,8.5`;
    const events = vi
      .fn()
      .mockResolvedValueOnce({ events: [event({ stills: links("a"), clip: clip("a") })], next: null })
      .mockResolvedValue({ events: [event({ stills: links("b"), clip: clip("b") })], next: null });
    renderPolls(events);
    await act(async () => {});
    const video = document.querySelector("video")!;
    expect(video.getAttribute("src")).toBe(clip("a"));
    await poll();
    expect(events).toHaveBeenCalledTimes(2);
    expect(document.querySelector("video")).toBe(video); // not reloaded
    expect(video.getAttribute("src")).toBe(clip("a"));
  });

  // Clip appears
  test("a clip that appears on a later poll is shown", async () => {
    const events = vi
      .fn()
      .mockResolvedValueOnce({ events: [event({ stills: links("a"), clip: null })], next: null })
      .mockResolvedValue({ events: [event({ stills: links("b"), clip: "https://c/clip.mp4?sig=v1" })], next: null });
    renderPolls(events);
    await act(async () => {});
    expect(document.querySelector("video")).toBeNull();
    await poll();
    expect(document.querySelector("video")?.getAttribute("src")).toBe("https://c/clip.mp4?sig=v1");
  });

  // Still count changes
  test("a change in the number of stills shows the new links", async () => {
    const events = vi
      .fn()
      .mockResolvedValueOnce({ events: [event({ stills: links("a", 2) })], next: null })
      .mockResolvedValue({ events: [event({ stills: links("b", 4) })], next: null });
    renderPolls(events);
    await act(async () => {});
    expect(shownSrcs()).toEqual(links("a", 2));
    await poll();
    expect(shownSrcs()).toEqual(links("b", 4));
  });
});

// Owner follows the link
test("the owner's Debug link opens the door opening's trace", async () => {
  const api = renderActivity([event({ id: "xyz" })]);
  const card = await screen.findByRole("article");
  await userEvent.click(within(card).getByRole("link", { name: "Debug door opening at 18:02" }));
  await waitFor(() => expect(api.debugMotion).toHaveBeenCalledWith("xyz"));
  expect(location.hash).toBe("#config/debug/xyz");
  location.hash = "";
});

// Viewer has no link
test("a viewer sees no Debug link", async () => {
  renderActivity([event()], { role: "viewer" });
  const card = await screen.findByRole("article");
  expect(within(card).queryByRole("link", { name: /Debug/ })).not.toBeInTheDocument();
});

// No Debug link for users
test("a user can delete an opening but sees no Debug link", async () => {
  renderActivity([event()], { role: "user" });
  const card = await screen.findByRole("article");
  expect(within(card).getByRole("button", { name: /Delete/ })).toBeInTheDocument();
  expect(within(card).queryByRole("link", { name: /Debug/ })).not.toBeInTheDocument();
});

// Scenario: Button for every role
test("the owner sees a Livestream button", async () => {
  renderActivity([event()], { role: "owner" });
  expect(await screen.findByRole("button", { name: "Livestream" })).toBeInTheDocument();
});

test.each(["user", "viewer"] as const)("the %s sees no Livestream button", async (role) => {
  renderActivity([event()], { role });
  expect(await screen.findByLabelText("Day")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Livestream" })).not.toBeInTheDocument();
});

test("the Livestream button opens the Livestream dialog", async () => {
  const api = renderActivity([event()], { role: "owner", camera: vi.fn().mockResolvedValue({ name: "Fridge", online: true }) });
  await userEvent.click(await screen.findByRole("button", { name: "Livestream" }));
  expect(screen.getByRole("dialog", { name: "Livestream" })).toBeInTheDocument();
  // jsdom has no WebRTC, so after the online check the dialog says so instead of calling the API.
  expect(await screen.findByText("This browser can't play live video.")).toBeInTheDocument();
  expect(api.startLive).not.toHaveBeenCalled();
  await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Close" }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

const PROOF = ["https://s3.test/still-3.jpg?sig", "https://s3.test/still-4.jpg?sig"];
const SODA = { item: "soda", category: "beverage", direction: "added" as const, quantity: 1, confidence: 0.9, applied: true };
const EGGS = { item: "eggs", category: "dairy", direction: "removed" as const, quantity: 2, confidence: 0.81, applied: true };
const strip = () => screen.findByRole("region", { name: "Proof" });

// Scenario: Proof beside the clip
test("proof stills show beside the clip", async () => {
  renderActivity([event({ clip: "https://s3.test/clip.mp4#t=0.5,8.5", changes: [{ ...SODA, proof: PROOF }] })]);
  const proof = await strip();
  expect(screen.getByLabelText(/^Door opening at/)).toBeInTheDocument();
  expect(within(proof).getByRole("button", { name: "Proof for + soda, 1 of 2" })).toBeInTheDocument();
  expect(within(proof).getByRole("button", { name: "Proof for + soda, 2 of 2" })).toBeInTheDocument();
});

// Scenario: Several changes
test("the proof strip shows every change's proof, captioned", async () => {
  renderActivity([event({ changes: [{ ...SODA, proof: [PROOF[0]] }, { ...EGGS, proof: PROOF }] })]);
  const proof = await strip();
  expect(within(proof).getAllByRole("button")).toHaveLength(3);
  expect(within(proof).getByText("+ soda")).toBeInTheDocument();
  expect(within(proof).getByText("− 2 eggs")).toBeInTheDocument();
});

// Scenario: No proof
test("an event without proof shows no proof strip", async () => {
  renderActivity([event({ clip: "https://s3.test/clip.mp4#t=0.5,8.5", changes: [{ ...SODA, proof: [] }, SODA] })]);
  await screen.findByRole("article");
  expect(screen.queryByRole("region", { name: "Proof" })).not.toBeInTheDocument();
});

// Scenario: Proof with stills
test("proof shows alongside the stills when there is no clip", async () => {
  renderActivity([event({ stills: STILLS, changes: [{ ...SODA, proof: [STILLS[2]] }] })]);
  const proof = await strip();
  expect(screen.getAllByRole("button", { name: /^Still \d of 4$/ })).toHaveLength(4);
  expect(within(proof).getAllByRole("button")).toHaveLength(1);
});

// Scenario: Layout by width
test("the media and proof sit in a grid that splits into two columns at sm", async () => {
  renderActivity([event({ clip: "https://s3.test/clip.mp4#t=0.5,8.5", changes: [{ ...SODA, proof: PROOF }] })]);
  const proof = await strip();
  const grid = proof.parentElement!;
  expect(grid).toHaveClass("grid", "grid-cols-1", "sm:grid-cols-[2fr_1fr]");
  expect(grid.lastElementChild).toBe(proof);
});

// Scenario: Tap a proof still
test("tapping a proof still opens it in the viewer with proof titles", async () => {
  renderActivity([event({ changes: [{ ...SODA, proof: [PROOF[0]] }, { ...EGGS, proof: PROOF }] })]);
  const proof = await strip();
  await userEvent.click(within(proof).getByRole("button", { name: "Proof for − 2 eggs, 2 of 2" }));
  const dialog = screen.getByRole("dialog");
  expect(within(dialog).getByRole("img")).toHaveAttribute("src", PROOF[1]);
  expect(within(dialog).getByRole("button", { name: "Next still" })).toBeDisabled();
  await userEvent.click(within(dialog).getByRole("button", { name: "Previous still" }));
  expect(within(dialog).getByRole("heading", { name: "Proof for − 2 eggs, 1 of 2" })).toBeInTheDocument();
  expect(within(dialog).getByRole("img")).toHaveAttribute("src", PROOF[0]);
});
