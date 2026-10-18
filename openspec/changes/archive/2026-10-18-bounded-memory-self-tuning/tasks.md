# Tasks

## 1. Bounded-memory event sampling

- [x] 1.1 Write failing tests in `backend/tests/test_self_tuning.py` for "Long event sampled with two frames decoded" and "Several zones share one pass", using a `weakref` spy on `self_tuning._open_rgb`. Verify: `uv run pytest tests/test_self_tuning.py -k "decoded or one_pass"` fails because more than 2 decoded frames were alive.
- [x] 1.2 Rewrite `sample_event` to decode the bookend once, score all rules in one pass over the frames (one decoded frame at a time, `>=` ties kept), and re-decode each rule's best frame for its open `Look`. Verify: the new tests pass and every existing test in `tests/test_self_tuning.py` stays green.
- [x] 1.3 Refactor if needed, with tests green. Verify: `uv run pytest tests/test_self_tuning.py` passes.

## 2. Full suite

- [x] 2.1 Run the backend suite and linters. Verify: `uv run pytest` and `uv run ruff check . && uv run ruff format --check .` in `backend/` pass.
