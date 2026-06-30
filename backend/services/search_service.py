"""
Search service — orchestrates semantic search with history tracking.
"""

from __future__ import annotations

import time
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from backend.chains.retriever import HybridRetriever
from backend.core.logging_config import get_logger
from backend.core.models import SearchHistory
from backend.schemas.search import SearchRequest, SearchResponse, SearchResultItem

log = get_logger(__name__)


class SearchService:
    """Performs hybrid semantic + keyword search and records history."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.retriever = HybridRetriever()

    async def search(
        self, request: SearchRequest, user_id: uuid.UUID
    ) -> SearchResponse:
        """Run a search and persist the query in history."""
        t0 = time.perf_counter()

        result = self.retriever.retrieve(
            query=request.query,
            act_filter=request.act_filter,
        )

        items: list[SearchResultItem] = []
        for chunk in result.chunks[: request.top_k]:
            snippet = chunk.text[:500]
            items.append(
                SearchResultItem(
                    act_title=chunk.act_title,
                    act_slug=chunk.act_slug,
                    section_number=chunk.section_number,
                    section_title=chunk.section_title,
                    chapter=chunk.chapter,
                    text_snippet=snippet,
                    score=round(chunk.score, 4),
                )
            )

        elapsed = (time.perf_counter() - t0) * 1000

        # Persist search history.
        history = SearchHistory(
            user_id=user_id,
            query=request.query,
            filters={"act_filter": request.act_filter} if request.act_filter else None,
            results_count=len(items),
        )
        self.db.add(history)
        await self.db.flush()

        log.info(
            "search_completed",
            query=request.query[:60],
            results=len(items),
            elapsed_ms=round(elapsed, 1),
        )

        return SearchResponse(
            query=request.query,
            results=items,
            total=len(items),
            elapsed_ms=round(elapsed, 1),
        )
