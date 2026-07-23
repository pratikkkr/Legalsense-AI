# Contributing

Thanks for taking an interest in the project. This covers how to get set up
and what we expect from a PR. For the deeper technical stuff (local setup,
testing patterns, conventions) check `ai-context/development.md`.

## Getting started

- Small fix (typo, obvious bug)? Just send a PR.
- Anything bigger — new feature, RAG pipeline changes, architecture stuff —
  open an issue first so we can talk through the approach before you sink
  time into it.
- If you're new to the codebase, `ai-context/architecture.md` covers the
  request flow and the reasoning behind a few non-obvious design choices.

## Workflow

1. Fork (or branch directly if you have write access).
2. `ai-context/development.md#local-setup` has the setup steps.
3. Branch off with a `type/short-description` name — `feat/`, `fix/`,
   `docs/`, `refactor/`, `test/`, or `chore/`. E.g. `fix/search-history-pagination`.
4. Before opening the PR, run:
   ```bash
   ruff check .
   pytest --cov=backend --cov-report=term-missing
   cd frontend && npm run lint && npm run build
   ```
5. Open the PR against `main`.

## Commits

Imperative, present tense ("Fix search pagination", not "Fixed"). Keep the
first line short; explain *why* in the body if it's not obvious from the
diff. Reference an issue if there is one.

## Code style

CI runs `ruff check .` on the backend and `oxlint`/`tsc --strict`/`vite build`
on the frontend — run these yourself before pushing, don't wait for CI to
tell you. Config is in `pyproject.toml`.

A few conventions worth knowing beyond the linter (more detail in
`ai-context/development.md`): routers call into services, never the ORM
directly; authorization is an explicit `.where(user_id == ...)` in the
service, not a shared decorator; tunable numbers live in
`backend/core/config.py` rather than scattered as magic constants.

## Tests

New backend code needs a test — API behavior goes in `tests/test_api_*.py`,
service logic in `tests/test_*_service.py`. A bug fix should come with a
regression test. `ai-context/development.md#testing` covers the
`mock_llm_provider`/`mock_qdrant` fixtures most new tests will need.

No hard coverage number to hit, but a new module with zero tests will get
asked for some before merge. Frontend doesn't have a test runner set up yet
— a clean build plus manually checking the affected page is the current bar.

## PRs

- Fill in the template.
- Keep it green — both CI jobs need to pass.
- Keep it focused. One bug or one feature per PR is much easier to review
  than a grab-bag.
- If you disagree with review feedback, say so and explain why instead of
  just going along with it — that's more useful to the reviewer than silent
  compliance.

## What not to do

- Don't add abstractions "for later" — wait until a second real use case
  needs it.
- Don't reformat files you're not otherwise touching.
- Don't add error handling for inputs that literally can't happen (already
  guaranteed by a schema).
- Don't bundle an unrelated fix into your PR — split it out.
- Don't commit `.env` or real API keys.

## Bugs and feature requests

Use the issue templates. For bugs: what you expected, what happened, repro
steps, and your deployment path (Docker / cloud) + `LLM_PROVIDER`.

## Security issues

Don't file these as a public issue — see `SECURITY.md`.
