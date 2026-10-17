# Tasks

## 1. Failed runs end as failed executions

- [x] 1.1 Write failing test for "Failed run ends as a failed execution" in `infra/test/pipeline.test.ts` (MarkFailed → Fail `AnalysisFailed`); run `npm test` in `infra/` and see it fail
- [x] 1.2 Implement the `Fail` state after `MarkFailed` and verify the test passes

## 2. Window and stills steps retried and caught

- [x] 2.1 Write failing tests for "Window step retries and is caught" and "Stills step retries and is caught" in `infra/test/pipeline.test.ts`; see them fail
- [x] 2.2 Add Retry and Catch to `FindWindow` and `FetchStills` and verify the tests pass
- [x] 2.3 Write failing pytest for "Failure before the door event exists" in `backend/tests/test_analyze_task.py`; see it fail with `KeyError: 'door_sk'`
- [x] 2.4 Make `mark_failed_task` skip the status write without `door_sk` and verify the test passes

## 3. Alarms

- [x] 3.1 Write failing tests for "Alarm on timed-out executions", "Metric filter on rejected refreshes" and "Alarm on rejected refreshes" in `infra/test/guards.test.ts`; see them fail
- [x] 3.2 Add the timed-out alarm, metric filter and relink alarm to `infra/lib/fridgesense-stack.ts` and verify the tests pass

## 4. Re-link warning

- [x] 4.1 Write failing pytest for "Link expired", "Link expired with other problems", "Link expired before any camera" and "Linked" in `backend/tests/test_api_warnings.py`; see them fail
- [x] 4.2 Add the `needs_relink` warning to `setup_warnings.warnings_body`, pass `link_status` from the API handler, and verify the tests pass
- [x] 4.3 Write failing vitest for "Re-link banner" in `pwa/src/components/Warnings.test.tsx`; see it fail
- [x] 4.4 Add `needs_relink` to `SetupWarning` and to the banner's fixes (no link) and verify the test passes

## 5. Full suites

- [x] 5.1 Run `uv run pytest` and `uv run ruff check` in `backend/`, `npm test` in `infra/` and `pwa/` (plus the PWA lint/typecheck scripts if present), all green
