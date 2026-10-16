# Tasks

## 1. Backend: user role

- [x] 1.1 Write failing tests in `backend/tests/test_api_auth.py` for "User passcode", "No user passcode configured", "Equal passcodes", "User passcode changed", "User writes" and "User refused debug traces". Run them and confirm they fail because the `user` role does not exist.
- [x] 1.2 Add `AppConfig.user_passcode`, the `user` role in `session.py` (order owner, user, viewer) and the route check in `handlers/api.py`. Verify the 1.1 tests and all existing backend tests pass.

## 2. PWA: user role

- [x] 2.1 Write failing Vitest tests for "User sign-in", "User sees no Debug tab", "User opens the debug hash", "No Debug link for users" and "User role restored". Run them and confirm they fail.
- [x] 2.2 Add `"user"` to `Role`, keep it in `loadSession`, add `canEdit` / `isAdmin`, and switch every `role === "owner"` check to the right helper. Verify the tests pass.

## 3. PWA: sign out

- [x] 3.1 Write failing Vitest tests for "Sign out" and "Signed out stays signed out". Run them and confirm they fail.
- [x] 3.2 Add the header "Sign out" button. Verify the tests pass.

## 4. Mock, docs, secret

- [x] 4.1 Add `FRIDGESENSE_MOCK=user` to the mock API (role `user`, 403 `admin only` on `/debug`), and document the three passcodes and the user role in the README without their values.
- [x] 4.2 Write `passcode` and `user_passcode` to the `fridgesense/ring-app` secret (values never committed).
- [x] 4.3 Run `uv run pytest`, `uv run ruff check`, `npm test` and `npm run build` in `pwa/`, all green. Check sign out and the user role in the browser preview.
