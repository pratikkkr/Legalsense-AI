# Security Policy

## Supported versions

This project does not yet maintain multiple released versions — security
fixes are applied to the `main` branch. There is no LTS or backport policy
at this stage.

## Reporting a vulnerability

**Do not open a public GitHub issue for a security vulnerability.** Public
issues are visible to everyone immediately, including anyone who might
exploit the report before a fix ships.

Instead:

1. **Preferred**: use GitHub's private vulnerability reporting — go to the
   repository's **Security** tab → **Report a vulnerability**. This opens a
   private advisory visible only to maintainers until a fix is ready.
   *(If this option isn't visible, it means the repository owner hasn't
   enabled it yet under Settings → Security → "Private vulnerability
   reporting" — enabling it is recommended.)*
2. If private reporting isn't available, open an issue with minimal detail
   (e.g. "Potential security issue — requesting private contact") and wait
   for a maintainer to respond with a secure channel, rather than posting
   exploit details publicly.

Please include, as applicable:
- The affected component (backend route, frontend page, dependency, infra
  config)
- Steps to reproduce, or a proof of concept
- The potential impact (what an attacker could do)
- Any suggested fix, if you have one

We'll acknowledge reports and aim to keep you updated as a fix is developed.
Coordinated disclosure is appreciated — please give us a reasonable window
to ship a fix before any public disclosure.

## Scope

In scope:
- The FastAPI backend (`backend/`)
- The React frontend (`frontend/`)
- Deployment configuration (`docker/`, `docker-compose.yml`, `render.yaml`,
  `frontend/vercel.json`)
- The ingestion/seeding scripts (`scripts/`)

Out of scope:
- Third-party services this project depends on (Google Gemini, Qdrant,
  Postgres, Render, Vercel, Neon) — report those to the respective vendor
- Denial-of-service via sheer traffic volume against a public deployment you
  don't control
- Social engineering, physical security

## Known issues we already know about

No need to re-report these — they're on our radar, just not fixed yet:

- **JWT tokens live in `localStorage`**, which any script on the page can
  read (XSS-stealable). Fixing it properly means httpOnly cookies + CSRF
  protection + login flow changes on both ends — it's on the list, just
  hasn't been done. More context in `ai-context/architecture.md`.
- **`/docs` and `/openapi.json` are open to the public** through the default
  Nginx config. Fine for early integration work, worth turning off
  (`docs_url=None` in `backend/main.py`) before a real launch.
- **No Alembic migrations set up** — `Base.metadata.create_all()` only adds
  new tables/columns, never alters existing ones. Not a security hole, but
  worth knowing before the schema needs to change post-launch. See
  `ai-context/database.md`.

## What's already handled

JWT auth with bcrypt hashing, authorization checks at the service layer (not
just per-route), parameterized queries everywhere, input validation on every
request schema, rate limiting, and untrusted text getting delimited before
it hits an LLM prompt. No secrets ship with the repo — `docker-compose.yml`
won't start without real values for `JWT_SECRET_KEY`, `POSTGRES_PASSWORD`,
and `GEMINI_API_KEY`.
