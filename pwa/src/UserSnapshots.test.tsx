import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";
import { ApiError } from "./api/client";
import { fakeApi, signedIn } from "./test-utils";

const SNAPSHOT = { image: "/9j/SNAP", captured_at: "2026-10-15T19:20:07.000Z" };

/** A user's app with spies on every live-view call, which a user's snapshot must never make. */
function renderAsUser(hash: string, cameraSnapshot: ReturnType<typeof vi.fn>) {
  signedIn("user");
  location.hash = hash;
  const api = fakeApi({
    cameraSnapshot,
    startLive: vi.fn(),
    stopLive: vi.fn(),
    cameraFrame: vi.fn(),
    camera: vi.fn().mockResolvedValue({ name: "Fridge", online: true }),
  });
  render(<App api={api} />);
  return api;
}

function expectNoLiveView(api: ReturnType<typeof fakeApi>) {
  // The live path checks the camera is online first; jsdom has no WebRTC, so this is its trace.
  expect(api.camera).not.toHaveBeenCalled();
  expect(api.startLive).not.toHaveBeenCalled();
  expect(api.stopLive).not.toHaveBeenCalled();
  expect(api.cameraFrame).not.toHaveBeenCalled();
}

afterEach(() => {
  location.hash = "";
});

// Scenario: User takes a reference snapshot
test("a user's reference snapshot comes from the newest recording", async () => {
  const api = renderAsUser("#config/refs", vi.fn().mockResolvedValue(SNAPSHOT));
  await userEvent.click(await screen.findByRole("button", { name: "Add" }));
  await userEvent.click(screen.getByRole("button", { name: "Camera snapshot" }));
  expect(await within(screen.getByRole("dialog")).findByRole("img", { name: "Reference to draw on" })).toBeInTheDocument();
  expect(api.cameraSnapshot).toHaveBeenCalledTimes(1);
  expectNoLiveView(api);
});

// Scenario: User snapshot with no recent footage
test("a user's snapshot with no recent footage says so without a live view", async () => {
  const api = renderAsUser("#config/refs", vi.fn().mockRejectedValue(new ApiError(409, "no recent footage")));
  await userEvent.click(await screen.findByRole("button", { name: "Add" }));
  await userEvent.click(screen.getByRole("button", { name: "Camera snapshot" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "No recent footage. Walk past the camera, then try again.",
  );
  expectNoLiveView(api);
});

// Scenario: User snapshot fails
test("a user's fridge-area snapshot that fails says so without a live view", async () => {
  const api = renderAsUser("#config/fridge", vi.fn().mockRejectedValue(new ApiError(502, "camera unavailable")));
  await userEvent.click(await screen.findByRole("button", { name: "Set area" }));
  expect(await within(screen.getByRole("dialog")).findByRole("alert")).toHaveTextContent(
    "The camera can't be reached right now.",
  );
  expectNoLiveView(api);
});
