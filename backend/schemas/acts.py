"""Pydantic schemas for Acts and Sections."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class ActSummary(BaseModel):
    id: uuid.UUID
    slug: str
    title: str
    year: int | None
    total_sections: int

    model_config = {"from_attributes": True}


class SectionSummary(BaseModel):
    id: uuid.UUID
    section_number: str
    title: str
    chapter: str | None

    model_config = {"from_attributes": True}


class SectionDetail(BaseModel):
    id: uuid.UUID
    section_number: str
    title: str
    chapter: str | None
    text: str
    has_state_amendment: bool
    act: ActSummary

    model_config = {"from_attributes": True}


class ActDetail(BaseModel):
    id: uuid.UUID
    slug: str
    title: str
    year: int | None
    total_sections: int
    created_at: datetime
    sections: list[SectionSummary]

    model_config = {"from_attributes": True}
