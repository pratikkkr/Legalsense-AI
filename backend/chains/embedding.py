"""
Embedding service — generates dense vector representations of text and
manages the Qdrant vector store.

Uses Google Gemini's embedding API (no local model, no PyTorch needed).
"""

from __future__ import annotations

import hashlib
import re
import uuid
from typing import Any

import google.generativeai as genai
from qdrant_client import QdrantClient, models

from backend.core.config import get_settings
from backend.core.logging_config import get_logger

log = get_logger(__name__)
_settings = get_settings()

# Gemini embedding model — 768 dimensions
GEMINI_EMBED_MODEL = "models/text-embedding-004"

# ── Qdrant client singleton ─────────────────────────────────────────

_qdrant_client: QdrantClient | None = None


def get_qdrant_client() -> QdrantClient:
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClient(
            host=_settings.QDRANT_HOST,
            port=_settings.QDRANT_PORT,
            api_key=_settings.QDRANT_API_KEY,
            timeout=30,
        )
    return _qdrant_client


# ── Gemini setup ────────────────────────────────────────────────────

def _get_genai():
    genai.configure(api_key=_settings.GEMINI_API_KEY)
    return genai


# ── Collection management ──────────────────────────────────────────

def ensure_collection() -> None:
    client = get_qdrant_client()
    collections = [c.name for c in client.get_collections().collections]
    name = _settings.QDRANT_COLLECTION

    if name not in collections:
        log.info("creating_qdrant_collection", name=name)
        client.create_collection(
            collection_name=name,
            vectors_config=models.VectorParams(
                size=768,  # Gemini text-embedding-004 dimension
                distance=models.Distance.COSINE,
            ),
        )
        client.create_payload_index(
            collection_name=name,
            field_name="act_slug",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )
        client.create_payload_index(
            collection_name=name,
            field_name="section_number",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )
        client.create_payload_index(
            collection_name=name,
            field_name="chapter",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )


# ── Chunking ────────────────────────────────────────────────────────

def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def chunk_section(
    section: dict[str, Any],
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[dict[str, Any]]:
    cs = chunk_size or _settings.RAG_CHUNK_SIZE
    co = chunk_overlap or _settings.RAG_CHUNK_OVERLAP
    if co >= cs:
        raise ValueError(f"chunk_overlap ({co}) must be smaller than chunk_size ({cs})")
    text: str = section["text"]
    act_slug = _slug(section.get("source", "unknown"))
    base_meta = {
        "act_title": section.get("source", ""),
        "act_slug": act_slug,
        "section_number": section.get("section", ""),
        "section_title": section.get("title", ""),
        "chapter": section.get("chapter", ""),
        "has_state_amendment": section.get("has_state_amendment", False),
    }

    words = text.split()
    if len(words) <= cs:
        return [{**base_meta, "text": text, "chunk_index": 0}]

    chunks: list[dict[str, Any]] = []
    start = 0
    idx = 0
    while start < len(words):
        end = min(start + cs, len(words))
        chunk_text = " ".join(words[start:end])
        chunks.append({**base_meta, "text": chunk_text, "chunk_index": idx})
        if end == len(words):
            break
        start += cs - co
        idx += 1

    return chunks


# ── Embedding ───────────────────────────────────────────────────────

def _embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts using Gemini text-embedding-004."""
    g = _get_genai()
    vectors = []
    # Gemini embedding API supports batch of up to 100
    batch_size = 100
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        result = g.embed_content(
            model=GEMINI_EMBED_MODEL,
            content=batch,
            task_type="retrieval_document",
        )
        vectors.extend(result["embedding"])
    return vectors


def embed_query(query: str) -> list[float]:
    """Embed a single query string."""
    g = _get_genai()
    result = g.embed_content(
        model=GEMINI_EMBED_MODEL,
        content=query,
        task_type="retrieval_query",
    )
    return result["embedding"]


# ── Ingestion ───────────────────────────────────────────────────────

def ingest_sections(sections: list[dict[str, Any]]) -> int:
    ensure_collection()
    client = get_qdrant_client()

    all_chunks: list[dict[str, Any]] = []
    for sec in sections:
        all_chunks.extend(chunk_section(sec))

    log.info("embedding_chunks", total=len(all_chunks))
    texts = [c["text"] for c in all_chunks]
    vectors = _embed_texts(texts)

    points: list[models.PointStruct] = []
    for chunk, vec in zip(all_chunks, vectors):
        uid = uuid.UUID(
            hashlib.md5(
                f"{chunk['act_slug']}:{chunk['section_number']}:{chunk['chunk_index']}".encode()
            ).hexdigest()
        )
        points.append(
            models.PointStruct(
                id=uid.hex,
                vector=vec,
                payload=chunk,
            )
        )

    batch_size = 100
    for i in range(0, len(points), batch_size):
        client.upsert(
            collection_name=_settings.QDRANT_COLLECTION,
            points=points[i:i + batch_size],
        )

    log.info("ingestion_complete", points=len(points))
    return len(points)