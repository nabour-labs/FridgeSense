import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApiError } from "../api/client";
import type { CameraInfo, Role } from "../api/types";
import { AppContext, type Api } from "../AppContext";
import { fakeApi } from "../test-utils";
import { clock, dayLabel } from "../format";
import { Camera } from "./Camera";

const INFO: CameraInfo = {
  device_id: "ava1.ring.device.D1",
  name: "Fridge Cam",
  image_url: "https://example.test/device_3x.png",
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
  history: [],
  uptime: { window_days: 30, percent: null, since: null },
  checked_at: "2026-10-16T12:00:00.000Z",
  monitoring: { paused: false, since: null },
};

function renderCamera(
  camera: Api["camera"],
  extra: Partial<Record<keyof Api, unknown>> = {},
  createPeer?: () => RTCPeerConnection | null,
  role: Role = "viewer",
) {
  const api = fakeApi({ camera, ...extra });
  const report = vi.fn();
  render(
    <AppContext.Provider value={{ api, role, report, online: vi.fn(), go: vi.fn() }}>
      <Camera createPeer={createPeer} />
    </AppContext.Provider>,
  );
  return { api, report };
}

/** A peer whose video arrives on demand and whose stats describe an H.264 stream. */
class StatsPeer {
  iceGatheringState = "complete";
  connectionState = "new";
  localDescription: RTCSessionDescriptionInit | null = null;
  ontrack: ((e: { streams: MediaStream[] }) => void) | null = null;
  onconnectionstatechange: (() => void) | null = null;
  addTransceiver() {}
  async createOffer() {
    return { type: "offer" as const, sdp: "v=0\r\n" };
  }
  async setLocalDescription(d: RTCSessionDescriptionInit) {
    this.localDescription = d;
  }
  async setRemoteDescription() {}
  close() {}
  async getStats() {
    return new Map<string, Record<string, unknown>>([
      ["V1", { type: "inbound-rtp", kind: "video", codecId: "C1", decoderImplementation: "ExternalDecoder", frameWidth: 1920, frameHeight: 1080, framesPerSecond: 15 }],
      ["C1", { type: "codec", mimeType: "video/H264" }],
    ]);
  }
  track() {
    act(() => this.ontrack?.({ streams: [{ id: "stream" } as unknown as MediaStream] }));
  }
  fail() {
    this.connectionState = "failed";
    act(() => this.onconnectionstatechange?.());
  }
}

const LIVE = { startLive: vi.fn().mockResolvedValue({ answer: "v=0\r\nanswer\r\n", session_id: "S1", max_seconds: 60 }) };
const CHECK_HINT = "Run a check to see how this browser decodes the camera's video.";

async function checkDecoder() {
  const peers: StatsPeer[] = [];
  const createPeer = () => {
    const p = new StatsPeer();
    peers.push(p);
    return p as unknown as RTCPeerConnection;
  };
  renderCamera(vi.fn().mockResolvedValue(INFO), LIVE, createPeer);
  await userEvent.click(await screen.findByRole("button", { name: "Check decoder" }));
  await waitFor(() => expect(peers[0]?.localDescription).not.toBeNull());
  return peers;
}

function closeDialog() {
  fireEvent.click(within(screen.getByRole("dialog", { name: "Livestream" })).getByRole("button", { name: "Close" }));
}

/** The value shown next to a detail's label. */
function value(label: string) {
  return screen.getByText(label, { selector: "dt" }).nextElementSibling?.textContent;
}

// Scenario: Camera tab shows details
test("the camera tab shows the camera's details", async () => {
  renderCamera(vi.fn().mockResolvedValue(INFO));
  expect(await screen.findByRole("heading", { name: "Fridge Cam" })).toBeInTheDocument();
  expect(screen.getByTestId("camera-status")).toHaveTextContent("Online");
  expect(screen.getByRole("img", { name: "Fridge Cam" })).toHaveAttribute("src", INFO.image_url);
  expect(value("Manufacturer")).toBe("Ring");
  expect(value("Video codecs")).toBe("AVC");
  expect(value("Aspect ratio")).toBe("16:9");
  expect(value("Max resolution")).toBe("1080p");
  expect(value("Supported resolutions")).toBe("1080p");
  expect(value("HDR")).toBe("On");
  expect(value("Color night vision")).toBe("Off");
  expect(value("Motion detection")).toBe("On");
  expect(value("End-to-end encryption")).toBe("Off");
  expect(value("Location")).toBe("WA, US");
});

test("the camera details have no edit controls for anyone", async () => {
  renderCamera(vi.fn().mockResolvedValue(INFO));
  await screen.findByRole("heading", { name: "Fridge Cam" });
  expect(screen.queryByRole("button", { name: /save|delete|add/i })).not.toBeInTheDocument();
});

