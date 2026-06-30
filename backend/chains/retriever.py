"""
Hybrid retriever — combines dense vector search with keyword filtering
against the Qdrant vector store.

Supports:
- Semantic (dense) retrieval via cosine similarity
- Payload filtering by act, chapter, or section number
- Score thresholding to eliminate low-relevance noise
"""

from __future__ import annotations

from dataclasses import dataclass, field

from qdrant_client import models

from backend.chains.embedding import embed_query, get_qdrant_client
from backend.core.config import get_settings
from backend.core.logging_config import get_logger

log = get_logger(__name__)
_settings = get_settings()


@dataclass
class RetrievedChunk:
    """A single retrieved document chunk with its metadata and score."""

    text: str
    act_title: str
    act_slug: str
    section_number: str
    section_title: str
    chapter: str | None
    chunk_index: int
    score: float
    has_state_amendment: bool = False


@dataclass
class RetrievalResult:
    """Aggregated result from the retriever."""

    chunks: list[RetrievedChunk] = field(default_factory=list)
    query: str = ""


class HybridRetriever:
    """
    Retriever that performs dense vector search on Qdrant with optional
    payload-based keyword filtering.
    """

    def __init__(
        self,
        top_k: int | None = None,
        score_threshold: float | None = None,
    ):
        self.top_k = top_k or _settings.RAG_TOP_K
        self.score_threshold = score_threshold or _settings.RAG_SCORE_THRESHOLD

    def retrieve(
        self,
        query: str,
        act_filter: str | None = None,
        chapter_filter: str | None = None,
        section_filter: str | None = None,
    ) -> RetrievalResult:
        """
        Run hybrid retrieval.

        Parameters
        ----------
        query : str
            Natural-language search query.
        act_filter : str, optional
            Restrict results to a specific act slug.
        chapter_filter : str, optional
            Restrict results to a specific chapter.
        section_filter : str, optional
            Restrict results to a specific section number.
        """
        vector = embed_query(query)
        client = get_qdrant_client()

        # Build Qdrant filter conditions.
        conditions: list[models.FieldCondition] = []
        if act_filter:
            conditions.append(
                models.FieldCondition(
                    key="act_slug",
                    match=models.MatchValue(value=act_filter),
                )
            )
        if chapter_filter:
            conditions.append(
                models.FieldCondition(
                    key="chapter",
                    match=models.MatchValue(value=chapter_filter),
                )
            )
        if section_filter:
            conditions.append(
                models.FieldCondition(
                    key="section_number",
                    match=models.MatchValue(value=section_filter),
                )
            )

        qdrant_filter = (
            models.Filter(must=conditions) if conditions else None
        )

        results = client.query_points(
            collection_name=_settings.QDRANT_COLLECTION,
            query=vector,
            query_filter=qdrant_filter,
            limit=self.top_k,
            score_threshold=self.score_threshold,
            with_payload=True,
        )

        chunks: list[RetrievedChunk] = []
        for point in results.points:
            payload = point.payload or {}
            chunks.append(
                RetrievedChunk(
                    text=payload.get("text", ""),
                    act_title=payload.get("act_title", ""),
                    act_slug=payload.get("act_slug", ""),
                    section_number=payload.get("section_number", ""),
                    section_title=payload.get("section_title", ""),
                    chapter=payload.get("chapter"),
                    chunk_index=payload.get("chunk_index", 0),
                    score=point.score,
                    has_state_amendment=payload.get("has_state_amendment", False),
                )
            )

        # Deduplicate: if multiple chunks from the same section, keep the
        # highest-scoring one to avoid citation repetition.
        seen: dict[str, RetrievedChunk] = {}
        for chunk in chunks:
            key = f"{chunk.act_slug}:{chunk.section_number}"
            if key not in seen or chunk.score > seen[key].score:
                seen[key] = chunk
        deduped = sorted(seen.values(), key=lambda c: c.score, reverse=True)

        log.info(
            "retrieval_complete",
            query=query[:60],
            raw_hits=len(chunks),
            deduped_hits=len(deduped),
        )

        return RetrievalResult(chunks=deduped, query=query)
