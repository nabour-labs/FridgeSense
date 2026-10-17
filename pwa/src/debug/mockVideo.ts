const KEY = "fridgesense.mockVideo";

/** The Mock video switch as last left in this browser; off when storage is blocked. */
export function loadMockVideo(): boolean {
  try {
    return localStorage.getItem(KEY) === "1";
  } catch {
    return false;
  }
}

export function saveMockVideo(on: boolean) {
  try {
    if (on) localStorage.setItem(KEY, "1");
    else localStorage.removeItem(KEY);
  } catch {
    // Blocked storage: the switch still works for this page.
  }
}
