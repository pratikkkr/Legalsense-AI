"""
Search API — semantic search across legal sections.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_current_user, get_db
from backend.core.models import User
from backend.schemas.search import SearchHistoryItem, SearchRequest, SearchResponse
from backend.services.search_service import SearchService
from backend.core.models import SearchHistory
from sqlalchemy import select

router = APIRouter(prefix="/api/v1/search", tags=["Search"])


@router.post("", response_model=SearchResponse)
async def search(
    body: SearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Perform a semantic search across all Acts."""
    svc = SearchService(db)
    return await svc.search(body, current_user.id)


@router.get("/history", response_model=list[SearchHistoryItem])
async def search_history(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the authenticated user's recent search history."""
    result = await db.execute(
        select(SearchHistory)
        .where(SearchHistory.user_id == current_user.id)
        .order_by(SearchHistory.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
