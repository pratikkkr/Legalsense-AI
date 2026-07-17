"""
LegalSense AI — FastAPI application entry point.

Configures CORS, middleware, rate limiting, exception handlers, lifespan
events, and mounts all API routers.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from backend.api import acts, auth, chat, health, search
from backend.api.middleware import RequestTracingMiddleware
from backend.core.config import get_settings
from backend.core.database import close_db, init_db
from backend.core.logging_config import get_logger, setup_logging

_settings = get_settings()


# ── Lifespan ────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown hooks."""
    setup_logging(
        log_level=_settings.LOG_LEVEL,
        json_logs=_settings.ENVIRONMENT == "production",
    )
    log = get_logger("startup")
    log.info(
        "application_starting",
        app=_settings.APP_NAME,
        version=_settings.APP_VERSION,
        env=_settings.ENVIRONMENT,
    )

    # Create database tables.
    await init_db()
    log.info("database_initialised")

    yield

    await close_db()
    log.info("application_stopped")


# ── App factory ─────────────────────────────────────────────────────

limiter = Limiter(key_func=get_remote_address, default_limits=[_settings.RATE_LIMIT_DEFAULT])

app = FastAPI(
    title=_settings.APP_NAME,
    version=_settings.APP_VERSION,
    description="AI-powered legal research platform for Indian Central Acts",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ── Middleware ──────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestTracingMiddleware)


# ── Global exception handlers ──────────────────────────────────────


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)},
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    log = get_logger("error")
    log.error("unhandled_exception", error=str(exc), type=type(exc).__name__)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal error occurred. Please try again later."},
    )


# ── Routers ─────────────────────────────────────────────────────────

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(acts.router)
app.include_router(search.router)
app.include_router(chat.router)
