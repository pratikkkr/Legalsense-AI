# Configuration Reference

All backend configuration lives in `backend/core/config.py` as a single
`pydantic-settings` `Settings` class. Every field can be set via an
environment variable of the same name, or via a `.env` file at the project
root (loaded automatically, one directory below where you'd expect —
`_PROJECT_ROOT = Path(__file__).resolve().parents[2]` resolves to the repo
root from `backend/core/config.py`). Variable names are case-insensitive.

Start from [`.env.example`](../.env.example) — copy it to `.env` and fill in
the required values. `.env` is gitignored; never commit real secrets.

## Contents

- [Application](#application)
- [Server / CORS](#server--cors)
- [Database](#database)
- [Qdrant](#qdrant)
- [Embeddings](#embeddings)
- [LLM provider](#llm-provider)
- [JWT authentication](#jwt-authentication)
- [Rate limiting](#rate-limiting)
- [RAG tuning](#rag-tuning)
- [Data paths](#data-paths)
- [Frontend](#frontend-vite-build-time)

---

## Application

| Variable | Type | Default | Description |
|---|---|---|---|
| `APP_NAME` | string | `LegalSense AI` | Shown in `/health` and API docs title |
| `APP_VERSION` | string | `1.0.0` | Shown in `/health` and API docs |
| `ENVIRONMENT` | `development` \| `staging` \| `production` | `development` | Controls JSON vs. human-readable logging |
| `DEBUG` | bool | `false` | Not currently read by application logic beyond `.env.example`'s default; reserved |
| `LOG_LEVEL` | string | `INFO` | Passed to `structlog`/stdlib logging |

## Server / CORS

| Variable | Type | Default | Description |
|---|---|---|---|
| `HOST` | string | `0.0.0.0` | Bind address (used when running `uvicorn` directly, not via the Docker `CMD`) |
| `PORT` | int | `8000` | Bind port |
| `ALLOWED_ORIGINS` | JSON array of strings | `["http://localhost:5173", "http://localhost:3000", "http://localhost:8080"]` | CORS allow-list, consumed by `CORSMiddleware` in `backend/main.py`. **Must include your deployed frontend's exact origin in production.** |

## Database

| Variable | Type | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | string | `postgresql+asyncpg://legalsense:legalsense@localhost:5432/legalsense` | Must use the `postgresql+asyncpg://` scheme (async driver). In `docker-compose.yml`, this is overridden with the containerized Postgres's credentials. |

## Qdrant

| Variable | Type | Default | Description |
|---|---|---|---|
| `QDRANT_HOST` | string | `localhost` | Set to your Qdrant Cloud cluster host in production |
| `QDRANT_PORT` | int | `6333` | |
| `QDRANT_COLLECTION` | string | `legal_sections` | Collection name; created automatically on first ingest if missing |
| `QDRANT_API_KEY` | string \| null | `null` | Required for Qdrant Cloud; leave unset for a local, unauthenticated instance |
| `QDRANT_TIMEOUT_SECONDS` | int | `30` | Client request timeout |

## Embeddings

| Variable | Type | Default | Description |
|---|---|---|---|
| `EMBEDDING_MODEL` | string | `all-MiniLM-L6-v2` | **Informational only** — the actual embedding calls in `backend/chains/embedding.py` hardcode Gemini's `text-embedding-004` model name (`GEMINI_EMBED_MODEL`), not this setting. Kept for documentation/future use; don't expect changing it to switch embedding models. |
| `EMBEDDING_DIMENSION` | int | `768` | Must match the embedding model's actual output dimension — used when creating the Qdrant collection's vector config |
| `EMBEDDING_BATCH_SIZE` | int | `100` | Texts per Gemini embedding API call during ingestion |

## LLM provider

| Variable | Type | Default | Description |
|---|---|---|---|
| `LLM_PROVIDER` | `gemini` \| `openai` \| `anthropic` \| `ollama` \| `azure_openai` | `gemini` | Selects the `LLMProvider` implementation — see [`architecture.md`](architecture.md#provider-agnostic-llm-layer) |
| `LLM_MODEL` | string | `gemini-2.0-flash` | Model name/deployment name, interpreted per-provider |
| `LLM_TEMPERATURE` | float | `0.2` | Sampling temperature |
| `LLM_MAX_TOKENS` | int | `4096` | Max output tokens per generation |
| `GEMINI_API_KEY` | string \| null | `null` | Required when `LLM_PROVIDER=gemini` — **also required regardless of `LLM_PROVIDER`**, since embeddings always go through Gemini |
| `OPENAI_API_KEY` | string \| null | `null` | Required when `LLM_PROVIDER=openai` |
| `ANTHROPIC_API_KEY` | string \| null | `null` | Required when `LLM_PROVIDER=anthropic` |
| `AZURE_OPENAI_API_KEY` | string \| null | `null` | Required when `LLM_PROVIDER=azure_openai` |
| `AZURE_OPENAI_ENDPOINT` | string \| null | `null` | Required when `LLM_PROVIDER=azure_openai`, e.g. `https://your-resource.openai.azure.com` |
| `AZURE_OPENAI_API_VERSION` | string | `2024-02-01` | |
| `OLLAMA_BASE_URL` | string | `http://localhost:11434` | Required when `LLM_PROVIDER=ollama`; no API key needed |

Missing the required key for the selected provider raises `RuntimeError` the
first time an LLM call is made (`create_llm_provider()` in
`backend/chains/llm.py`), not at application startup — the process will boot
successfully and fail on the first chat/search request.

## JWT authentication

| Variable | Type | Default | Description |
|---|---|---|---|
| `JWT_SECRET_KEY` | string | `CHANGE-ME-in-production-use-a-real-secret-key` | **Must be overridden.** `.env.example` ships this blank on purpose to force you to generate one (`openssl rand -hex 32`) — an *empty* `.env` value is treated as a real (empty) override by pydantic-settings, not as "unset falls through to the class default," so don't leave it blank. `docker-compose.yml` additionally refuses to start at all without a value via `${JWT_SECRET_KEY:?...}`. |
| `JWT_ALGORITHM` | string | `HS256` | |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | int | `30` | |
| `REFRESH_TOKEN_EXPIRE_DAYS` | int | `7` | |

## Rate limiting

| Variable | Type | Default | Description |
|---|---|---|---|
| `RATE_LIMIT_DEFAULT` | string (slowapi format) | `60/minute` | Applied globally |
| `RATE_LIMIT_AUTH` | string (slowapi format) | `10/minute` | Intended for `/api/v1/auth/*`; currently only the global limit is wired into `app.state.limiter` in `main.py` — see note below |

> **Note**: `RATE_LIMIT_AUTH` is defined in config but not currently applied
> as a per-route override anywhere in `backend/api/auth.py`. All routes,
> including auth, are presently subject only to `RATE_LIMIT_DEFAULT`. Worth
> confirming/fixing if tighter auth-route throttling is a requirement.

## RAG tuning

| Variable | Type | Default | Description |
|---|---|---|---|
| `RAG_TOP_K` | int | `8` | Chunks retrieved per query before dedup/truncation |
| `RAG_SCORE_THRESHOLD` | float | `0.35` | Minimum cosine similarity score to include a result |
| `RAG_MAX_CONTEXT_TOKENS` | int | `6000` | Token budget for retrieved context injected into the prompt (heuristic: 1 token ≈ 4 chars) |
| `RAG_CHUNK_SIZE` | int | `1000` | Words per chunk during ingestion |
| `RAG_CHUNK_OVERLAP` | int | `200` | Word overlap between consecutive chunks. Must be strictly less than `RAG_CHUNK_SIZE`, or `chunk_section()` raises `ValueError` rather than looping forever. |

## Data paths

| Variable | Type | Default | Description |
|---|---|---|---|
| `DATA_DIR` | path | `<repo root>/data` | Base directory; `raw_data_dir`/`processed_data_dir` properties derive `data/raw` and `data/processed` from it |

## Frontend (Vite build-time)

Not part of the backend `Settings` class — these are read by Vite at build
time via `import.meta.env`.

| Variable | Default | Description |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000` | Base URL the frontend calls for all `/api/v1/*` requests. Set this to your Render backend URL when deploying to Vercel. |

---

## A note on secrets hygiene

- `.env` is gitignored. Never commit it.
- `docker-compose.yml` requires `JWT_SECRET_KEY`, `POSTGRES_PASSWORD`, and
  `GEMINI_API_KEY` via `${VAR:?message}` syntax — the stack will not start
  with these unset, rather than silently using an insecure default.
- Generate secrets fresh per environment. Never reuse a `JWT_SECRET_KEY` or
  database password between local, staging, and production.
