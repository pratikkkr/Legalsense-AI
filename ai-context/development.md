# Development Guide

How to set up a local dev environment, the project's coding standards, and
how the test suite is organized. For contribution *process* (branching, PR
etiquette), see [`CONTRIBUTING.md`](../CONTRIBUTING.md) — this document is
the technical reference that guide points back to.

## Contents

- [Local setup](#local-setup)
- [Project conventions](#project-conventions)
- [Linting and formatting](#linting-and-formatting)
- [Type checking](#type-checking)
- [Testing](#testing)
- [Adding a new API endpoint](#adding-a-new-api-endpoint)
- [Adding a new environment variable](#adding-a-new-environment-variable)
- [Debugging tips](#debugging-tips)

---

## Local setup

### Backend

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

pip install -r requirements-dev.txt   # runtime deps + pytest + ruff
cp .env.example .env                  # fill in GEMINI_API_KEY, JWT_SECRET_KEY, POSTGRES_PASSWORD

docker compose up -d db qdrant        # just the two data services
uvicorn backend.main:app --reload --port 8000
```

`--reload` watches `backend/` for changes. `http://localhost:8000/docs` gives
you an interactive Swagger UI for manual testing without needing the
frontend running.

### Frontend

```bash
cd frontend
npm install
npm run dev       # http://localhost:5173, hot module reload
```

The dev server proxies nothing by default — `VITE_API_URL` defaults to
`http://localhost:8000` (see `frontend/src/api/client.ts`), so run the
backend on that port or set `VITE_API_URL` in `frontend/.env.local`.

### Seed some data to work with

```bash
python scripts/seed_db.py
```

Idempotent — safe to re-run any time.

---

## Project conventions

- **Routers never touch the ORM or Qdrant directly.** A route handler in
  `backend/api/*.py` should be a thin adapter: parse the request (Pydantic
  does this automatically), call a method on the matching
  `backend/services/*.py` class, translate the result or a caught
  `ValueError` into an HTTP response. All actual logic — queries,
  authorization checks, orchestration — lives in the service. This is what
  makes services unit-testable without spinning up HTTP (see
  `tests/test_chat_service.py` for the pattern).
- **Authorization is explicit at the query level.** Don't add a shared
  "check ownership" decorator — write `.where(Model.user_id == user_id)`
  directly in the service method that needs it, matching every existing
  service. It's slightly more repetition in exchange for the authorization
  logic being visible exactly where the query runs.
- **Config, not constants.** A hardcoded number that might reasonably need
  tuning per-deployment (timeouts, batch sizes, thresholds) belongs in
  `backend/core/config.py` as a `Settings` field, not as a module-level
  constant. See [`configuration.md`](configuration.md) for the full list —
  add new entries there when you add a new setting.
- **No comments explaining *what* the code does.** Identifiers should be
  self-explanatory; a comment is only warranted for a non-obvious *why*
  (a workaround, a subtle invariant, a constraint that isn't visible from
  the code itself).
- **Frontend types are hand-mirrored, not generated.** `frontend/src/types/index.ts`
  is manually kept in sync with `backend/schemas/*.py` — there's no
  OpenAPI codegen step. When you change a Pydantic response model, update
  the matching TypeScript interface in the same PR.
- **Retrieved/external text is untrusted in prompts.** Any text pulled from
  Qdrant or a tool call and interpolated into an LLM prompt must be treated
  as data, not instructions — see the delimiter pattern in
  `backend/agents/legal_agent.py` and the system-prompt guideline in
  `backend/chains/prompts.py`. Don't remove these when touching the RAG
  chain or agent.

---

## Linting and formatting

[`pyproject.toml`](../pyproject.toml) configures `ruff` for both linting and
import sorting:

```bash
ruff check .            # lint
ruff check . --fix      # lint + auto-fix what's safe to auto-fix
ruff format .           # format
```

`B008` (function calls in argument defaults) is disabled — FastAPI's
`Depends(...)` pattern relies on exactly that, so it's not a real issue here.

Frontend linting uses `oxlint`:

```bash
cd frontend
npm run lint
```

Both run in CI (`.github/workflows/ci.yml`) on every push and PR.

---

## Type checking

Backend: no `mypy` yet — type hints exist throughout
(`from __future__ import annotations`, typed signatures) but aren't
currently enforced by a type checker in CI. Worth adding if the codebase
grows; not set up today.

Frontend: `tsconfig.app.json` has `"strict": true`. Check with:

```bash
cd frontend
npx tsc -b --force   # --force to bypass the incremental build cache when debugging
```

`npm run build` runs this as its first step (`tsc -b && vite build`), so a
type error fails the build, not just the lint pass.

---

## Testing

```bash
pytest -v                                          # run everything
pytest --cov=backend --cov-report=term-missing      # with coverage
pytest tests/test_api_chat.py -v                    # one file
pytest -k "test_chat_creates" -v                     # by name pattern
```

### How the test suite is set up

`tests/conftest.py` provides the shared fixtures:

- `client` — an `httpx.AsyncClient` wired to the real FastAPI app via
  `ASGITransport`, with the `get_db` dependency overridden to use an
  in-memory SQLite database (`sqlite+aiosqlite:///:memory:`) instead of
  Postgres. This means integration tests exercise the actual route → service
  → ORM code path, just against a different database backend.
- `test_user` / `auth_headers` — a pre-created user and a valid
  `Authorization` header for tests that need an authenticated caller.
- `mock_llm_provider` — a fake `LLMProvider` with scriptable
  `.generate`/`.generate_with_tools` return values, patched into every
  module that imports `create_llm_provider` directly (`backend.chains.rag`,
  `backend.agents.legal_agent`, and the source module itself — patching
  only the source isn't enough because those modules do
  `from backend.chains.llm import create_llm_provider`, which copies the
  reference at import time).
- `mock_qdrant` — patches `get_qdrant_client`/`embed_query` where
  `HybridRetriever` imports them, returning zero hits by default. Override
  `client.query_points.return_value` in a test for specific retrieval
  results.

### Writing a new test

- API-level behavior (status codes, response shape, auth) → a
  `tests/test_api_*.py` file using the `client` fixture.
- Service-level logic (without HTTP) → a `tests/test_*_service.py` file
  using the `db_session`/`test_user` fixtures directly against the service
  class.
- Anything that constructs an `LLMProvider` or `RAGChain`/`LegalAgent`
  (directly or transitively, e.g. via `ChatService.__init__`, which always
  builds a `RAGChain`) needs `mock_llm_provider` in the test's parameters,
  even if the test doesn't call an LLM-dependent method — the constructor
  itself calls `create_llm_provider()`, which raises if no API key is
  configured in the test environment.
- Anything that calls `HybridRetriever.retrieve()` (directly or via a
  service) needs `mock_qdrant`.

No frontend test runner is configured yet (no Jest/Vitest/RTL) — frontend
correctness is currently verified via `tsc`/`vite build` plus manual
browser testing. Adding component tests is a reasonable next step if the
frontend grows.

---

## Adding a new API endpoint

1. Define the request/response Pydantic models in `backend/schemas/<resource>.py`.
2. Add the business logic as a method on the matching
   `backend/services/<resource>_service.py` class (create the file if the
   resource is new).
3. Add the route in `backend/api/<resource>.py`, delegating to the service.
   Add `Depends(get_current_user)` unless the endpoint is intentionally
   public.
4. Register the router in `backend/main.py` if it's a new file
   (`app.include_router(...)`).
5. Add the matching TypeScript type to `frontend/src/types/index.ts` and a
   client method to `frontend/src/api/client.ts` if the frontend needs it.
6. Write an API-level test in `tests/test_api_<resource>.py`.
7. Update [`api-reference.md`](api-reference.md) with the new endpoint.

## Adding a new environment variable

1. Add the field to `Settings` in `backend/core/config.py` with a sensible
   default (or `None` if it's a secret with no safe default).
2. Add it to `.env.example` with a comment explaining what it's for.
3. If it's required in production, add it to `render.yaml`'s `envVars` list.
4. Document it in [`configuration.md`](configuration.md).

## Debugging tips

- `GET /health/ready` tells you immediately whether Postgres or Qdrant
  connectivity is the problem before you go digging further.
- Structured logs (`structlog`) are JSON in production
  (`ENVIRONMENT=production`) and human-readable otherwise — set
  `ENVIRONMENT=development` locally if you want readable console output.
- `LLMProvider` instances are cached as a module-level singleton
  (`create_llm_provider()`); if you change `LLM_PROVIDER` or an API key at
  runtime without restarting the process, you won't see the change take
  effect — the cached instance is reused for the life of the process.
- When a test involving `ChatService` or `RAGChain` fails with
  `RuntimeError: GEMINI_API_KEY is required`, you forgot to add
  `mock_llm_provider` to that test's parameters — see
  [Testing](#testing) above.
