"""Pydantic schemas for search endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=1000)
    act_filter: str | None = Field(None, description="Filter by act slug")
    top_k: int = Field(8, ge=1, le=50)


class SearchResultItem(BaseModel):
    section_id: uuid.UUID | None = None
    act_title: str
    act_slug: str
    section_number: str
    section_title: str
    chapter: str | None
    text_snippet: str
    score: float
    highlight: str | None = None


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResultItem]
    total: int
    elapsed_ms: float


class SearchHistoryItem(BaseModel):
    id: uuid.UUID
    query: str
    results_count: int
    created_at: datetime

    model_config = {"from_attributes": True}
