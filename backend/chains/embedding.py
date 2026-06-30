"""
Embedding service — generates dense vector representations of text and
manages the Qdrant vector store.

Uses sentence-transformers for local, API-key-free embedding generation.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer

from backend.core.config import get_settings
from backend.core.logging_config import get_logger

log = get_logger(__name__)

_settings = get_settings()

# ── Singleton instances ─────────────────────────────────────────────

_embed_model: SentenceTransformer | None = None
_qdrant_client: QdrantClient | None = None


def get_embed_model() -> SentenceTransformer:
    """Lazy-load the sentence-transformers model (singleton)."""
    global _embed_model
    if _embed_model is None:
        log.info("loading_embedding_model", model=_settings.EMBEDDING_MODEL)
        _embed_model = SentenceTransformer(_settings.EMBEDDING_MODEL)
    return _embed_model


def get_qdrant_client() -> QdrantClient:
    """Return a singleton Qdrant client."""
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClient(
            host=_settings.QDRANT_HOST,
            port=_settings.QDRANT_PORT,
            api_key=_settings.QDRANT_API_KEY,
            timeout=30,
        )
    return _qdrant_client


# ── Collection management ──────────────────────────────────────────


def ensure_collection() -> None:
    """Create the Qdrant collection if it does not already exist."""
    client = get_qdrant_client()
    collections = [c.name for c in client.get_collections().collections]
    name = _settings.QDRANT_COLLECTION

    if name not in collections:
        log.info("creating_qdrant_collection", name=name)
        client.create_collection(
            collection_name=name,
            vectors_config=models.VectorParams(
                size=_settings.EMBEDDING_DIMENSION,
                distance=models.Distance.COSINE,
            ),
        )
        # Payload indexes for hybrid filtering.
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
    """
    Split a parsed section into overlapping text chunks.

    If the section text is shorter than ``chunk_size`` it is returned
    as a single chunk.  Each chunk inherits the section's metadata so
    citations can always trace back to the source.
    """
    cs = chunk_size or _settings.RAG_CHUNK_SIZE
    co = chunk_overlap or _settings.RAG_CHUNK_OVERLAP
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


# ── Ingestion ───────────────────────────────────────────────────────


def ingest_sections(sections: list[dict[str, Any]]) -> int:
    """
    Chunk, embed, and upsert a list of parsed sections into Qdrant.

    Returns the total number of points upserted.
    """
    ensure_collection()
    model = get_embed_model()
    client = get_qdrant_client()

    all_chunks: list[dict[str, Any]] = []
    for sec in sections:
        all_chunks.extend(chunk_section(sec))

    log.info("embedding_chunks", total=len(all_chunks))
    texts = [c["text"] for c in all_chunks]
    vectors = model.encode(texts, show_progress_bar=True, batch_size=64).tolist()

    # Stable point IDs derived from content hash (idempotent upserts).
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
            points=points[i : i + batch_size],
        )

    log.info("ingestion_complete", points=len(points))
    return len(points)


def embed_query(query: str) -> list[float]:
    """Embed a single query string and return its dense vector."""
    model = get_embed_model()
    return model.encode(query).tolist()
