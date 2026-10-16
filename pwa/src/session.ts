import type { Role } from "./api/types";

const TOKEN = "fridgesense.token";
const ROLE = "fridgesense.role";
const EXPIRES = "fridgesense.expires";

export interface StoredSession {
  token: string;
  role: Role;
  /** Epoch ms after which the passcode is asked for again. */
  expiresAt: number;
}

/** The stored session, or null (and storage cleared) if it is missing, expired or has no expiry. */
export function loadSession(now = Date.now()): StoredSession | null {
  try {
    const token = localStorage.getItem(TOKEN);
    if (!token) return null;
    const stored = localStorage.getItem(ROLE);
    // Sessions from before roles were stored belong to the owner.
    const role: Role = stored === "viewer" || stored === "user" ? stored : "owner";
    const expiresAt = Number(localStorage.getItem(EXPIRES));
    if (!expiresAt || now > expiresAt) {
      clearSession();
      return null;
    }
    return { token, role, expiresAt };
  } catch {
    return null;
  }
}

export function saveSession(session: StoredSession) {
  try {
    localStorage.setItem(TOKEN, session.token);
    localStorage.setItem(ROLE, session.role);
    localStorage.setItem(EXPIRES, String(session.expiresAt));
  } catch {
    // Private mode: the session lasts until the page closes.
  }
}

export function clearSession() {
  try {
    localStorage.removeItem(TOKEN);
    localStorage.removeItem(ROLE);
    localStorage.removeItem(EXPIRES);
  } catch {
    // Nothing stored.
  }
}
