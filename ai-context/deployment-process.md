# Deployment Guide

Two supported ways to run LegalSense AI in production: **Docker Compose**
(everything on one host) or a **split cloud deploy** across free-tier
platforms. Both run identical application code — pick based on whether you
want one host to manage or zero infrastructure to manage.

## Contents

- [Choosing a path](#choosing-a-path)
- [Path A — Docker Compose](#path-a--docker-compose)
- [Path B — Free-tier cloud deploy](#path-b--free-tier-cloud-deploy)
- [Seeding data](#seeding-data)
- [Environment variables reference](#environment-variables-reference)
- [Post-deploy checklist](#post-deploy-checklist)
- [Troubleshooting](#troubleshooting)
- [Production hardening](#production-hardening)

---

## Choosing a path

| | Docker Compose | Cloud (Vercel + Render + Neon + Qdrant Cloud) |
|---|---|---|
| Cost | Cost of your host (VPS, on-prem) | $0 to start (all free tiers) |
| Setup time | ~5 minutes if Docker is installed | ~20–30 minutes (4 accounts to create) |
| Control | Full — you own the host | Limited to each platform's free-tier resources |
| Cold starts | None | Render free web services sleep after 15 min idle (~30–60s wake-up) |
| Best for | Self-hosting, VPS, internal deployments | Public demos, low-traffic production, zero-ops |

---

## Path A — Docker Compose

### Prerequisites

- [Docker](https://www.docker.com/) and Docker Compose (bundled with Docker
  Desktop)
- A Google Gemini API key ([Google AI Studio](https://aistudio.google.com/),
  free tier available)

### Steps

1. **Configure secrets.**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and set:
   - `GEMINI_API_KEY` — your key
   - `JWT_SECRET_KEY` — generate with `openssl rand -hex 32`
   - `POSTGRES_PASSWORD` — a strong password of your choosing

   `docker-compose.yml` uses `${VAR:?message}` for these three — the stack
   **will refuse to start** if any are unset, rather than silently falling
   back to an insecure default.

2. **Build and start the stack.**
   ```bash
   docker-compose up --build
   ```
   This starts four containers:
   - `legalsense_db` — PostgreSQL 16, with a healthcheck gate
   - `legalsense_qdrant` — Qdrant, with a healthcheck gate
   - `legalsense_backend` — FastAPI, waits for both healthchecks before starting
   - `legalsense_frontend` — Nginx serving the built React app on port 80,
     reverse-proxying `/api/v1/*`, `/docs`, and `/openapi.json` to the backend

3. **Seed the data** (see [Seeding data](#seeding-data) below).

4. **Verify.**
   - `http://localhost` — the app
   - `http://localhost:8000/health` — liveness probe
   - `http://localhost:8000/health/ready` — readiness probe (checks Postgres + Qdrant connectivity)
   - `http://localhost:8000/docs` — interactive API docs

5. **Stop the stack.**
   ```bash
   docker-compose down          # stop, keep volumes (data persists)
   docker-compose down -v       # stop and delete volumes (fresh start)
   ```

### Running behind your own reverse proxy / TLS terminator

`docker-compose.yml` exposes the frontend on port 80 and the backend on port
8000 directly. For a real public deployment, put a TLS-terminating proxy
(Caddy, another Nginx, Cloudflare Tunnel, etc.) in front of port 80 rather
than exposing it raw — the bundled `docker/nginx.conf` does not handle TLS
itself.

---

## Path B — Free-tier cloud deploy

Four platforms, one free account each, no credit card required for the tiers
used here.

### Prerequisites

- A GitHub account with this repo (or your fork) accessible
- A Google Gemini API key

### Step 1 — Database: Neon

1. Create a project at [neon.tech](https://neon.tech).
2. Copy the connection string from the dashboard. It looks like:
   ```
   postgresql://<user>:<password>@<host>/<database>?sslmode=require
   ```
3. Convert it to the async-driver form the app expects — change the scheme
   and `sslmode` param:
   ```
   postgresql+asyncpg://<user>:<password>@<host>/<database>?ssl=require
   ```
   Save this as your `DATABASE_URL`.

### Step 2 — Vector store: Qdrant Cloud

1. Create a free cluster at [cloud.qdrant.io](https://cloud.qdrant.io).
2. From the cluster dashboard, copy:
   - **Host** (e.g. `xxxxxxxx-xxxx.aws.cloud.qdrant.io`) → `QDRANT_HOST`
   - **API key** → `QDRANT_API_KEY`
   - Port is `6333` (`QDRANT_PORT`)

### Step 3 — Backend: Render

1. Go to [render.com](https://render.com) → **New +** → **Blueprint**.
2. Point it at this repository. Render reads [`render.yaml`](../render.yaml)
   and provisions a Docker-based web service automatically.
3. Fill in the environment variables Render prompts for (everything marked
   `sync: false` in the blueprint):

   | Variable | Value |
   |---|---|
   | `DATABASE_URL` | from Step 1 |
   | `QDRANT_HOST` | from Step 2 |
   | `QDRANT_API_KEY` | from Step 2 |
   | `GEMINI_API_KEY` | your Gemini key |
   | `JWT_SECRET_KEY` | `openssl rand -hex 32` |
   | `ALLOWED_ORIGINS` | leave blank for now — fill in after Step 4 |

4. Deploy. Note the resulting URL, e.g.
   `https://legalsense-backend.onrender.com`.

### Step 4 — Frontend: Vercel

1. Go to [vercel.com](https://vercel.com) → **New Project** → import this
   repository.
2. Set **Root Directory** to `frontend`.
3. Add an environment variable: `VITE_API_URL` = your Render backend URL
   from Step 3.
4. Deploy. [`frontend/vercel.json`](../frontend/vercel.json) already
   configures the SPA rewrite rule so client-side routes (`/chat`,
   `/search`, `/acts`) don't 404 on direct load or refresh.

### Step 5 — Close the CORS loop

Go back to Render, set `ALLOWED_ORIGINS` to a JSON array containing your
Vercel URL:
```
["https://your-app.vercel.app"]
```
Redeploy the backend. **This step is easy to forget and is the most common
reason a fresh deploy "doesn't work"** — without it, the deployed frontend's
API requests are blocked by CORS and every request fails silently in the
browser console.

### Step 6 — Seed the data

See [Seeding data](#seeding-data) below — run it from your own machine,
pointed at the production `DATABASE_URL`/`QDRANT_HOST`/`QDRANT_API_KEY`.

### Known limitation of this path

Render's free web services spin down after 15 minutes of inactivity. The
first request after idling takes roughly 30–60 seconds while the container
restarts. This is a Render free-tier characteristic, not an application bug.

---

## Seeding data

Both deployment paths need this step once (it's idempotent — re-running it
is safe and skips Acts that already exist).

```bash
pip install -r requirements-dev.txt   # or requirements.txt if not developing
python scripts/seed_db.py
```

What it does:
1. Creates all Postgres tables (`Base.metadata.create_all`).
2. Reads the 14 pre-parsed Act JSON files from `data/processed/`.
3. Chunks each Act's sections (1000 words, 200-word overlap).
4. Embeds every chunk via the Gemini embeddings API.
5. Upserts vectors into the configured Qdrant collection.

For the cloud path, run this from your local machine with environment
variables pointed at your production `DATABASE_URL`, `QDRANT_HOST`,
`QDRANT_API_KEY`, and `GEMINI_API_KEY` — either export them in your shell for
the one-off run, or temporarily point your local `.env` at the production
values (make sure not to commit it).

---

## Environment variables reference

The full reference lives in [`configuration.md`](configuration.md). The
variables every deployment must set are:

| Variable | Required | Notes |
|---|---|---|
| `GEMINI_API_KEY` | Yes (if `LLM_PROVIDER=gemini`, the default) | Also used for embeddings regardless of `LLM_PROVIDER` |
| `JWT_SECRET_KEY` | Yes | `openssl rand -hex 32`; never reuse across environments |
| `DATABASE_URL` | Yes | `postgresql+asyncpg://...` |
| `QDRANT_HOST` | Yes | `localhost` for Docker Compose, cluster host for Qdrant Cloud |
| `QDRANT_API_KEY` | Cloud only | Qdrant Cloud requires it; local Qdrant does not |
| `ALLOWED_ORIGINS` | Yes | JSON array of allowed frontend origins for CORS |
| `POSTGRES_PASSWORD` | Docker Compose only | Sets both the container's Postgres password and the backend's `DATABASE_URL` |

---

## Post-deploy checklist

- [ ] `GET /health` returns `{"status": "healthy"}`
- [ ] `GET /health/ready` returns `{"status": "ready", ...}` with both
      `database` and `vector_store` checks `"ok"`
- [ ] Registering a new account succeeds (`POST /api/v1/auth/register`)
- [ ] Logging in returns an access + refresh token pair
- [ ] `scripts/seed_db.py` has been run at least once against this
      database/Qdrant instance
- [ ] `GET /api/v1/acts` returns 14 Acts
- [ ] A chat message returns a response with at least one citation
- [ ] (Cloud path) `ALLOWED_ORIGINS` includes the deployed frontend's exact
      origin, and the browser console shows no CORS errors

---

## Troubleshooting

**`GEMINI_API_KEY is required when LLM_PROVIDER=gemini`** — the backend
raises this on the first LLM call if the key is missing, not at startup.
Set `GEMINI_API_KEY` and restart the backend.

**Chat/search requests fail with a 500 and empty results** — usually means
`scripts/seed_db.py` hasn't been run yet, so Qdrant has no vectors to
retrieve. Check `GET /health/ready`'s `vector_store` field, and confirm
`GET /api/v1/acts` returns data.

**Frontend loads but every API call fails in the browser console with a
CORS error** — `ALLOWED_ORIGINS` on the backend doesn't include the
frontend's actual origin. It must be an exact match (scheme + host, no
trailing slash), set as a JSON array.

**`docker-compose up` fails immediately with `POSTGRES_PASSWORD must be set
in .env`** — this is intentional (see Path A, step 1). Create `.env` from
`.env.example` and fill in the three required secrets.

**Render service builds but crashes on start** — check the Render logs for
which environment variable is missing; `backend/core/config.py` fields
without a default will raise a validation error at import time if unset via
a required setting, or the LLM factory will raise `RuntimeError` on first
use if only the API key is missing.

**Section text or search results look truncated or wrong after re-seeding**
— `scripts/seed_db.py` is idempotent for *creating* Acts but does not
delete stale Qdrant points if chunking parameters change. If you modify
`RAG_CHUNK_SIZE`/`RAG_CHUNK_OVERLAP` and re-seed, drop and recreate the
Qdrant collection first (`docker-compose down -v` locally, or delete the
collection via the Qdrant Cloud dashboard).

---

## Production hardening

Beyond a working deploy, consider before serving real users:

- **Move JWT storage off `localStorage`** to httpOnly cookies with CSRF
  protection — documented as a known, deliberately deferred gap in
  [`architecture.md`](architecture.md#security-architecture).
- **Gate or disable `/docs` and `/openapi.json`** in production — they're
  proxied publicly by default (`docker/nginx.conf`), which is convenient for
  early integration work but discloses your full API surface.
- **Run `pip-audit` and `npm audit`** before each release; dependency
  versions are pinned but not continuously monitored for new CVEs.
- **Set up log aggregation** — `structlog` emits JSON logs when
  `ENVIRONMENT=production`; ship them somewhere durable (they're not
  persisted by default in either deployment path).
- **Back up Postgres** — Neon and self-hosted Postgres both need an explicit
  backup policy; nothing in this repo configures one.
- **Consider database connection pooling limits** at your Postgres provider
  if you scale the backend horizontally — `asyncpg`'s default pool size per
  process can exhaust a free-tier connection limit under load.
