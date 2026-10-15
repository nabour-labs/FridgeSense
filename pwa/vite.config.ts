/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";
import { manifest, workbox } from "./src/manifest";

// `npm run dev` proxies /api to a deployed FridgeSense: FRIDGESENSE_URL=https://xxxx.cloudfront.net
const apiTarget = process.env.FRIDGESENSE_URL;

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({ registerType: "autoUpdate", manifest, workbox, includeAssets: ["icon.svg", "apple-touch-icon.png"] }),
  ],
  server: apiTarget ? { proxy: { "/api": { target: apiTarget, changeOrigin: true } } } : {},
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test-setup.ts"],
  },
});
