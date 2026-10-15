import { existsSync } from "node:fs";
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
