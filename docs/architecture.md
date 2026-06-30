# LegalSense AI — System Architecture

This document details the architectural design and structural choices for LegalSense AI.

## Directory Structure

```
Legalsense-ai/
├── backend/
│   ├── main.py                  # FastAPI app entry point
│   ├── api/                     # API routers (auth, acts, search, chat, health)
│   ├── core/                    # Core configs, logging, db, models, security
│   ├── schemas/                 # Pydantic validation schemas
│   ├── services/                # Business logic services (acts, search, chat)
│   ├── chains/                  # RAG components (embedding, retriever, prompts, RAG)
│   └── agents/                  # Multi-tool LLM agents
├── frontend/
│   ├── src/                     # React application source (pages, hooks, layouts)
│   └── public/                  # Static assets
├── scripts/
│   ├── ingest/                  # PDF parser pipeline
│   └── seed_db.py               # Database and Qdrant vector store seeder
├── docker/
│   ├── Dockerfile.backend       # Multi-stage python image
│   ├── Dockerfile.frontend      # Multi-stage serve image
│   └── nginx.conf               # SPA routing + API reverse proxy
├── docker-compose.yml           # Complete containerized local stack
├── requirements.txt             # Python dependencies
└── README.md                    # Setup and onboarding manual
```

---

## Technical Architecture

### 1. Request Flow (FastAPI Backend)
```
[Client App] ──(HTTPS)──> [Nginx Reverse Proxy]
                                  │
                       ┌──────────┴──────────┐
                (Static Assets)          (API /api/v1/*)
                       │                     │
                       ▼                     ▼
               [React App Bundle]     [FastAPI Application]
                                             │
                                     [Request Tracing]
                                             │
                                     [Auth Dependency]
                                             │
                                     [Service Layer]
                                     ┌───────┴───────┐
                                     ▼               ▼
                              [SQL Database]   [AI RAG Chain]
                                                     │
                                             [Embedding Service]
                                             [Qdrant Retriever]
                                             [LLM Provider Layer]
```

### 2. Provider-Agnostic LLM Layer
The LLM layer abstracts API connectivity behind the `LLMProvider` abstract base class (located in `backend/chains/llm.py`). It permits hot-swapping between the following providers through config only:
*   **Google Gemini** (Default: `gemini-2.0-flash`)
*   **OpenAI**
*   **Anthropic**
*   **Azure OpenAI**
*   **Ollama** (Local execution)

### 3. RAG Retrieval Design
*   **Ingestion & Chunking**: Indian Central Acts (PDFs) are cleaned, parsed into JSON, split into chunks of 1000 words with 200 words overlap, and embedded using `sentence-transformers/all-MiniLM-L6-v2` locally (generating 384-dimension vectors).
*   **Vector Database**: Points are persisted in **Qdrant** with keyword payload filters (`act_slug`, `chapter`, `section_number`).
*   **Hybrid Search**: Dense cosine similarity vector matching combined with metadata keyword filters.
*   **Citation Processing**: LLM outputs citations in standard format `[Section X, Act Name]`, which are resolved back to specific vector source metadata by the RAG orchestrator.

### 4. Security Controls
*   **Authentication**: JWT-based stateless tokens. Access token (30-min life) + Refresh token (7-day life) persisted in client localStorage.
*   **Password Hashing**: Cryptographic hashes generated and verified via `bcrypt` / `passlib`.
*   **Database Access**: Eager relationships loading (`selectinload`) to prevent N+1 queries. Parameterized queries executed through SQLAlchemy ORM.
*   **Rate Limiting**: Slowapi middleware restricts endpoints (defaults to 60/min globally, 10/min on auth).
