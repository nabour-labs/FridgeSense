import { loadMockVideo, saveMockVideo } from "./mockVideo";

afterEach(() => vi.restoreAllMocks());

it("is off by default", () => {
  expect(loadMockVideo()).toBe(false);
});

it("Turned on, then reload: the switch is still on", () => {
  saveMockVideo(true);
  expect(loadMockVideo()).toBe(true);
  saveMockVideo(false);
  expect(loadMockVideo()).toBe(false);
});

it("Storage blocked: starts off and saving does not throw", () => {
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
    throw new DOMException("blocked", "SecurityError");
  });
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new DOMException("blocked", "SecurityError");
  });
  expect(loadMockVideo()).toBe(false);
  expect(() => saveMockVideo(true)).not.toThrow();
});
