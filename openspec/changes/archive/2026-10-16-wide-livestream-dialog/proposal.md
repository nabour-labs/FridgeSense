# Proposal

## Why

The Livestream dialog uses the shared `Sheet`, which is capped at 448 px (`max-w-md`) for forms and confirmations. On a laptop or desktop that leaves the video at about 400 × 225 px, too small to see what is in the fridge.

## What Changes

- `Sheet` takes an optional `size`: `"default"` (unchanged, `max-w-md`) or `"wide"`, which allows up to 768 px (`sm:max-w-3xl`) on screens `sm` and up. On phones the sheet stays full width.
- The Livestream dialog uses the wide size, both for the live camera view and for the Mock video clip player on localhost.
- Every other dialog keeps its current width.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `camera-live-view`: the Livestream dialog is wide on larger screens.

## Impact

- `pwa/src/components/Sheet.tsx`, `pwa/src/components/LiveStream.tsx`, `pwa/src/debug/ClipLive.tsx` and their tests.
- No backend, infra, AWS or cost change.
