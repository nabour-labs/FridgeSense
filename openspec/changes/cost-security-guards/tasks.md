# Tasks

## 1. Door check before face detection (`door-event-detection`)

- [x] 1.1 Write failing tests in `backend/tests/test_stills.py`: raw download returns `(n, bytes)` and writes no S3 object; "Four stills saved" (bright door box) and "Download link gets no token", "Still not ready yet", "Too few stills" (403) still hold against the split functions; `store_blurred_stills` stores only blurred bytes
- [x] 1.2 Write failing tests in `backend/tests/test_fetch_stills_task.py`: "Closed door costs no face detection", "Door stayed closed", "Too few stills" (no DetectFaces, `still_keys = []`), "Too few stills survive face detection", "Door check runs on downloaded stills", "Fridge light visible"; replace the two blurred-door-check tests that encode the old requirement
- [x] 1.3 Implement: split `download_stills` into raw download and `store_blurred_stills`, reorder `fetch_stills` (download → door check → blur and store only on `door_open`) to make tests pass
- [x] 1.4 Run `tests/test_faces.py`, `tests/test_analyze_task.py` and `tests/test_pipeline_e2e.py` to confirm "Analysis receives blurred bytes", the fail-closed scenarios and the end-to-end path still pass; refactor with tests green

## 2. Ring token takeover guard (`ring-account-link`)

- [ ] 2.1 Write failing tests in `backend/tests/test_token_exchange.py` for "Different account while one is linked", "Different account while relink is needed", "Same account links again" and "Different account before anything is linked"
- [ ] 2.2 Implement the refusal in `linking.token_exchange` (409, `token_exchange_refused` log, store untouched) to make tests pass; confirm "Valid authorization code", "Ring rejects the code" and "Secrets never logged" still pass

## 3. API throttling (`cost-and-abuse-guards`)

- [ ] 3.1 Set `alertEmail: "owner@example.test"` as a default context in `infra/test/helpers.ts` (needed by section 4; harmless before it)
- [ ] 3.2 Write failing CDK tests for "Default stage throttled", "Passcode routes throttled", "Session route reaches the app API" and "Routes exist before their limits"
- [ ] 3.3 Implement: explicit `POST /api/session` route in `AppSite`, stage default and route settings plus stage dependencies in `fridgesense-stack.ts`, to make tests pass; update any route-count test that the new route legitimately changes

## 4. Budget and alarm (`cost-and-abuse-guards`)

- [ ] 4.1 Write failing CDK tests for "Budget at 80 percent", "Alarm on failed executions" and "Address missing"
- [ ] 4.2 Implement `alertEmail` context check, `CfnBudget`, SNS topic with email subscription and the `ExecutionsFailed` alarm to make tests pass
- [ ] 4.3 Make sure `cdk.context.json` is gitignored; add `-c alertEmail=...` to the deploy command in the README

## 5. Finish

- [ ] 5.1 Run every suite green: `cd backend && uv run pytest && uv run ruff check .`, `cd pwa && npm test`, `cd infra && npm test && npx tsc --noEmit -p .`
- [ ] 5.2 Log any friction from API Gateway, Budgets, CloudWatch or CDK in `docs/friction-log.md`
- [ ] 5.3 Merge `feat/cost-security-guards` into `local` (no push, no deploy)
