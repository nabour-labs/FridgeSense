import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ClipPicker, grabFrame } from "./ClipPicker";

const CLIPS = {
  clips: [
    { name: "Ring_Fridge_20261015_2025.mp4", size: 16246581, url: "/__dev/videos/Ring_Fridge_20261015_2025.mp4" },
    { name: "Ring_Fridge_20261015_1920.mp4", size: 8266528, url: "/__dev/videos/Ring_Fridge_20261015_1920.mp4" },
  ],
  upload: false,
};

function serve(body: unknown) {
  const fetchMock = vi.fn(async () => new Response(JSON.stringify(body), { headers: { "content-type": "application/json" } }));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const video = () => screen.getByTestId("clip-video") as HTMLVideoElement;

it("Clips listed: newest first, newest selected and playing in the player", async () => {
  const fetchMock = serve(CLIPS);
  render(<ClipPicker onPick={vi.fn()} onCancel={vi.fn()} />);
  const box = await screen.findByRole("combobox", { name: "Clip" });
  expect(fetchMock).toHaveBeenCalledWith("/__dev/videos");
  expect(box).toHaveTextContent("Ring_Fridge_20261015_2025.mp4");
  expect(video()).toHaveAttribute("src", "/__dev/videos/Ring_Fridge_20261015_2025.mp4");
  await userEvent.click(box);
  const options = screen.getAllByRole("option").map((o) => o.textContent);
  expect(options).toEqual(["Ring_Fridge_20261015_2025.mp4", "Ring_Fridge_20261015_1920.mp4"]);
  await userEvent.click(screen.getByRole("option", { name: "Ring_Fridge_20261015_1920.mp4" }));
  expect(video()).toHaveAttribute("src", "/__dev/videos/Ring_Fridge_20261015_1920.mp4");
});

it("Use this frame: returns the grabbed frame at the scrubber position as the snapshot", async () => {
  serve(CLIPS);
  const grab = vi.fn(async () => "BASE64FRAME");
  const onPick = vi.fn();
  render(<ClipPicker onPick={onPick} onCancel={vi.fn()} grab={grab} />);
  await screen.findByRole("combobox", { name: "Clip" });
  const use = screen.getByRole("button", { name: "Use this frame" });
  expect(use).toBeDisabled();
  Object.defineProperty(video(), "duration", { value: 12, configurable: true });
  fireEvent.loadedMetadata(video());
  fireEvent.loadedData(video());
  fireEvent.change(screen.getByRole("slider", { name: "Position" }), { target: { value: "4.5" } });
  expect(video().currentTime).toBe(4.5);
  await userEvent.click(use);
  expect(grab).toHaveBeenCalledWith(video());
  expect(onPick).toHaveBeenCalledWith({ image: "BASE64FRAME", captured_at: expect.any(String) });
  expect(Number.isNaN(Date.parse(onPick.mock.calls[0][0].captured_at))).toBe(false);
});

it("Frame size: a 2560×1440 clip becomes a 960×540 JPEG", async () => {
  const drawImage = vi.fn();
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({ drawImage } as never);
  let size: [number, number] = [0, 0];
  vi.spyOn(HTMLCanvasElement.prototype, "toBlob").mockImplementation(function (this: HTMLCanvasElement, cb, type) {
    size = [this.width, this.height];
    expect(type).toBe("image/jpeg");
    cb(new Blob(["jpeg!"], { type: "image/jpeg" }));
  });
  const v = document.createElement("video");
  Object.defineProperty(v, "videoWidth", { value: 2560 });
  Object.defineProperty(v, "videoHeight", { value: 1440 });
  const image = await grabFrame(v);
  expect(size).toEqual([960, 540]);
  expect(drawImage).toHaveBeenCalledWith(v, 0, 0, 960, 540);
  expect(atob(image)).toBe("jpeg!");
});

it("No clips: says so and Use this frame is disabled", async () => {
  serve({ clips: [], upload: false });
  render(<ClipPicker onPick={vi.fn()} onCancel={vi.fn()} />);
  expect(await screen.findByText("No clips in the videos folder")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Use this frame" })).toBeDisabled();
});

it("Clip won't load: says so and Use this frame is disabled", async () => {
  serve(CLIPS);
  render(<ClipPicker onPick={vi.fn()} onCancel={vi.fn()} />);
  await screen.findByRole("combobox", { name: "Clip" });
  fireEvent.loadedData(video());
  fireEvent.error(video());
  expect(screen.getByText("This clip can't be played")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Use this frame" })).toBeDisabled();
});

it("Deployed backend notice", async () => {
  serve({ ...CLIPS, upload: true });
  render(<ClipPicker onPick={vi.fn()} onCancel={vi.fn()} />);
  expect(await screen.findByText("Frames are not face-blurred and will be uploaded if you save them.")).toBeInTheDocument();
});

it("Mock API has no notice", async () => {
  serve(CLIPS);
  render(<ClipPicker onPick={vi.fn()} onCancel={vi.fn()} />);
  await screen.findByRole("combobox", { name: "Clip" });
  expect(screen.queryByText(/not face-blurred/)).not.toBeInTheDocument();
});

it("Cancel: the Cancel button and closing the sheet both cancel", async () => {
  serve(CLIPS);
  const onCancel = vi.fn();
  const onPick = vi.fn();
  render(<ClipPicker onPick={onPick} onCancel={onCancel} />);
  await screen.findByRole("combobox", { name: "Clip" });
  await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
  await userEvent.click(screen.getAllByRole("button", { name: "Close" })[0]);
  await waitFor(() => expect(onCancel).toHaveBeenCalledTimes(2));
  expect(onPick).not.toHaveBeenCalled();
});
