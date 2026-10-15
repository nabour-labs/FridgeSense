import { act, renderHook } from "@testing-library/react";
import { usePolling } from "./usePolling";

let visibility: DocumentVisibilityState = "visible";

beforeEach(() => {
  vi.useFakeTimers();
  visibility = "visible";
  vi.spyOn(document, "visibilityState", "get").mockImplementation(() => visibility);
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

function setVisibility(state: DocumentVisibilityState) {
  visibility = state;
  document.dispatchEvent(new Event("visibilitychange"));
}

test("calls immediately and then every 10 s", () => {
  const fn = vi.fn();
  renderHook(() => usePolling(fn, 10_000));
  expect(fn).toHaveBeenCalledTimes(1);
  act(() => void vi.advanceTimersByTime(10_000));
  expect(fn).toHaveBeenCalledTimes(2);
  act(() => void vi.advanceTimersByTime(20_000));
  expect(fn).toHaveBeenCalledTimes(4);
});

test("makes no calls while hidden", () => {
  const fn = vi.fn();
  renderHook(() => usePolling(fn, 10_000));
  act(() => setVisibility("hidden"));
  act(() => void vi.advanceTimersByTime(60_000));
  expect(fn).toHaveBeenCalledTimes(1);
});

test("calls again when the page becomes visible", () => {
  const fn = vi.fn();
  renderHook(() => usePolling(fn, 10_000));
  act(() => setVisibility("hidden"));
  act(() => setVisibility("visible"));
  expect(fn).toHaveBeenCalledTimes(2);
  act(() => void vi.advanceTimersByTime(10_000));
  expect(fn).toHaveBeenCalledTimes(3);
});

test("stops on unmount", () => {
  const fn = vi.fn();
  const { unmount } = renderHook(() => usePolling(fn, 10_000));
  unmount();
  act(() => void vi.advanceTimersByTime(30_000));
  expect(fn).toHaveBeenCalledTimes(1);
});
