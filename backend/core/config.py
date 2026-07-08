"""
Application configuration via environment variables.

All settings are loaded from the environment (or a .env file) using
pydantic-settings.  Secrets are never hard-coded.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root directory (two levels up from this file).
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Centralised, validated application settings."""

    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ─────────────────────────────────────────
    APP_NAME: str = "LegalSense AI"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # ── Server ──────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:8080",
    ]

    # ── PostgreSQL ──────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://legalsense:legalsense@localhost:5432/legalsense"

    # ── Qdrant ──────────────────────────────────────────────
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "legal_sections"
    QDRANT_API_KEY: str | None = None

    # ── Embeddings ──────────────────────────────────────────
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 768

    # ── LLM (provider-agnostic) ─────────────────────────────
    LLM_PROVIDER: Literal[
        "gemini", "openai", "anthropic", "ollama", "azure_openai"
    ] = "gemini"
    LLM_MODEL: str = "gemini-2.0-flash"
    LLM_TEMPERATURE: float = 0.2
    LLM_MAX_TOKENS: int = 4096

    # Provider-specific keys (only the active provider's key is required)
    GEMINI_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    AZURE_OPENAI_API_KEY: str | None = None
    AZURE_OPENAI_ENDPOINT: str | None = None
    AZURE_OPENAI_API_VERSION: str = "2024-02-01"
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # ── JWT Authentication ──────────────────────────────────
    JWT_SECRET_KEY: str = "CHANGE-ME-in-production-use-a-real-secret-key"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── Rate Limiting ───────────────────────────────────────
    RATE_LIMIT_DEFAULT: str = "60/minute"
    RATE_LIMIT_AUTH: str = "10/minute"

    # ── RAG Settings ────────────────────────────────────────
    RAG_TOP_K: int = 8
    RAG_SCORE_THRESHOLD: float = 0.35
    RAG_MAX_CONTEXT_TOKENS: int = 6000
    RAG_CHUNK_SIZE: int = 1000
    RAG_CHUNK_OVERLAP: int = 200

    # ── Data Paths ──────────────────────────────────────────
    DATA_DIR: Path = _PROJECT_ROOT / "data"

    @property
    def raw_data_dir(self) -> Path:
        return self.DATA_DIR / "raw"

    @property
    def processed_data_dir(self) -> Path:
        return self.DATA_DIR / "processed"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton of application settings."""
    return Settings()
