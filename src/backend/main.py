"""TriStar FastAPI application entry point.

F-004 FIX: Background asyncio task `expire_offers_task()` sweeps the Hub
in-memory store every 300s, transitioning active→expired for offers where
valid_until < now.
"""

from __future__ import annotations

import asyncio
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from src.backend.api import designer, hub, scout
from src.backend.api.hub import _store as hub_store
from src.backend.api.deps import get_hub_client
from src.backend.core.config import settings
from src.backend.models.offer_brief import OfferStatus
from src.backend.services.claude_api import ClaudeApiError, ClaudeResponseParseError
from src.backend.services.fraud_check_service import FraudBlockedError
from src.backend.services.hub_api_client import HubSaveError


# ─── Logging Setup ────────────────────────────────────────────────────────────

def _setup_logging() -> None:
    logger.remove()
    logger.add(
        sys.stdout,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
        level=settings.LOG_LEVEL,
        serialize=(settings.ENVIRONMENT != "development"),
    )


# ─── F-004: Background offer expiry task ─────────────────────────────────────

async def _expire_offers_task() -> None:
    """Sweep hub store every OFFER_EXPIRY_SWEEP_SECONDS and expire stale offers."""
    while True:
        await asyncio.sleep(settings.OFFER_EXPIRY_SWEEP_SECONDS)
        now = datetime.utcnow()
        expired_count = 0

        for offer_id, offer in list(hub_store.items()):
            if (
                offer.status == OfferStatus.active
                and offer.valid_until is not None
                and offer.valid_until < now
            ):
                hub_store[offer_id] = offer.model_copy(
                    update={"status": OfferStatus.expired}
                )
                expired_count += 1
                logger.info(
                    "Offer expired",
                    extra={"offer_id": offer_id, "valid_until": offer.valid_until.isoformat()},
                )

        if expired_count > 0:
            logger.info(f"Expiry sweep complete: {expired_count} offer(s) expired")


# ─── Application Lifespan ─────────────────────────────────────────────────────

def _validate_production_secrets() -> None:
    """Fail fast if insecure default secrets are used in production."""
    if settings.ENVIRONMENT != "production":
        return
    if settings.JWT_SECRET == "dev-secret-change-in-prod":
        raise RuntimeError(
            "JWT_SECRET must be set to a secure value in production. "
            "Current value is the public default from config.py."
        )
    if settings.SCOUT_WEBHOOK_SECRET == "dev-webhook-secret":
        raise RuntimeError(
            "SCOUT_WEBHOOK_SECRET must be set to a secure value in production. "
            "Current value is the public default from config.py."
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _setup_logging()
    _validate_production_secrets()
    logger.info(f"TriStar API starting (environment={settings.ENVIRONMENT})")

    # Start background expiry task (F-004)
    expiry_task = asyncio.create_task(_expire_offers_task())
    logger.info(
        f"Offer expiry task started (sweep every {settings.OFFER_EXPIRY_SWEEP_SECONDS}s)"
    )

    yield

    expiry_task.cancel()
    try:
        await expiry_task
    except asyncio.CancelledError:
        pass

    await get_hub_client().close()
    logger.info("TriStar API shutdown complete")


# ─── Application ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="TriStar API",
    version="0.1.0",
    description=(
        "Triangle Smart Targeting and Real-Time Activation — "
        "AI-powered loyalty offer generation and context-driven activation."
    ),
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


# ─── Request Logging Middleware ───────────────────────────────────────────────

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    duration_ms = int((time.monotonic() - start) * 1000)
    logger.info(
        "HTTP request",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    return response


# ─── Global Exception Handlers ────────────────────────────────────────────────

@app.exception_handler(FraudBlockedError)
async def fraud_blocked_handler(request: Request, exc: FraudBlockedError):
    return JSONResponse(
        status_code=422,
        content={
            "error": "FraudBlocked",
            "severity": exc.result.severity,
            "warnings": exc.result.warnings,
        },
    )


@app.exception_handler(ClaudeApiError)
async def claude_api_error_handler(request: Request, exc: ClaudeApiError):
    return JSONResponse(
        status_code=503,
        content={"error": "ClaudeApiError", "detail": str(exc)},
    )


@app.exception_handler(HubSaveError)
async def hub_save_error_handler(request: Request, exc: HubSaveError):
    return JSONResponse(
        status_code=502,
        content={"error": "HubSaveError", "detail": str(exc)},
    )


# ─── Routers ──────────────────────────────────────────────────────────────────

app.include_router(designer.router, prefix="/api/designer", tags=["Designer"])
app.include_router(scout.router, prefix="/api/scout", tags=["Scout"])
app.include_router(hub.router, prefix="/api/hub", tags=["Hub"])


@app.get("/health", tags=["System"])
async def health_check() -> dict:
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "purchase_trigger_enabled": settings.PURCHASE_TRIGGER_ENABLED,
    }
