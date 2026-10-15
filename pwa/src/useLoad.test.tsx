import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { ApiError } from "./api/client";
import { AppContext, type AppContextValue } from "./AppContext";
import { fakeApi } from "./test-utils";
import { useLoad } from "./useLoad";

let ctx: AppContextValue;

beforeEach(() => {
  vi.useFakeTimers();
  ctx = { api: fakeApi(), role: "owner", report: vi.fn(), online: vi.fn(), go: vi.fn() };
});

afterEach(() => {
  vi.useRealTimers();
});

function wrapper({ children }: { children: ReactNode }) {
  return <AppContext.Provider value={ctx}>{children}</AppContext.Provider>;
}

async function flush() {
  await act(async () => {});
}

// Still loading
test("loading: no data and not failed while the first request is in flight", () => {
  const fetch = vi.fn(() => new Promise<number>(() => {}));
  const { result } = renderHook(() => useLoad(fetch, 10_000), { wrapper });
  expect(result.current.data).toBeNull();
  expect(result.current.failed).toBe(false);
});

// First load fails
test("a failed first load reports the error and is marked failed", async () => {
  const error = new ApiError(409);
  const fetch = vi.fn().mockRejectedValue(error);
  const { result } = renderHook(() => useLoad(fetch, 10_000), { wrapper });
  await flush();
  expect(result.current.data).toBeNull();
  expect(result.current.failed).toBe(true);
  expect(ctx.report).toHaveBeenCalledWith(error);
});

// Data arrives later
test("a later successful poll replaces the failure with data", async () => {
  const fetch = vi.fn().mockRejectedValueOnce(new ApiError(409)).mockResolvedValue(6);
  const { result } = renderHook(() => useLoad(fetch, 10_000), { wrapper });
  await flush();
  expect(result.current.failed).toBe(true);
  await act(async () => void vi.advanceTimersByTime(10_000));
  expect(result.current.data).toBe(6);
  expect(result.current.failed).toBe(false);
  expect(ctx.online).toHaveBeenCalled();
});

// Later poll fails
test("a failed poll after data keeps the data", async () => {
  const fetch = vi.fn().mockResolvedValueOnce(3).mockRejectedValue(new ApiError(500));
  const { result } = renderHook(() => useLoad(fetch, 10_000), { wrapper });
  await flush();
  await act(async () => void vi.advanceTimersByTime(10_000));
  expect(result.current.data).toBe(3);
  expect(ctx.report).toHaveBeenCalledTimes(1);
});

test("setData replaces the data", async () => {
  const fetch = vi.fn().mockResolvedValue(3);
  const { result } = renderHook(() => useLoad(fetch, 10_000), { wrapper });
  await flush();
  act(() => result.current.setData(4));
  expect(result.current.data).toBe(4);
});
