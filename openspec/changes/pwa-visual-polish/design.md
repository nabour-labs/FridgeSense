# Design

## Context

See proposal.md for the motivation. The PWA is Vite + React 19 + Tailwind 4 + Recharts, with lucide icons. Colours are hard-coded Tailwind palette classes (`slate-*`, `sky-*`) in each screen. There is no shared component layer beyond `Sheet`. Tests render `<App api={fakeApi()} />` and query by role and text, so visual changes are safe as long as roles, names and text stay the same.

## Goals / Non-Goals

**Goals:**
- One place to change the look: theme tokens in `index.css`.
- Keep every existing role, accessible name and visible text that tests and the spec rely on.
- Work offline and in both light and dark mode.

**Non-Goals:**
- A component library or design-system package.
- Pixel-level visual regression tests.

## Decisions

### Theme tokens
`@theme` in `index.css` defines `--color-brand-50…950` (a teal/cyan "frost" scale in oklch) and `--color-warm-50…950` (aliases of Tailwind's amber), plus `--font-sans` set to Plus Jakarta Sans Variable with the system stack as fallback. Screens use `brand-*` wherever they used `sky-*` and `warm-*` for pending and attention states. Neutrals stay `slate`, so dark mode keeps working without new tokens.

*Alternative:* CSS variables outside Tailwind. Rejected because `@theme` gives us `bg-brand-600` style utilities for free.

### Font
`@fontsource-variable/plus-jakarta-sans` is imported from `index.css`. Vite bundles the woff2, and `workbox.globPatterns` gains `woff2` so it is precached. We use a package rather than Google Fonts because the app has to work offline and the service worker does not cache cross-origin requests.

### Item icons
`src/itemIcon.ts` exports `itemIcon(name, category)`. It checks an ordered keyword list against the lower-cased name (for example `milk → 🥛`, `egg → 🥚`, `apple → 🍎`, `pasta → 🍝`), then a category map (`dairy → 🧀`, `produce → 🥬`, `beverage → 🧃`, `leftovers → 🍱`, `meat → 🥩`, `snack → 🍫`, `condiment → 🫙`), then falls back to `🍽️`. The icon is drawn on a tinted rounded square, marked `aria-hidden`, with `data-icon` set so tests can read it. Emoji need no assets and look good in a demo video.

### Summary card
This replaces the amber banner. It shows a large count of in-stock items ("3 in stock"), "Last change {ago}" taken from the latest `last_changed_at`, and the pending link with the existing text. The card is a `section` with `aria-label="Fridge summary"`. The brand gradient sits behind it.

### Activity stills
The layout is a 3-column grid: the first still spans 2 columns and 3 rows (`data-featured`), and the next three stack in the right column. Events with more than 4 stills show "+N" on the 4th. The viewer `Sheet` keeps an index state with "Previous still" and "Next still" buttons, disabled at the ends. The mock API serves four SVG "fridge shelf" drawings at `/mock/still-{1..4}.svg`. They are generated inline in `mock-api.ts`, so no binary files are added.

### Change chips
The chips add `ArrowUpRight` or `ArrowDownRight` (`aria-hidden`) and keep the text in a single span. That matters because Testing Library's `getByText` matches an element's own text nodes, so splitting the label into several spans would break the existing tests.

### Confidence meter
`<div role="meter" aria-label="Confidence" aria-valuenow aria-valuemin=0 aria-valuemax=100 data-tone>` with a filled bar. The tones are `low` (under 0.5, rose), `medium` (under 0.7, warm) and `high` (brand). The "62% sure" text stays.

### Stats
Opens per day stays a Recharts `BarChart`. It gets a `linearGradient` fill, a `Cell` per bar (today in solid `brand-500`, other days in the gradient), a `LabelList` on top, and no `YAxis`. `perDay` returns `isToday` so the screen doesn't compute it again. Opens by hour becomes a plain CSS grid of 24 cells (`role="list"`, each `role="listitem"` with `aria-label="HH:00, N opens"`) whose background opacity scales with `opens / max`, with tick labels at 0, 6, 12 and 18. Recharts' axis and empty-bar rendering is awkward for 24 thin bars, and a heat strip says "when do we open the fridge" better.

### Motion
`@theme` defines `--animate-fade-up` and `--animate-sheet-up` keyframes. `<main key={tab}>` re-mounts on tab change, which re-runs `animate-fade-up`. `Sheet` uses `animate-sheet-up`. Buttons get `transition active:scale-[0.97]`. A global `@media (prefers-reduced-motion: reduce)` rule sets `animation-duration` and `transition-duration` to `0.01ms`.

### Empty states
There is a shared `EmptyState` component (icon in a tinted circle, title, hint) in `components/EmptyState.tsx`. It is used for Fridge (Refrigerator icon), Activity (DoorClosed) and Review (CheckCheck). The text is unchanged.

### PWA chrome
- `index.html` gets two `theme-color` metas: light `#f0fdfa`-ish brand-50, dark slate-950 `#020617`.
- In `manifest.ts`, `theme_color` becomes brand-600 and `background_color` brand-50.
- `make_icons.py` redraws the fridge glyph on a brand-teal gradient tile. It also writes `splash-1179x2556.png`, `splash-1290x2796.png` and `splash-750x1334.png` (centred icon on brand-50), and `index.html` links them with `apple-touch-startup-image` device media queries.

## Risks / Trade-offs

- **Emoji render differently per OS.** They're acceptable for the demo. Android and iOS both have full-colour sets.
- **Font weight:** about 30 KB extra precache. Acceptable.
- **The Recharts `Cell` and gradient aren't visible in jsdom.** Today's highlight is covered by the `isToday` unit test plus a manual screenshot check.

## Test strategy

- **Unit (Vitest):** `itemIcon` (name, category and fallback), `perDay` `isToday`, CSS and manifest checks (reading `src/index.css` and `index.html` with `node:fs`, splash files exist).
- **Component (Vitest + Testing Library through `<App>`):** Fridge summary and icons, Activity featured still, viewer navigation and end states, Review meter value and tone, Stats hour strip cells and labels.
- **Fixtures:** the existing `fakeApi()`. No new fixtures. Nothing touches the network.
- **Manual:** run the `pwa-mock` preview at 375 px in light and dark mode and take screenshots of each screen.
