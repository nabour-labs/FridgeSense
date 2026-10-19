# Tasks

## 1. Backend

- [x] 1.1 Write failing tests in `backend/tests/test_analysis_config.py` and `backend/tests/test_api_config.py` for "Edit the annotation", "Replace the image", "Edit both", "Nothing to change", "Bad edit", "Edit an unknown reference" and "Viewer cannot edit"; run them and see them fail
- [x] 1.2 Implement `analysis_config.update_reference` and `PATCH /api/config/references/{id}` until `uv run pytest` passes

## 2. PWA

- [x] 2.1 Write failing tests: `updateReference` in `api/client.test.ts`; "Edit an annotation", "Replace the image", "Draw on the current image", "Nothing changed", "Edit refused" and "Viewer has no edit" in `screens/Config.test.tsx`; run them and see them fail
- [x] 2.2 Add `updateReference` and turn the add sheet into a shared add/edit sheet until `npm test` passes
