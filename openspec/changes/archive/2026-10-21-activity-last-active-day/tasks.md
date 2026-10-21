# Tasks

## 1. Default day

- [x] 1.1 Write failing tests in `Activity.test.tsx` for "Last day with openings by default" and "No openings in the last 31 days". Run `npm test` in `pwa/`: they fail because the screen stays on today
- [x] 1.2 On open, ask for the newest opening from local midnight 30 days ago to local midnight tomorrow (`limit=1`) and start on its day; fall back to today when there is none or the request fails. Verify: `npm test` in `pwa/` is green
