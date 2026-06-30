"""
Shared FastAPI dependencies injected into route handlers.

Re-exports commonly used dependencies so routes can import from a single
module.
"""

from __future__ import annotations

from backend.core.database import get_db
from backend.core.security import get_current_user, require_admin

__all__ = ["get_db", "get_current_user", "require_admin"]