// Scenario: Only the two switches are editable
test("for the owner the FridgeSense and blur switches are the only controls that change data", async () => {
  renderCamera(vi.fn().mockResolvedValue(INFO), {}, undefined, "owner");
  await screen.findByRole("heading", { name: "Fridge Cam" });
  expect(screen.queryByRole("button", { name: /save|delete|add/i })).not.toBeInTheDocument();
  await screen.findAllByRole("switch");
  const switches = screen.getAllByRole("switch");
  expect(switches).toHaveLength(2);
  expect(switches[0]).toHaveAccessibleName("FridgeSense");
  expect(switches[1]).toHaveAccessibleName("Blur faces");
  await waitFor(() => switches.forEach((s) => expect(s).toBeEnabled()));
});

// Scenario: Owner sees it on by default
test("the owner sees Blur faces on by default", async () => {
  renderCamera(vi.fn().mockResolvedValue(INFO), {}, undefined, "owner");
  const toggle = await screen.findByRole("switch", { name: "Blur faces" });
  await waitFor(() => expect(toggle).toHaveAttribute("aria-checked", "true"));
  expect(toggle).toBeEnabled();
  expect(screen.getByText("Blurs faces in stored stills, snapshots and debug traces. Livestream is never blurred.")).toBeInTheDocument();
  expect(screen.queryByText("Faces are stored as recorded for 7 days.")).not.toBeInTheDocument();
});

// Scenario: Owner turns it off
test("the owner turns Blur faces off", async () => {
  const { api } = renderCamera(vi.fn().mockResolvedValue(INFO), {}, undefined, "owner");
  const toggle = await screen.findByRole("switch", { name: "Blur faces" });
  await waitFor(() => expect(toggle).toBeEnabled());
  await userEvent.click(toggle);
  expect(api.setFaceBlur).toHaveBeenCalledWith(false);
  await waitFor(() => expect(toggle).toHaveAttribute("aria-checked", "false"));
  expect(await screen.findByText("Faces are stored as recorded for 7 days.")).toBeInTheDocument();
});

// Scenario: Save fails
test("a failed save turns Blur faces back on", async () => {
  const error = new ApiError(500);
  const { api, report } = renderCamera(
    vi.fn().mockResolvedValue(INFO),
    { setFaceBlur: vi.fn().mockRejectedValue(error) },
    undefined,
    "owner",
  );
  const toggle = await screen.findByRole("switch", { name: "Blur faces" });
  await waitFor(() => expect(toggle).toBeEnabled());
  await userEvent.click(toggle);
  expect(api.setFaceBlur).toHaveBeenCalledWith(false);
  await waitFor(() => expect(toggle).toHaveAttribute("aria-checked", "true"));
  expect(report).toHaveBeenCalledWith(error);
});

// Scenario: Others see it read-only
test.each(["user", "viewer"] as const)("the %s sees Blur faces read-only", async (role) => {
  const { api } = renderCamera(
    vi.fn().mockResolvedValue(INFO),
    { faceBlur: vi.fn().mockResolvedValue({ enabled: false }) },
    undefined,
    role,
  );
  const toggle = await screen.findByRole("switch", { name: "Blur faces" });
  await waitFor(() => expect(toggle).toHaveAttribute("aria-checked", "false"));
  expect(toggle).toBeDisabled();
  await userEvent.click(toggle);
  expect(api.setFaceBlur).not.toHaveBeenCalled();
});

// Scenario: Camera offline
test("an offline camera shows an Offline badge", async () => {
  renderCamera(vi.fn().mockResolvedValue({ ...INFO, online: false }));
  expect(await screen.findByTestId("camera-status")).toHaveTextContent("Offline");
});

// Scenario: Ring unreachable
test("when Ring is unreachable the saved details show with an Unknown badge", async () => {
  renderCamera(
    vi.fn().mockResolvedValue({
      ...INFO,
      name: "Fridge",
      image_url: null,
      online: null,
      video: null,
      image_enhancements: null,
      motion_detection: null,
      e2e_encryption: null,
      location: null,
      ring: "unavailable",
    }),
  );
  expect(await screen.findByTestId("camera-status")).toHaveTextContent("Unknown");
  expect(screen.getByText("Could not reach the camera service. Showing saved details.")).toBeInTheDocument();
  expect(value("Video codecs")).toBe("Not reported");
  expect(value("Aspect ratio")).toBe("Not reported");
  expect(value("Motion detection")).toBe("Not reported");
});

// Scenario: No camera linked
test("with no camera linked the tab says so, without an error notice", async () => {
  const { report } = renderCamera(vi.fn().mockRejectedValue(new ApiError(409, "no camera linked")));
  expect(await screen.findByText("No camera is linked yet.")).toBeInTheDocument();
  expect(report).not.toHaveBeenCalled();
});

// Scenario: History listed
test("the online history shows uptime, the changes and a timeline", async () => {
  renderCamera(
    vi.fn().mockResolvedValue({
      ...INFO,
      history: [
        { online: true, at: "2026-10-16T06:00:00.000Z", source: "webhook" },
        { online: false, at: "2026-10-16T00:00:00.000Z", source: "webhook" },
      ],
      uptime: { window_days: 30, percent: 99.2, since: "2026-09-16T12:00:00.000Z" },
    }),
  );
  expect(await screen.findByText("99.2% online")).toBeInTheDocument();
  const items = within(screen.getByRole("list", { name: "Status changes" })).getAllByRole("listitem");
  expect(items).toHaveLength(2);
  expect(items[0]).toHaveTextContent("Online");
  expect(items[1]).toHaveTextContent("Offline");
  expect(screen.getAllByTestId("timeline-offline")).toHaveLength(1);
});

