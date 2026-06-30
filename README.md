# LegalSense AI — Production AI Legal Assistant

LegalSense AI is a production-grade AI-powered legal assistant designed to query, search, and analyze Indian Central Acts. Built using a robust Retrieval-Augmented Generation (RAG) architecture, it offers semantic search, automated citations, and multi-turn chat capabilities over statutory texts.

---

## Technical Stack

- **Backend**: FastAPI (Python 3.12)
- **Frontend**: Vite + React + TypeScript + Vanilla CSS
- **SQL Database**: PostgreSQL (via SQLAlchemy Asyncpg)
- **Vector Store**: Qdrant Database
- **Embeddings**: `sentence-transformers/all-MiniLM-L6-v2` (Local, CPU-efficient)
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

## Onboarding & Setup

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
- Generate vector embeddings for the chunks using the local embedding model.
- Upsert points into the Qdrant database.

---

## Running Tests

To run the full suite of unit and integration tests:

```bash
# Run pytest through the virtual environment runner
venv/Scripts/python -m pytest -v
```
To run tests with code coverage metrics:
```bash
venv/Scripts/python -m pytest --cov=backend --cov-report=term-missing
```
