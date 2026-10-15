import { clearSession, loadSession, saveSession } from "./session";

const HOUR = 3600_000;

beforeEach(() => localStorage.clear());

test("saveSession stores the expiry and loadSession returns it while valid", () => {
  const expiresAt = Date.now() + 24 * HOUR;
  saveSession({ token: "tok", role: "viewer", expiresAt });
  expect(localStorage.getItem("fridgesense.expires")).toBe(String(expiresAt));
  expect(loadSession()).toEqual({ token: "tok", role: "viewer", expiresAt });
});

// Opened after 24 hours
test("a stored session past its expiry is cleared", () => {
  saveSession({ token: "tok", role: "owner", expiresAt: Date.now() - 1 });
  expect(loadSession()).toBeNull();
  expect(localStorage.getItem("fridgesense.token")).toBeNull();
  expect(localStorage.getItem("fridgesense.expires")).toBeNull();
});

// Token stored without expiry
test("a token from an earlier app version with no expiry is cleared", () => {
  localStorage.setItem("fridgesense.token", "old");
  localStorage.setItem("fridgesense.role", "owner");
  expect(loadSession()).toBeNull();
  expect(localStorage.getItem("fridgesense.token")).toBeNull();
});

test("clearSession removes the expiry too", () => {
  saveSession({ token: "tok", role: "owner", expiresAt: Date.now() + HOUR });
  clearSession();
  expect(localStorage.getItem("fridgesense.expires")).toBeNull();
});
