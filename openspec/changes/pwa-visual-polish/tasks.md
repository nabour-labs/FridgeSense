# Tasks

## 1. Visual style

- [x] 1.1 Write failing tests in `src/style.test.ts` for "Theme tokens", "Reduced motion" and, in `manifest.test.ts`, "Font cached offline". Verify they fail
- [x] 1.2 Add `@fontsource-variable/plus-jakarta-sans`, theme tokens, keyframes and the reduced-motion rule to `index.css`, and `woff2` to the precache patterns, to make 1.1 pass
- [x] 1.3 Restyle the app shell, nav, `Sheet` and SignIn with `brand-*` / `warm-*` and motion (fade on tab change, sheet slide, press scale). Existing tests stay green

## 2. Fridge

- [x] 2.1 Write failing tests for "Item icons from name" and "Item icon falls back to category, then a plate" (`src/itemIcon.test.ts` and a Fridge screen test). Verify they fail
- [x] 2.2 Implement `itemIcon.ts` and the icon badge in `ItemRow` to make 2.1 pass
- [x] 2.3 Write failing tests for "Summary card", "Summary with nothing changed yet" and the updated "Pending banner". Verify they fail
- [x] 2.4 Implement the summary card to make 2.3 pass
- [x] 2.5 Add the `EmptyState` component and use it for "Empty fridge". The existing test stays green

## 3. Activity

- [x] 3.1 Write failing tests for "Stills" (featured), "Step through stills", "Viewer at the ends" and "No stills". Verify they fail
- [x] 3.2 Implement the featured-still grid and the viewer with previous/next to make 3.1 pass
- [x] 3.3 Restyle the change chips with direction arrows. The "Door opening shown" and "Unconfirmed change marked" tests stay green
- [x] 3.4 Serve the SVG sample stills from the mock API, and use `EmptyState` for "No door openings"

## 4. Review

- [x] 4.1 Write a failing test for "Confidence meter". Verify it fails
- [x] 4.2 Implement the meter to make 4.1 pass, and use `EmptyState` for "Nothing to review"

## 5. Stats

- [x] 5.1 Write failing tests for "Today marked" (`stats.test.ts`) and "Hour heat strip". Verify they fail
- [x] 5.2 Add `isToday` to `perDay`, restyle the per-day chart (gradient, today highlight, labels, no Y axis), and build the hour heat strip to make 5.1 pass

## 6. PWA chrome

- [x] 6.1 Write failing tests for "Theme colour per scheme" and "iOS splash images" in `manifest.test.ts`. Verify they fail
- [x] 6.2 Redraw the icons and add splash images in `make_icons.py`, regenerate the PNGs, and update `index.html` and `manifest.ts` colours to make 6.1 pass

## 7. Finish

- [x] 7.1 Run `npm test` and `npm run typecheck` in `pwa/`, both green
- [x] 7.2 Check every screen in the `pwa-mock` preview at 375 px in light and dark mode, and fix anything that looks off
