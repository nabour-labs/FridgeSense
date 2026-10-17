import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => {
  cleanup();
  // Node-environment tests (scripts/) have no localStorage.
  if (typeof localStorage !== "undefined") localStorage.clear();
});
