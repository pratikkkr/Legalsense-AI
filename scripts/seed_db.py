"""
seed_db.py — One-command bootstrap for the LegalSense AI database and
vector store.

Usage::

    python scripts/seed_db.py

What it does:
1. Reads all processed JSON files from ``data/processed/``.
2. Creates Act + Section rows in PostgreSQL.
3. Chunks, embeds, and upserts all sections into Qdrant.

This script is idempotent — running it again will skip existing Acts
and re-upsert vectors.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

# Ensure the project root is on the Python path.
_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from backend.core.config import get_settings
from backend.core.database import async_session_factory, engine, Base
from backend.core.models import ActMetadata, Section
from backend.chains.embedding import ingest_sections

from sqlalchemy import select

settings = get_settings()


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _extract_year(title: str) -> int | None:
    m = re.search(r"\b(1[89]\d{2}|20\d{2})\b", title)
    return int(m.group(1)) if m else None


async def seed_database():
    """Load processed JSONs into PostgreSQL."""
    # Create tables.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    processed_dir = settings.processed_data_dir
    json_files = sorted(processed_dir.glob("*.json"))
    if not json_files:
        print(f"No JSON files found in {processed_dir}")
        return

    print(f"Found {len(json_files)} processed Act files.")

    async with async_session_factory() as session:
        for jf in json_files:
            with open(jf, "r", encoding="utf-8") as f:
                sections_data = json.load(f)

            if not sections_data:
                print(f"  Skipping {jf.name}: empty file")
                continue

            act_title = sections_data[0].get("source", jf.stem)
            slug = _slug(act_title)
            year = _extract_year(act_title)

            # Check if Act already exists.
            result = await session.execute(
                select(ActMetadata).where(ActMetadata.slug == slug)
            )
            existing = result.scalar_one_or_none()
            if existing:
                print(f"  Act '{slug}' already exists — skipping DB insert.")
                continue

            act = ActMetadata(
                slug=slug,
                title=act_title,
                year=year,
                total_sections=len(sections_data),
            )
            session.add(act)
            await session.flush()

            for sec in sections_data:
                section = Section(
                    act_id=act.id,
                    section_number=sec["section"],
                    title=sec["title"],
                    chapter=sec.get("chapter"),
                    text=sec["text"],
                    has_state_amendment=sec.get("has_state_amendment", False),
                )
                session.add(section)

            await session.commit()
            print(f"  ✓ {act_title}: {len(sections_data)} sections inserted.")

    print("\nDatabase seeding complete.")


def seed_vectors():
    """Embed all processed sections and upsert into Qdrant."""
    processed_dir = settings.processed_data_dir
    json_files = sorted(processed_dir.glob("*.json"))
    all_sections: list[dict] = []

    for jf in json_files:
        with open(jf, "r", encoding="utf-8") as f:
            data = json.load(f)
            all_sections.extend(data)

    print(f"\nIngesting {len(all_sections)} sections into Qdrant…")
    total = ingest_sections(all_sections)
    print(f"  ✓ {total} vector points upserted.")


async def main():
    print("=" * 60)
    print("  LegalSense AI — Database & Vector Store Seeder")
    print("=" * 60)
    print()

    print("Phase 1: Seeding PostgreSQL…")
    await seed_database()

    print("\nPhase 2: Seeding Qdrant vector store…")
    seed_vectors()

    print("\n" + "=" * 60)
    print("  Seeding complete! The application is ready to use.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
