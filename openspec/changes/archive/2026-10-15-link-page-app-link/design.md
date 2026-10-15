## Context

`link_page.linked()` renders the success page; `linking.link_submit()` returns it; `handlers/http.py` wires dependencies. The site URL is `AppSite.url` (`https://<distribution>.cloudfront.net`), already a stack output.

## Decisions

- **Pass the URL in, don't read env deep down.** `handlers/http.py` reads `APP_URL` and passes it to `link_submit(..., app_url=...)`, which passes it to `linked()`. Keeps `link_page` and `linking` pure and testable.
- **CDK:** `httpFn.addEnvironment("APP_URL", appSite.url)` after `AppSite` is built. No dependency cycle: Distribution depends on the HttpApi, the HttpFunction depends on the Distribution, and only routes depend on the HttpFunction.
- **Rendering:** an `<a class="button">` styled like the existing button; the URL is HTML-escaped. Missing or empty `APP_URL` → no link.

## Test strategy

- Unit (pytest, moto + respx as in `tests/test_link_page.py`): successful link with `APP_URL` set shows the link; without it, no link.
- Infra (vitest, `infra/test/stack.test.ts`): `HttpFunction` env includes `APP_URL`.
- No live Ring or AWS calls.
