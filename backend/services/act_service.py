"""
Act service — handles Act and Section CRUD operations.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.core.models import ActMetadata, Section


class ActService:
    """Encapsulates all act/section-related data access."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_acts(self) -> list[ActMetadata]:
        """Return all acts ordered by title."""
        result = await self.db.execute(
            select(ActMetadata).order_by(ActMetadata.title)
        )
        return list(result.scalars().all())

    async def get_act_by_slug(self, slug: str) -> ActMetadata | None:
        """Fetch a single act with its sections eagerly loaded."""
        result = await self.db.execute(
            select(ActMetadata)
            .where(ActMetadata.slug == slug)
            .options(selectinload(ActMetadata.sections))
        )
        return result.scalar_one_or_none()

    async def get_section(
        self, act_slug: str, section_number: str
    ) -> Section | None:
        """Fetch a specific section by act slug and section number."""
        result = await self.db.execute(
            select(Section)
            .join(ActMetadata)
            .where(
                ActMetadata.slug == act_slug,
                Section.section_number == section_number,
            )
            .options(selectinload(Section.act))
        )
        return result.scalar_one_or_none()

    async def get_sections_by_act(
        self,
        act_slug: str,
        chapter: str | None = None,
    ) -> list[Section]:
        """List sections for an act, optionally filtered by chapter."""
        query = (
            select(Section)
            .join(ActMetadata)
            .where(ActMetadata.slug == act_slug)
        )
        if chapter:
            query = query.where(Section.chapter == chapter)
        query = query.order_by(
            func.length(Section.section_number),
            Section.section_number,
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def search_sections_by_keyword(
        self,
        keyword: str,
        act_slug: str | None = None,
        limit: int = 20,
    ) -> list[Section]:
        """Simple keyword (ILIKE) search across section text and title."""
        query = select(Section).options(selectinload(Section.act))
        if act_slug:
            query = query.join(ActMetadata).where(ActMetadata.slug == act_slug)
        query = query.where(
            Section.text.ilike(f"%{keyword}%")
            | Section.title.ilike(f"%{keyword}%")
        ).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())
