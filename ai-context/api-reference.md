# API Reference

Base URL: `/api/v1` (e.g. `http://localhost:8000/api/v1` locally, or
`https://your-backend.onrender.com/api/v1` in the cloud deploy).

An interactive version of this reference (auto-generated from the Pydantic
schemas) is always available at `/docs` (Swagger UI) and `/redoc` while the
backend is running.

## Contents

- [Authentication](#authentication)
- [Conventions](#conventions)
- [Health](#health)
- [Auth](#auth-endpoints)
- [Acts](#acts-endpoints)
- [Search](#search-endpoints)
- [Chat](#chat-endpoints)
- [Error responses](#error-responses)
- [Rate limits](#rate-limits)

---

## Authentication

Every endpoint except `/health*` and `/api/v1/auth/register|login|refresh`
requires a bearer token:

```
Authorization: Bearer <access_token>
```

Access tokens expire after 30 minutes (`ACCESS_TOKEN_EXPIRE_MINUTES`).
Refresh tokens expire after 7 days (`REFRESH_TOKEN_EXPIRE_DAYS`). When an
access token expires, exchange the refresh token via `POST
/api/v1/auth/refresh` for a new pair — the frontend's API client
(`frontend/src/api/client.ts`) does this automatically on any `401`.

## Conventions

- All request/response bodies are JSON.
- Timestamps are ISO 8601 UTC.
- IDs are UUIDv4 strings.
- Pagination (where present) uses a `limit` query parameter with a documented
  `ge`/`le` bound — there is no `offset`/cursor pagination in this API yet.

---

## Health

### `GET /health`
Liveness probe — returns `200` if the process is up. No auth required.

**Response `200`**
```json
{ "status": "healthy", "app": "LegalSense AI", "version": "1.0.0" }
```

### `GET /health/ready`
Readiness probe — verifies Postgres and Qdrant connectivity. No auth
required. Returns `200` with `"status": "degraded"` in the body (not a
non-200 status) if a dependency check fails — check the `checks` object.

**Response `200`**
```json
{
  "status": "ready",
  "checks": { "database": "ok", "vector_store": "ok" }
}
```

---

## Auth endpoints

### `POST /api/v1/auth/register`
Create a new account. Rate limit: 10/min.

**Request**
```json
{
  "email": "user@example.com",
  "password": "at-least-8-chars",
  "full_name": "Jane Doe"
}
```
`password`: 8–128 chars. `full_name`: 1–256 chars.

**Response `201`**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "Jane Doe",
  "role": "user",
  "is_active": true,
  "created_at": "2026-01-01T00:00:00Z"
}
```

**Errors**: `409` if the email is already registered.

### `POST /api/v1/auth/login`
Rate limit: 10/min.

**Request**
```json
{ "email": "user@example.com", "password": "..." }
```

**Response `200`**
```json
{
  "access_token": "...",
  "refresh_token": "...",
  "token_type": "bearer"
}
```

**Errors**: `401` on invalid credentials.

### `POST /api/v1/auth/refresh`

**Request**
```json
{ "refresh_token": "..." }
```

**Response `200`**: same shape as login. **Errors**: `401` if the refresh
token is invalid, expired, or not a refresh-type token.

### `GET /api/v1/auth/me`
Auth required.

**Response `200`**: same shape as register's response — the current user's profile.

### `PUT /api/v1/auth/me`
Auth required. Currently supports updating `full_name` only.

**Request**
```json
{ "full_name": "New Name" }
```

**Response `200`**: updated profile.

---

## Acts endpoints

All require auth.

### `GET /api/v1/acts`
List every ingested Act.

**Response `200`**
```json
[
  {
    "id": "uuid",
    "slug": "the_indian_contract_act_1872",
    "title": "The Indian Contract Act, 1872",
    "year": 1872,
    "total_sections": 238
  }
]
```

### `GET /api/v1/acts/{slug}`
Act detail including all section summaries.

**Response `200`**
```json
{
  "id": "uuid",
  "slug": "the_indian_contract_act_1872",
  "title": "The Indian Contract Act, 1872",
  "year": 1872,
  "total_sections": 238,
  "created_at": "2026-01-01T00:00:00Z",
  "sections": [
    { "id": "uuid", "section_number": "1", "title": "Short title", "chapter": "PRELIMINARY" }
  ]
}
```

**Errors**: `404` if the slug doesn't exist.

### `GET /api/v1/acts/{slug}/sections`
List sections of an Act, optionally filtered.

**Query params**: `chapter` (optional, exact match).

**Response `200`**: array of `{ id, section_number, title, chapter }`.

**Errors**: `404` if the Act doesn't exist, or no sections match the filter.

### `GET /api/v1/acts/{slug}/sections/{number}`
Full text of one section.

**Response `200`**
```json
{
  "id": "uuid",
  "section_number": "73",
  "title": "Compensation for loss or damage caused by breach of contract",
  "chapter": "OF THE CONSEQUENCES OF BREACH OF CONTRACT",
  "text": "When a contract has been broken...",
  "has_state_amendment": false,
  "act": { "id": "uuid", "slug": "...", "title": "...", "year": 1872, "total_sections": 238 }
}
```

**Errors**: `404` if the Act or section number doesn't exist.

---

## Search endpoints

All require auth.

### `POST /api/v1/search`
Semantic search across all ingested Acts.

**Request**
```json
{
  "query": "breach of contract damages",
  "act_filter": null,
  "top_k": 8
}
```
`query`: 2–1000 chars. `act_filter`: optional Act slug to restrict results.
`top_k`: 1–50, default 8.

**Response `200`**
```json
{
  "query": "breach of contract damages",
  "results": [
    {
      "section_id": "uuid",
      "act_title": "The Indian Contract Act, 1872",
      "act_slug": "the_indian_contract_act_1872",
      "section_number": "73",
      "section_title": "Compensation for loss or damage caused by breach of contract",
      "chapter": "OF THE CONSEQUENCES OF BREACH OF CONTRACT",
      "text_snippet": "When a contract has been broken, the party who suffers...",
      "score": 0.8123,
      "highlight": null
    }
  ],
  "total": 1,
  "elapsed_ms": 142.3
}
```
Every search is also recorded in the caller's search history.

### `GET /api/v1/search/history`
The authenticated user's recent searches, newest first.

**Query params**: `limit` (1–100, default 20).

**Response `200`**
```json
[
  { "id": "uuid", "query": "breach of contract damages", "results_count": 8, "created_at": "..." }
]
```

**Errors**: `422` if `limit` is outside 1–100.

---

## Chat endpoints

All require auth.

### `POST /api/v1/chat`
Send a message and receive an AI-generated response grounded in retrieved
Act text. Omit `conversation_id` to start a new conversation.

**Request**
```json
{
  "message": "What are the rules of acceptance under the Indian Contract Act?",
  "conversation_id": null
}
```
`message`: 1–4000 chars.

**Response `200`**
```json
{
  "conversation_id": "uuid",
  "message": {
    "id": "uuid",
    "role": "assistant",
    "content": "Under the Indian Contract Act, acceptance must be...\n[Section 7, The Indian Contract Act, 1872]",
    "citations": [
      {
        "act_title": "The Indian Contract Act, 1872",
        "section_number": "7",
        "section_title": "Acceptance must be absolute",
        "text_snippet": "In order to convert a proposal into a promise..."
      }
    ],
    "model_used": "gemini-2.0-flash",
    "created_at": "2026-01-01T00:00:00Z"
  }
}
```

**Errors**: `404` if `conversation_id` is provided but doesn't belong to the
caller (or doesn't exist — the two cases are indistinguishable by design, to
avoid leaking which UUIDs exist).

### `GET /api/v1/chat/conversations`
List the caller's conversations, newest first.

**Response `200`**
```json
[
  { "id": "uuid", "title": "Contract acceptance rules", "created_at": "...", "updated_at": "...", "message_count": 4 }
]
```

### `GET /api/v1/chat/conversations/{conversation_id}`
Full conversation with all messages.

**Response `200`**
```json
{
  "id": "uuid",
  "title": "Contract acceptance rules",
  "created_at": "...",
  "updated_at": "...",
  "messages": [
    { "id": "uuid", "role": "user", "content": "...", "citations": null, "model_used": null, "created_at": "..." },
    { "id": "uuid", "role": "assistant", "content": "...", "citations": [...], "model_used": "gemini-2.0-flash", "created_at": "..." }
  ]
}
```

**Errors**: `404` if the conversation doesn't exist or isn't owned by the caller.

### `DELETE /api/v1/chat/conversations/{conversation_id}`
Deletes the conversation and all its messages.

**Response**: `204 No Content`.

**Errors**: `404` if the conversation doesn't exist or isn't owned by the caller.

---

## Error responses

All errors follow FastAPI's default shape:
```json
{ "detail": "human-readable message" }
```

| Status | Meaning |
|---|---|
| `400` | Malformed request (uncaught `ValueError` in application code) |
| `401` | Missing/invalid/expired token, or wrong credentials |
| `403` | Authenticated but not authorized (reserved for admin-only routes) |
| `404` | Resource not found, or not owned by the caller |
| `409` | Conflict (duplicate email on registration) |
| `422` | Request body/query failed Pydantic validation |
| `429` | Rate limit exceeded |
| `500` | Unhandled server error — details are logged server-side, not returned to the client |

---

## Rate limits

Enforced by `slowapi`, keyed by remote address:

| Scope | Limit |
|---|---|
| Default (all routes) | 60 requests/minute |
| `/api/v1/auth/*` | 10 requests/minute |

A `429` response includes a `Retry-After` header.
