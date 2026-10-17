import { render, screen, within } from "@testing-library/react";
import { AppContext } from "../AppContext";
import type { Role, SetupWarning } from "../api/types";
import { fakeApi } from "../test-utils";
import { Warnings } from "./Warnings";

const MOTION_OFF: SetupWarning = {
  code: "motion_detection_off",
  message: "Motion detection is off on the camera, so no door openings are recorded. Turn it on in the Ring app.",
};
const SETUP_MISSING: SetupWarning = {
  code: "door_setup_missing",
  message: "Open/close detection is not set up, so the default zones are used and openings may be missed.",
};
const moved = (update: ("door_references" | "fridge_area")[]): SetupWarning => ({
  code: "camera_moved",
  message: "The camera has moved or changed angle. Update the references so detection stays accurate.",
  since: "2026-10-17T10:00:00.000Z",
  update,
});

function renderWarnings(warnings: SetupWarning[] | Error, role: Role = "owner") {
  const api = fakeApi({
    warnings: vi.fn(async () => {
      if (warnings instanceof Error) throw warnings;
      return { warnings, checked_at: "2026-10-17T12:00:00.000Z" };
    }),
  });
  const report = vi.fn();
  render(
    <AppContext.Provider value={{ api, role, report, online: vi.fn(), go: vi.fn() }}>
      <Warnings />
    </AppContext.Provider>,
  );
  return { api, report };
}

// Motion detection off banner
test("motion detection off links to the Camera tab", async () => {
  renderWarnings([MOTION_OFF]);
  const banner = await screen.findByRole("alert");
  expect(banner).toHaveTextContent(MOTION_OFF.message);
  expect(within(banner).getByRole("link", { name: "Open Camera" })).toHaveAttribute("href", "#config");
});

// Setup missing banner
test("setup missing links to Open/close detection", async () => {
  renderWarnings([SETUP_MISSING]);
  const banner = await screen.findByRole("alert");
  expect(banner).toHaveTextContent("Open/close detection is not set up");
  expect(within(banner).getByRole("link", { name: "Set up detection" })).toHaveAttribute("href", "#config/doors");
});

// Camera moved banner with both links
test("camera moved shows a link for each reference to update", async () => {
  renderWarnings([moved(["door_references", "fridge_area"])]);
  const banner = await screen.findByRole("alert");
  expect(banner).toHaveTextContent("The camera has moved or changed angle.");
  expect(within(banner).getByRole("link", { name: "Update door references" })).toHaveAttribute(
    "href",
    "#config/doors",
  );
  expect(within(banner).getByRole("link", { name: "Update fridge area" })).toHaveAttribute("href", "#config/fridge");
});

// Camera moved banner with one link
test("camera moved with only the fridge area left shows one link", async () => {
  renderWarnings([moved(["fridge_area"])]);
  const banner = await screen.findByRole("alert");
  expect(within(banner).getAllByRole("link")).toHaveLength(1);
  expect(within(banner).getByRole("link", { name: "Update fridge area" })).toBeInTheDocument();
});

test("several warnings show one banner each, in order", async () => {
  renderWarnings([MOTION_OFF, SETUP_MISSING]);
  const banners = await screen.findAllByRole("alert");
  expect(banners).toHaveLength(2);
  expect(banners[0]).toHaveTextContent("Motion detection is off");
  expect(banners[1]).toHaveTextContent("Open/close detection is not set up");
});

// Viewer sees no links
test("a viewer sees the banner text without links", async () => {
  renderWarnings([SETUP_MISSING, moved(["door_references"])], "viewer");
  const banners = await screen.findAllByRole("alert");
  expect(banners[0]).toHaveTextContent("Open/close detection is not set up");
  expect(screen.queryAllByRole("link")).toHaveLength(0);
});

// No warnings
test("no banner without warnings", async () => {
  const { api } = renderWarnings([]);
  await vi.waitFor(() => expect(api.warnings).toHaveBeenCalledTimes(1));
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

// Warnings request fails
test("a failed request shows nothing and reports no error", async () => {
  const { api, report } = renderWarnings(new Error("HTTP 500"));
  await vi.waitFor(() => expect(api.warnings).toHaveBeenCalledTimes(1));
  await new Promise((r) => setTimeout(r, 0));
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(report).not.toHaveBeenCalled();
});
