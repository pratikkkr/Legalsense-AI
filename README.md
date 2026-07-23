# LegalSense AI

An AI assistant for querying and searching Indian Central Acts. It's built
on a RAG pipeline — the answers are grounded in the actual statutory text
instead of whatever the model remembers, and every claim gets cited back to
a specific Act and Section.

---

## Technical Stack

- **Backend**: FastAPI (Python 3.12)
- **Frontend**: Vite + React + TypeScript + Vanilla CSS
- **SQL Database**: PostgreSQL (via SQLAlchemy Asyncpg)
- **Vector Store**: Qdrant Database
- **Embeddings**: Google Gemini `text-embedding-004` (768-dim, via API — no local model/GPU required)
- **LLM Provider**: Provider-agnostic abstraction layer (Supports Google Gemini, OpenAI, Anthropic, Ollama, Azure)
- **Proxy/Web**: Nginx

---

## Core Features

1. **Hybrid Legal Search**: Dense vector search combined with keyword metadata filtering (Act slug, chapters).
2. **AI Consultation Chat**: Stateful multi-turn conversation with memory context tuning.
3. **Automated Citations**: Resolves LLM statutory references back to raw vector payload metadata.
4. **Document Browser**: Eagerly loaded multi-column provisions reader with local State Amendment alerts.
5. **Secure Authentication**: JWT credentials verification and refresh token lifecycle.

---

## Setup

### Prerequisites

- [Docker & Docker Compose](https://www.docker.com/)
- [Node.js v20+](https://nodejs.org/)
- [Python 3.12](https://www.python.org/)
- A **Google Gemini API Key** (Required for legal reasoning responses)

### Quick Start with Docker (Single Command)

1. Create a `.env` file at the root of the project using the template:
   ```bash
   cp .env.example .env
   ```
2. Open `.env` and fill in your `GEMINI_API_KEY`:
   ```env
   GEMINI_API_KEY=your_actual_key_here
   ```
3. Start the entire container stack:
   ```bash
   docker-compose up --build
   ```
   *This starts Postgres, Qdrant, FastAPI backend, and Nginx proxying the React frontend on `http://localhost`.*

4. In a separate terminal, seed the database with the Indian Central Acts:
   ```bash
   # Enter virtualenv
   .\venv\Scripts\activate
   # Seed acts into DB and vectors into Qdrant
   python scripts/seed_db.py
   ```

---

## Deploy for Free (Vercel + Render + Neon + Qdrant Cloud)

The fastest path to a live, public deployment with no credit card, using each
platform's free tier:

1. **Database — [Neon](https://neon.tech)**: create a free Postgres project,
   then copy its connection string (starts `postgresql://...`). Convert it to
   the async driver form the app expects:
   `postgresql+asyncpg://<user>:<password>@<host>/<db>?ssl=require`.

2. **Vector store — [Qdrant Cloud](https://cloud.qdrant.io)**: create a free
   cluster, then copy its **host** (e.g. `xxxxxxxx-xxxx.aws.cloud.qdrant.io`)
   and **API key** from the cluster dashboard.

3. **Backend — [Render](https://render.com)**: click "New +" → "Blueprint",
   point it at this repo — Render reads [`render.yaml`](render.yaml) and
   provisions the service automatically. Fill in the env vars it prompts for
   (marked `sync: false` in the blueprint): `DATABASE_URL` (from step 1),
   `QDRANT_HOST` + `QDRANT_API_KEY` (from step 2), `GEMINI_API_KEY`,
   `JWT_SECRET_KEY` (generate with `openssl rand -hex 32`), and
   `ALLOWED_ORIGINS` (you'll fill this in after step 4). Once deployed, note
   the backend's public URL (e.g. `https://legalsense-backend.onrender.com`).

4. **Frontend — [Vercel](https://vercel.com)**: import this repo as a new
   project, set the **root directory** to `frontend`, and add an environment
   variable `VITE_API_URL` pointing at your Render backend URL from step 3.
   Deploy. [`frontend/vercel.json`](frontend/vercel.json) already handles SPA
   routing so client-side routes (`/chat`, `/search`, `/acts`) work on
   direct load/refresh.

5. **Close the loop — CORS**: go back to Render and set `ALLOWED_ORIGINS` to
   a JSON array containing your Vercel URL, e.g.
   `["https://your-app.vercel.app"]`, then redeploy the backend. Without
   this step the deployed frontend's requests will be blocked by CORS.

6. **Seed the data**: from your machine, with `requirements-dev.txt`
   installed, run `scripts/seed_db.py` with `DATABASE_URL`/`QDRANT_HOST`/
   `QDRANT_API_KEY`/`GEMINI_API_KEY` set to your production values (export
   them in your shell, or point `.env` at the same values temporarily) —
   this populates Neon and Qdrant Cloud with the 14 bundled Acts.

Free-tier caveat: Render's free web services spin down after 15 minutes of
inactivity, so the first request after idling takes ~30-60s to wake up.

Prefer full control over free-tier limits, or need this running on your own
infrastructure? Use the Docker Compose path above/below instead — it's the
same application, just self-hosted.

---

## Local Development Setup

If you wish to run the backend and frontend servers outside Docker containers:

### 1. Backend API Server

1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Start Postgres and Qdrant locally (or run them via Docker):
   ```bash
   docker compose up -d db qdrant
   ```
3. Run the FastAPI development server:
   ```bash
   uvicorn backend.main:app --reload --port 8000
   ```
   *Open `http://localhost:8000/docs` to view the interactive OpenAPI documentation.*

### 2. Frontend SPA Server

1. Change directory to frontend and install packages:
   ```bash
   cd frontend
   npm install
   ```
2. Start Vite HMR server:
   ```bash
   npm run dev
   ```
   *The application will open on `http://localhost:5173`.*

---

## Database Seeding

The database seeder is idempotent and should be run to populate Postgres and Qdrant from the pre-processed JSON acts:

```bash
python scripts/seed_db.py
```
This script will:
- Initialize the SQLAlchemy Postgres tables.
- Ingest and chunk all processed Acts in `data/processed/`.
- Generate vector embeddings for the chunks via the Gemini embeddings API.
- Upsert points into the Qdrant database.

---

## Running Tests

Install development dependencies (runtime deps + pytest + ruff) once:

```bash
pip install -r requirements-dev.txt
```

Run the full suite of unit and integration tests:

```bash
pytest -v
```
With code coverage metrics:
```bash
pytest --cov=backend --cov-report=term-missing
```
Lint the backend:
```bash
ruff check .
```

CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs all of the
above, plus the frontend's `npm run lint` and `npm run build`, on every push
and pull request.

---

## More docs

There's a Swagger UI at `/docs` on any running backend instance if you want
to poke at the API directly. For deeper notes on the architecture, the RAG
pipeline, config, and deployment, check the `ai-context/` folder — that's
where the longer writeups live so this file doesn't turn into a wall of text.
