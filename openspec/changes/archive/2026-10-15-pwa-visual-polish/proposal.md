# Proposal

## Why

The PWA works, but it looks like a stock Tailwind app: default slate and sky colours, system font, a plain text list, grey placeholder boxes on Activity and thin, unlabelled bars on Stats. The demo video is shot mostly on this app, so its look is a big part of the first impression. This change gives it its own visual identity and makes each screen easier to read at a glance. It does not change the API or what the app does.

## What Changes

1. **Brand theme.** A "frost" teal accent and a warm amber accent, defined once as Tailwind `@theme` tokens (`brand-*`, `warm-*`) and used everywhere in place of `sky-*`. Plus Jakarta Sans (bundled with the app, so it works offline) for all text.
2. **Item icons.** Every item on Fridge gets an emoji badge picked from its name, then its category, then a generic plate.
3. **Fridge summary.** A summary card at the top of Fridge shows how many items are in stock, when the inventory last changed, and the pending link ("2 items to confirm"), which moves into the card.
4. **Activity stills.** The first still is shown large, with the others stacked beside it. The full-size viewer gets previous/next buttons. The mock API serves real-looking sample stills, so dev mode no longer shows grey boxes.
5. **Change chips.** Added and removed chips get an up or down arrow icon and stronger colours. The label text stays as it is ("+ milk", "− 2 eggs").
6. **Confidence meter.** Each Review card shows confidence as a coloured meter (red under 50 %, amber under 70 %, green otherwise) next to the "62% sure" text.
7. **Stats charts.** Opens per day uses gradient bars with the count above each bar, highlights today and drops the Y axis. Opens by hour becomes a 24-cell heat strip.
8. **Motion.** Screens fade in when you switch tabs, sheets slide up, and buttons scale slightly when pressed. All of it is turned off under `prefers-reduced-motion`.
9. **Empty states.** Empty Fridge, Activity and Review each show a large icon on a tinted circle above the existing text.
10. **PWA chrome.** `theme-color` follows light and dark mode, the manifest colours match the theme, the icons are redrawn in the brand colours, and iOS home-screen splash images are added for common iPhone sizes.

Hackathon track: **Ring** (consumer experience of the camera-powered app shown in the demo).

### Out of scope

- New screens, new data or API changes.
- A user-selectable theme or an in-app light/dark toggle. The app follows the OS setting.
- Real door-opening stills in mock mode. Mock mode uses drawn SVG stand-ins.
- Splash images for iPads and every iPhone size. Only three common iPhone sizes get one.
- Charting libraries other than Recharts.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `inventory-app`: Fridge screen (summary card, item icons, illustrated empty state), Activity screen (featured still, still viewer navigation), Review screen (confidence meter), Stats screen (per-day highlight, hour heat strip) and Installable app (theme colour per scheme, splash images). A new "Visual style" requirement covers the theme tokens, font and reduced motion.

## Impact

- **Code:** `pwa/src/index.css`, `App.tsx`, every file under `pwa/src/screens/`, `components/Sheet.tsx`, a new `pwa/src/itemIcon.ts`, `stats.ts` (adds `isToday` to day counts), `manifest.ts`, `index.html`, `scripts/mock-api.ts`, `scripts/make_icons.py` and the PNGs in `pwa/public/`.
- **Dependencies:** `@fontsource-variable/plus-jakarta-sans`, about 30 KB of woff2 that the service worker precaches.
- **Tests:** new Vitest tests for each new scenario. Existing scenario tests keep passing unchanged, except the Activity stills test, which gains the previous/next viewer steps.
- **Backend, infra, MCP:** no change.
