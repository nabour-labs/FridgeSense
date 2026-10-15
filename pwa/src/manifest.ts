import type { ManifestOptions } from "vite-plugin-pwa";
import type { GenerateSWOptions } from "workbox-build";

export const manifest: Partial<ManifestOptions> = {
  name: "FridgeSense",
  short_name: "FridgeSense",
  description: "What's in your fridge, seen by your camera.",
  display: "standalone",
  start_url: "/",
  scope: "/",
  theme_color: "#00928a", // brand-600
  background_color: "#eafdfc", // brand-50, matches the iOS splash
  icons: [
    { src: "icon-192.png", sizes: "192x192", type: "image/png" },
    { src: "icon-512.png", sizes: "512x512", type: "image/png" },
    { src: "icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
  ],
};

/** The service worker caches the app shell; /api always goes to the network. */
export const workbox: Partial<GenerateSWOptions> = {
  globPatterns: ["**/*.{js,css,html,svg,png,webmanifest,woff2}"],
  navigateFallback: "index.html",
  navigateFallbackDenylist: [/^\/api\//],
  runtimeCaching: [],
};
