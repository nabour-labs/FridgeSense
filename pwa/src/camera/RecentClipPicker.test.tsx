import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApiError } from "../api/client";
import type { DoorEvent } from "../api/types";
import { RecentClipPicker } from "./RecentClipPicker";

function at(daysAgo: number, hour: number, minute: number): string {
  const d = new Date();
  d.setDate(d.getDate() - daysAgo);
  d.setHours(hour, minute, 0, 0);
  return d.toISOString();
}

function event(id: string, opened_at: string, duration_s: number, clip: string | null): DoorEvent {
  return {
    id,
    opened_at,
    closed_at: opened_at,
    duration_s,
    status: "done",
    changes: [],
    pending_count: 0,
    stills: [],
    clip,
  };
}

const V1 = "https://stills.example.com/a/clip.mp4?sig=1#t=0.5,8.5";
const V2 = "https://stills.example.com/b/clip.mp4?sig=2#t=1,5";
const EVENTS = [
  event("e1", at(0, 18, 2), 25, V1),
  event("e2", at(0, 9, 15), 10, null),
  event("e3", at(1, 20, 40), 12, V2),
];
const BLURRED = { image: "BLURRED", captured_at: "2026-10-17T18:02:00.000Z" };

function renderPicker(
  { events = EVENTS, cameraFrame = vi.fn().mockResolvedValue(BLURRED), grab = vi.fn(async () => "RAWFRAME") } = {} as {
    events?: DoorEvent[];
    cameraFrame?: ReturnType<typeof vi.fn>;
    grab?: ReturnType<typeof vi.fn>;
  },
) {
  const api = { events: vi.fn().mockResolvedValue({ events }), cameraFrame };
  const onPick = vi.fn();
  const onCancel = vi.fn();
  const report = vi.fn();
  render(<RecentClipPicker api={api} onPick={onPick} onCancel={onCancel} report={report} grab={grab} />);
  return { api, onPick, onCancel, report, grab };
}

const video = () => screen.getByTestId("clip-video") as HTMLVideoElement;

function loaded() {
  Object.defineProperty(video(), "duration", { value: 9, configurable: true });
  fireEvent.loadedMetadata(video());
  fireEvent.loadedData(video());
}

// Recent clips listed
it("lists the last 7 days' openings with a clip, newest first, the first one playing cross-origin", async () => {
  const { api } = renderPicker();
  const box = await screen.findByRole("combobox", { name: "Clip" });
  expect(api.events).toHaveBeenCalledWith(7);
  expect(box).toHaveTextContent("Today 18:02 · 25 s");
  expect(video()).toHaveAttribute("src", V1);
  expect(video()).toHaveAttribute("crossorigin", "anonymous");
  await userEvent.click(box);
  expect(screen.getAllByRole("option").map((o) => o.textContent)).toEqual([
    "Today 18:02 · 25 s",
    "Yesterday 20:40 · 12 s",
  ]);
  await userEvent.click(screen.getByRole("option", { name: "Yesterday 20:40 · 12 s" }));
  expect(video()).toHaveAttribute("src", V2);
});

// Add a reference from a recent clip (the picker's part)
it("Use this frame sends the grabbed frame to be blurred and returns only the blurred image", async () => {
  const { api, onPick, grab } = renderPicker();
  await screen.findByRole("combobox", { name: "Clip" });
  const use = screen.getByRole("button", { name: "Use this frame" });
  expect(use).toBeDisabled();
  loaded();
  await userEvent.click(use);
  expect(grab).toHaveBeenCalledWith(video());
  expect(api.cameraFrame).toHaveBeenCalledWith("RAWFRAME");
  await waitFor(() => expect(onPick).toHaveBeenCalledWith(BLURRED));
});

// No recent clips
it("says so when no recent opening has a clip, and Use this frame is disabled", async () => {
  renderPicker({ events: [event("e2", at(0, 9, 15), 10, null)] });
  expect(await screen.findByText("No door openings with a clip in the last 7 days.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Use this frame" })).toBeDisabled();
});

// Recent clip won't load
it("says so when the clip won't load, and Use this frame is disabled", async () => {
  renderPicker();
  await screen.findByRole("combobox", { name: "Clip" });
  loaded();
  fireEvent.error(video());
  expect(screen.getByText("This clip can't be played")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Use this frame" })).toBeDisabled();
});

// Frame can't be grabbed
it("says so when the frame can't be drawn, and sends nothing", async () => {
  const { api, onPick } = renderPicker({
    grab: vi.fn(async () => {
      throw new DOMException("tainted", "SecurityError");
    }),
  });
  await screen.findByRole("combobox", { name: "Clip" });
  loaded();
  await userEvent.click(screen.getByRole("button", { name: "Use this frame" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("This frame can't be used. Try another clip.");
  expect(api.cameraFrame).not.toHaveBeenCalled();
  expect(onPick).not.toHaveBeenCalled();
});

// Faces can't be blurred
it("says so when faces can't be blurred, and returns no image", async () => {
  const { onPick, report } = renderPicker({
    cameraFrame: vi.fn().mockRejectedValue(new ApiError(502, "camera unavailable")),
  });
  await screen.findByRole("combobox", { name: "Clip" });
  loaded();
  await userEvent.click(screen.getByRole("button", { name: "Use this frame" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Faces couldn't be blurred, so this frame can't be used.");
  expect(onPick).not.toHaveBeenCalled();
  expect(report).not.toHaveBeenCalled();
});

it("reports any other error", async () => {
  const boom = new Error("boom");
  const { report } = renderPicker({ cameraFrame: vi.fn().mockRejectedValue(boom) });
  await screen.findByRole("combobox", { name: "Clip" });
  loaded();
  await userEvent.click(screen.getByRole("button", { name: "Use this frame" }));
  await waitFor(() => expect(report).toHaveBeenCalledWith(boom));
});

// Cancel the recent clip picker
it("Cancel closes without a request", async () => {
  const { api, onCancel, onPick } = renderPicker();
  await screen.findByRole("combobox", { name: "Clip" });
  await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
  expect(onCancel).toHaveBeenCalledTimes(1);
  expect(api.cameraFrame).not.toHaveBeenCalled();
  expect(onPick).not.toHaveBeenCalled();
});
