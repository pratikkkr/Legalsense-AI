"""
Health-check endpoints for liveness and readiness probes.
"""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from backend.core.config import get_settings
from backend.core.database import async_session_factory

router = APIRouter(tags=["Health"])
_settings = get_settings()


@router.get("/health")
async def liveness():
    """Simple liveness probe — always returns 200 if the process is up."""
    return {
        "status": "healthy",
        "app": _settings.APP_NAME,
        "version": _settings.APP_VERSION,
    }


@router.get("/health/ready")
async def readiness():
    """
    Readiness probe — verifies database and vector store connectivity.
    Returns 503 if any dependency is unreachable.
    """
    checks: dict[str, str] = {}

    # PostgreSQL
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"

    # Qdrant
    try:
        from qdrant_client import QdrantClient

        client = QdrantClient(
            host=_settings.QDRANT_HOST,
            port=_settings.QDRANT_PORT,
            api_key=_settings.QDRANT_API_KEY,
            timeout=5,
        )
        client.get_collections()
        checks["vector_store"] = "ok"
    except Exception as exc:
        checks["vector_store"] = f"error: {exc}"

    all_ok = all(v == "ok" for v in checks.values())
    return {
        "status": "ready" if all_ok else "degraded",
        "checks": checks,
    }
