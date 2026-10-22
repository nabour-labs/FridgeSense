# Tasks

## 1. Owner-only banners

- [x] 1.1 In `pwa/src/components/Warnings.test.tsx`, replace the viewer tests ("a viewer sees …") with tests for "User sees no banners" and "Viewer sees no banners" (no alert and no `warnings()` call). Run `npx vitest run src/components/Warnings.test.tsx` and see them fail because banners still show
- [x] 1.2 Gate `Warnings` on `isAdmin(role)` and drop the `canEdit` link check. Verify: `npm test` in `pwa/` is green