// Scenario: Empty history
test("with no history the tab says none is recorded", async () => {
  renderCamera(vi.fn().mockResolvedValue(INFO));
  expect(await screen.findByText("No status changes recorded yet.")).toBeInTheDocument();
});

// Scenario: Before any check
test("before a check the decoder card explains itself", async () => {
  renderCamera(vi.fn().mockResolvedValue(INFO));
  expect(await screen.findByText(CHECK_HINT)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Check decoder" })).toBeInTheDocument();
});

// Scenario: Decoder values after a check
test("after a check the decoder card shows the browser's decoder", async () => {
  const peers = await checkDecoder();
  await waitFor(() => expect(peers[0].ontrack).not.toBeNull());
  await waitFor(() => expect(LIVE.startLive).toHaveBeenCalled());
  await act(() => new Promise((r) => setTimeout(r, 0)));
  peers[0].track();
  await act(() => new Promise((r) => setTimeout(r, 1_200)));
  closeDialog();
  expect(screen.queryByRole("dialog", { name: "Livestream" })).not.toBeInTheDocument();
  expect(value("Codec")).toBe("video/H264");
  expect(value("Decoder")).toBe("ExternalDecoder");
  expect(value("Frame size")).toBe("1920 × 1080");
  expect(value("Frame rate")).toBe("15 fps");
  expect(screen.queryByText(CHECK_HINT)).not.toBeInTheDocument();
});

// Scenario: No video played
test("a failed check leaves the decoder card unchanged", async () => {
  const peers = await checkDecoder();
  await act(() => new Promise((r) => setTimeout(r, 0)));
  peers[0].fail();
  closeDialog();
  expect(screen.getByText(CHECK_HINT)).toBeInTheDocument();
});

describe("FridgeSense monitoring switch", () => {
  const PAUSED = { paused: true, since: "2026-10-18T14:05:00.000Z" };
  const pausedText = () => `Paused since ${dayLabel(PAUSED.since)} ${clock(PAUSED.since)}`;
  const card = () => screen.getByRole("region", { name: "FridgeSense" });

  // Scenario: Active camera
  test("active camera shows Active and the switch on", async () => {
    renderCamera(vi.fn().mockResolvedValue(INFO), {}, undefined, "owner");
    expect(await within(await screen.findByRole("region", { name: "FridgeSense" })).findByText("Active")).toBeInTheDocument();
    expect(screen.getByRole("switch", { name: "FridgeSense" })).toHaveAttribute("aria-checked", "true");
    expect(
      within(card()).getByText("Pause while you clean, service or renovate. Door openings are not recorded or analyzed while paused."),
    ).toBeInTheDocument();
  });

  // Scenario: Pause from the tab
  test("pause from the tab", async () => {
    const setMonitoring = vi.fn().mockResolvedValue(PAUSED);
    renderCamera(vi.fn().mockResolvedValue(INFO), { setMonitoring }, undefined, "owner");
    await userEvent.click(await screen.findByRole("switch", { name: "FridgeSense" }));
    expect(setMonitoring).toHaveBeenCalledWith(true);
    expect(await within(card()).findByText(pausedText())).toBeInTheDocument();
    expect(screen.getByRole("switch", { name: "FridgeSense" })).toHaveAttribute("aria-checked", "false");
  });

  // Scenario: Resume from the tab
  test("resume from the tab", async () => {
    const setMonitoring = vi.fn().mockResolvedValue({ paused: false, since: "2026-10-18T16:30:00.000Z" });
    renderCamera(vi.fn().mockResolvedValue({ ...INFO, monitoring: PAUSED }), { setMonitoring }, undefined, "user");
    await userEvent.click(await screen.findByRole("switch", { name: "FridgeSense" }));
    expect(setMonitoring).toHaveBeenCalledWith(false);
    expect(await within(card()).findByText("Active")).toBeInTheDocument();
  });

  // Scenario: Change fails
  test("a failed change puts the switch back", async () => {
    const setMonitoring = vi.fn().mockRejectedValue(new ApiError(500));
    renderCamera(vi.fn().mockResolvedValue(INFO), { setMonitoring }, undefined, "owner");
    await userEvent.click(await screen.findByRole("switch", { name: "FridgeSense" }));
    expect(await within(card()).findByText("Could not change it. Try again.")).toBeInTheDocument();
    expect(screen.getByRole("switch", { name: "FridgeSense" })).toHaveAttribute("aria-checked", "true");
    expect(within(card()).getByText("Active")).toBeInTheDocument();
  });

  // Scenario: Viewer
  test("a viewer sees the state without the switch", async () => {
    renderCamera(vi.fn().mockResolvedValue({ ...INFO, monitoring: PAUSED }));
    expect(await within(await screen.findByRole("region", { name: "FridgeSense" })).findByText(pausedText())).toBeInTheDocument();
    expect(screen.queryByRole("switch", { name: "FridgeSense" })).not.toBeInTheDocument();
  });
});
