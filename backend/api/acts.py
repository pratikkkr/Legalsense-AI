"""
Acts & Sections browsing API.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_current_user, get_db
from backend.core.models import User
from backend.schemas.acts import ActDetail, ActSummary, SectionDetail, SectionSummary
from backend.services.act_service import ActService

router = APIRouter(prefix="/api/v1/acts", tags=["Acts"])


@router.get("", response_model=list[ActSummary])
async def list_acts(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """List all available Acts."""
    svc = ActService(db)
    return await svc.list_acts()


@router.get("/{slug}", response_model=ActDetail)
async def get_act(
    slug: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Get Act details including all section summaries."""
    svc = ActService(db)
    act = await svc.get_act_by_slug(slug)
    if act is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Act not found")
    return act


@router.get("/{slug}/sections", response_model=list[SectionSummary])
async def list_sections(
    slug: str,
    chapter: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """List sections of a specific Act, optionally filtered by chapter."""
    svc = ActService(db)
    sections = await svc.get_sections_by_act(slug, chapter)
    if not sections:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Act not found or no sections match the filter",
        )
    return sections


@router.get("/{slug}/sections/{number}", response_model=SectionDetail)
async def get_section(
    slug: str,
    number: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Get the full text of a specific section."""
    svc = ActService(db)
    section = await svc.get_section(slug, number)
    if section is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Section {number} not found in act '{slug}'",
        )
    return section
