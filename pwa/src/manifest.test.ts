import { existsSync, readFileSync } from "node:fs";
import { manifest, workbox } from "./manifest";

// Manifest
test("the manifest makes the app installable", () => {
  expect(manifest.name).toBe("FridgeSense");
  expect(manifest.display).toBe("standalone");
  const sizes = manifest.icons!.map((i) => i.sizes);
  expect(sizes).toEqual(expect.arrayContaining(["192x192", "512x512"]));
  for (const icon of manifest.icons!) {
    expect(existsSync(`public/${icon.src}`), icon.src).toBe(true);
  }
});

// Offline shell (service worker part)
test("the service worker serves the app shell and never the API", () => {
  expect(workbox.navigateFallback).toBe("index.html");
  expect(workbox.navigateFallbackDenylist!.some((re) => re.test("/api/inventory"))).toBe(true);
  expect(JSON.stringify(workbox.runtimeCaching ?? [])).not.toContain("api");
});

// Font cached offline
test("the service worker precaches the bundled font", () => {
  expect(workbox.globPatterns!.join(",")).toContain("woff2");
});

const html = readFileSync("index.html", "utf8");

// Theme colour per scheme
test("theme-color follows light and dark mode", () => {
  expect(html).toMatch(/<meta name="theme-color" media="\(prefers-color-scheme: light\)" content="#[0-9a-f]{6}"/);
  expect(html).toMatch(/<meta name="theme-color" media="\(prefers-color-scheme: dark\)" content="#[0-9a-f]{6}"/);
});

// iOS splash images
test("iOS splash images exist for common iPhones", () => {
  const hrefs = [...html.matchAll(/rel="apple-touch-startup-image"[^>]*href="\/([^"]+)"/g)].map((m) => m[1]);
  expect(hrefs.length).toBeGreaterThanOrEqual(3);
  for (const href of hrefs) expect(existsSync(`public/${href}`), href).toBe(true);
});
