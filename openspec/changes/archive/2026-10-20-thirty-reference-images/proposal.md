# Proposal

## Why

Six reference images is too few to cover the items that regularly go in and out of the fridge. The owner wants up to 30, so Nova has an example for more of them.

## What Changes

- An account can hold up to 30 reference images instead of 6. The 31st is refused with 409 `{"error": "at most 30 reference images"}`.
- The Reference images tab counts "n of 30" and disables "Add" at 30.
- No change to the image size cap (200,000 bytes, 768 px) or to how references are sent to Nova.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `analysis-config`: the per-account cap goes from 6 to 30
- `inventory-app`: the Reference images count and "Limit reached" use 30

## Impact

- `backend/src/fridgesense/analysis_config.py` (`MAX_REFERENCES`), `pwa/src/screens/ReferenceImages.tsx`, `pwa/scripts/mock-api.ts`, their tests, README.
- More reference images per Nova request means more input tokens per door opening (the references sit before the prompt cache point). `GET /api/config` returns every image as base64, so 30 full-size (200 KB) images would be about 8 MB, above Lambda's 6 MB response limit; typical 768 px JPEGs are far smaller.
