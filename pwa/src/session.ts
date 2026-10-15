import type { Role } from "./api/types";

const TOKEN = "fridgesense.token";
const ROLE = "fridgesense.role";

export interface StoredSession {
  token: string;
  role: Role;
}

export function loadSession(): StoredSession | null {
  try {
    const token = localStorage.getItem(TOKEN);
    const role = localStorage.getItem(ROLE) === "viewer" ? "viewer" : "owner";
    return token ? { token, role } : null;
  } catch {
    return null;
  }
}

export function saveSession(session: StoredSession) {
  try {
    localStorage.setItem(TOKEN, session.token);
    localStorage.setItem(ROLE, session.role);
  } catch {
    // Private mode: the session lasts until the page closes.
  }
}

export function clearSession() {
  try {
    localStorage.removeItem(TOKEN);
    localStorage.removeItem(ROLE);
  } catch {
    // Nothing stored.
  }
}
