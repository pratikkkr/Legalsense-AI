"""
User service — handles registration, authentication, and profile management.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.logging_config import get_logger
from backend.core.models import User
from backend.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from backend.schemas.auth import TokenResponse, UserRegister

log = get_logger(__name__)


class UserService:
    """Encapsulates all user-related business logic."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def register(self, data: UserRegister) -> User:
        """Create a new user account. Raises *ValueError* on duplicate email."""
        existing = await self.db.execute(
            select(User).where(User.email == data.email)
        )
        if existing.scalar_one_or_none() is not None:
            raise ValueError("A user with this email already exists")

        user = User(
            email=data.email,
            hashed_password=hash_password(data.password),
            full_name=data.full_name,
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        log.info("user_registered", user_id=str(user.id), email=user.email)
        return user

    async def authenticate(self, email: str, password: str) -> TokenResponse:
        """Verify credentials and return a JWT pair."""
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user is None or not verify_password(password, user.hashed_password):
            raise ValueError("Invalid email or password")

        if not user.is_active:
            raise ValueError("Account is deactivated")

        access = create_access_token(user.id, user.role.value)
        refresh = create_refresh_token(user.id)
        log.info("user_authenticated", user_id=str(user.id))
        return TokenResponse(access_token=access, refresh_token=refresh)

    async def refresh_tokens(self, refresh_token: str) -> TokenResponse:
        """Issue a new token pair from a valid refresh token."""
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError("Invalid refresh token")

        user_id = uuid.UUID(payload["sub"])
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None or not user.is_active:
            raise ValueError("User not found or deactivated")

        access = create_access_token(user.id, user.role.value)
        refresh = create_refresh_token(user.id)
        return TokenResponse(access_token=access, refresh_token=refresh)

    async def update_profile(self, user: User, full_name: str | None) -> User:
        """Update mutable user fields."""
        if full_name is not None:
            user.full_name = full_name
        await self.db.flush()
        await self.db.refresh(user)
        return user
