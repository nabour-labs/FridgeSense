# Tasks

## 1. Link page (ring-account-link)

- [x] 1.1 Write failing tests in `tests/test_link_page.py` for "App URL configured" and "App URL not configured"; run `uv run pytest tests/test_link_page.py` and verify they fail for the missing link
- [x] 1.2 Add `app_url` to `link_page.linked()` and `linking.link_submit()`, and read `APP_URL` in `handlers/http.py`, to make 1.1 pass

## 2. Infra

- [x] 2.1 Write a failing assertion in `infra/test/stack.test.ts` for "Stack passes the site URL"; run `npm test` in `infra/` and verify it fails
- [x] 2.2 Add `APP_URL` to `HttpFunction` from `AppSite.url` to make 2.1 pass

## 3. Verify

- [x] 3.1 Run `uv run pytest` and `uv run ruff check src tests` in `backend/`, and `npm test` in `infra/`, all green
