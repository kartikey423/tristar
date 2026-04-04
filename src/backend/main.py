"""TriStar FastAPI application entry point.

COMP-007: Background asyncio task `_expire_offers_task()` sweeps the Hub
store every OFFER_EXPIRY_SWEEP_SECONDS, transitioning active→expired for
offers where valid_until < now. Uses hub_store.list() + hub_store.update()
instead of direct dict access (R-006 fix).

GET /health extended with "redis": "ok" | "degraded" via hub_store.ping() (AC-033/034).
"""

from __future__ import annotations

import asyncio
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from src.backend.api import designer, hub, scout
from src.backend.api.deps import get_hub_client, get_hub_store
from src.backend.core.config import settings
from src.backend.models.offer_brief import (
    Channel,
    ChannelType,
    Construct,
    KPIs,
    OfferBrief,
    OfferStatus,
    RiskFlags,
    RiskSeverity,
    Segment,
)
from src.backend.services.claude_api import ClaudeApiError, ClaudeResponseParseError
from src.backend.services.fraud_check_service import FraudBlockedError
from src.backend.services.hub_api_client import HubSaveError
from src.backend.services.hub_store import HubStore


# ─── Logging Setup ────────────────────────────────────────────────────────────

def _setup_logging() -> None:
    logger.remove()
    logger.add(
        sys.stdout,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
        level=settings.LOG_LEVEL,
        serialize=(settings.ENVIRONMENT != "development"),
    )


# ─── Demo offer seeder ────────────────────────────────────────────────────────

_DEMO_OFFERS: list[OfferBrief] = [
    OfferBrief(
        offer_id="demo-winter-clearance-001",
        objective="Drive clearance on winter outdoor gear — snow blowers, shovels and winter apparel before spring arrives",
        segment=Segment(
            name="winter_shoppers",
            definition="Members who purchased outdoor or automotive items in the last 90 days",
            estimated_size=12000,
            criteria=["outdoor", "automotive", "lapsed_90_days"],
        ),
        construct=Construct(
            type="points_multiplier",
            value=15,
            description="15x Triangle Points on all winter clearance items at Canadian Tire",
        ),
        channels=[Channel(channel_type=ChannelType.push, priority=1)],
        kpis=KPIs(expected_redemption_rate=0.22, expected_uplift_pct=35, target_segment_size=12000),
        risk_flags=RiskFlags(
            over_discounting=False,
            cannibalization=False,
            frequency_abuse=False,
            offer_stacking=False,
            severity=RiskSeverity.low,
            warnings=[],
        ),
        status=OfferStatus.active,
    ),
    OfferBrief(
        offer_id="demo-auto-care-002",
        objective="Promote spring automotive prep — oil changes, wiper blades and tire accessories for gold and platinum members",
        segment=Segment(
            name="auto_enthusiasts",
            definition="Gold and platinum members with automotive purchase history",
            estimated_size=8500,
            criteria=["automotive", "gold", "platinum"],
        ),
        construct=Construct(
            type="cashback",
            value=20,
            description="20% cashback in Triangle Points on automotive accessories at Canadian Tire and PartSource",
        ),
        channels=[Channel(channel_type=ChannelType.push, priority=1)],
        kpis=KPIs(expected_redemption_rate=0.30, expected_uplift_pct=40, target_segment_size=8500),
        risk_flags=RiskFlags(
            over_discounting=False,
            cannibalization=False,
            frequency_abuse=False,
            offer_stacking=False,
            severity=RiskSeverity.low,
            warnings=[],
        ),
        status=OfferStatus.active,
    ),
    OfferBrief(
        offer_id="demo-sport-apparel-003",
        objective="Reactivate lapsed members with Sport Chek apparel — spring activewear and footwear promotion",
        segment=Segment(
            name="lapsed_sport_fans",
            definition="Members who purchased sports or apparel items but have not visited in 60+ days",
            estimated_size=15000,
            criteria=["apparel", "sports", "lapsed_60_days"],
        ),
        construct=Construct(
            type="bonus_points",
            value=500,
            description="500 bonus Triangle Points when you spend $75+ on activewear or footwear at Sport Chek",
        ),
        channels=[Channel(channel_type=ChannelType.push, priority=1)],
        kpis=KPIs(expected_redemption_rate=0.18, expected_uplift_pct=28, target_segment_size=15000),
        risk_flags=RiskFlags(
            over_discounting=False,
            cannibalization=False,
            frequency_abuse=False,
            offer_stacking=False,
            severity=RiskSeverity.low,
            warnings=[],
        ),
        status=OfferStatus.active,
    ),
]


async def _seed_demo_offers() -> None:
    """Seed active demo offers into the Hub so Scout has candidates at startup."""
    store = get_hub_store()
    seeded = 0
    for offer in _DEMO_OFFERS:
        if not await store.exists(offer.offer_id):
            await store.save(offer)
            seeded += 1
    if seeded:
        logger.info(f"Demo seeder: {seeded} active offer(s) loaded into Hub")
    else:
        logger.info("Demo seeder: all demo offers already present — skipping")


# ─── Background offer expiry task ─────────────────────────────────────────────

async def _expire_offers_task() -> None:
    """Sweep hub store every OFFER_EXPIRY_SWEEP_SECONDS and expire stale offers.

    TODO(F-006): O(n) scan — optimize with Redis sorted set by valid_until in production.
    """
    while True:
        await asyncio.sleep(settings.OFFER_EXPIRY_SWEEP_SECONDS)
        now = datetime.now(timezone.utc)
        store = get_hub_store()

        try:
            active_offers = await store.list(status_filter=OfferStatus.active)
        except Exception as e:
            logger.warning(f"expire_sweep_list_failed: {e}")
            continue

        expired_count = 0
        for offer in active_offers:
            if offer.valid_until is None:
                continue
            # Normalize valid_until to UTC-aware for comparison
            valid_until = offer.valid_until
            if valid_until.tzinfo is None:
                valid_until = valid_until.replace(tzinfo=timezone.utc)
            if valid_until < now:
                try:
                    await store.update(offer.model_copy(update={"status": OfferStatus.expired}))
                    expired_count += 1
                    logger.info(
                        "Offer expired",
                        extra={"offer_id": offer.offer_id, "valid_until": valid_until.isoformat()},
                    )
                except Exception as e:
                    logger.warning(
                        f"expire_offer_update_failed: {e}",
                        extra={"offer_id": offer.offer_id},
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

    # Seed demo offers so Scout has active candidates immediately
    await _seed_demo_offers()

    # Start background expiry task
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


@app.post("/api/auth/demo-token", tags=["System"])
async def get_demo_token(role: str = "marketing") -> dict:
    """Generate a short-lived demo JWT for Swagger UI / E2E testing.

    Returns a token valid for 1 hour with the requested role.
    Only available for roles: marketing, system, viewer.
    """
    import jwt

    allowed_roles = {"marketing", "system", "viewer"}
    if role not in allowed_roles:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail=f"role must be one of {allowed_roles}")

    payload = {
        "sub": f"demo-{role}",
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.SERVICE_JWT_EXPIRY_HOURS),
    }
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": role,
        "usage": f'Paste into Swagger Authorize as: Bearer {token}',
    }


@app.get("/health", tags=["System"])
async def health_check(hub_store: HubStore = Depends(get_hub_store)) -> dict:
    """AC-033/034: Include redis status from hub_store.ping()."""
    redis_ok = await hub_store.ping()
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "purchase_trigger_enabled": settings.PURCHASE_TRIGGER_ENABLED,
        "redis": "ok" if redis_ok else "degraded",
    }
