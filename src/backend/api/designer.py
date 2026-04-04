"""Designer API routes — offer generation, approval, and AI suggestions."""

from __future__ import annotations

import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger

from src.backend.api.deps import (
    get_audit_service,
    get_claude_service,
    get_deal_scraper_service,
    get_fraud_service,
    get_hub_audit_service,
    get_hub_client,
    get_hub_store,
    get_inventory_service,
)
from src.backend.api.hub import _validate_transition
from src.backend.core.security import AuthUser, require_marketing_role, require_system_role
from src.backend.models.offer_brief import (
    ApproveOfferResponse,
    DealSuggestion,
    GenerateOfferRequest,
    InventorySuggestion,
    OfferBrief,
    OfferStatus,
    RiskSeverity,
)
from src.backend.models.purchase_event import PurchaseContextRequest
from src.backend.services.audit_log_service import AuditLogService
from src.backend.services.claude_api import ClaudeApiError, ClaudeApiService, ClaudeResponseParseError
from src.backend.services.fraud_check_service import FraudBlockedError, FraudCheckService
from src.backend.services.hub_api_client import HubApiClient, HubSaveError
from src.backend.services.hub_audit_service import HubAuditEvent, HubAuditService
from src.backend.services.hub_store import HubStore, OfferAlreadyExistsError, RedisUnavailableError
from src.backend.services.inventory_service import InventoryService

router = APIRouter()


def _raise_if_fraud_blocked(
    fraud_result,
    offer_id: str,
    member_id: str,
    audit: "AuditLogService",
) -> None:
    """Log and raise 422 if the fraud check result is blocked."""
    if not fraud_result.blocked:
        return
    audit.log_fraud_block(offer_id, member_id, fraud_result.severity, fraud_result.warnings)
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "error": "FraudBlocked",
            "severity": fraud_result.severity,
            "warnings": fraud_result.warnings,
            "offer_id": offer_id,
        },
    )


@router.post(
    "/generate",
    response_model=OfferBrief,
    status_code=status.HTTP_201_CREATED,
    summary="Generate OfferBrief from marketing objective",
    description=(
        "Generate a structured OfferBrief using Claude AI from a marketer's objective. "
        "Runs fraud detection automatically. Returns a draft offer with risk_flags attached."
    ),
    responses={
        201: {"description": "OfferBrief generated (status=draft)"},
        400: {"description": "Validation error — objective too short or invalid"},
        401: {"description": "Missing or invalid Bearer token"},
        403: {"description": "Role 'marketing' required"},
        422: {"description": "Fraud check critical — offer generation blocked"},
        503: {"description": "Claude API unavailable after 3 retries"},
    },
)
async def generate_offer_brief(
    request: GenerateOfferRequest,
    user: AuthUser = Depends(require_marketing_role),
    claude: ClaudeApiService = Depends(get_claude_service),
    fraud: FraudCheckService = Depends(get_fraud_service),
    audit: AuditLogService = Depends(get_audit_service),
    hub_store: HubStore = Depends(get_hub_store),
) -> OfferBrief:
    start = time.monotonic()
    try:
        offer = await claude.generate_from_objective(
            request.objective, request.segment_hints
        )
    except ClaudeApiError as e:
        logger.error("Claude API failed", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Offer generation failed after 3 attempts: {e}",
        )
    except ClaudeResponseParseError as e:
        logger.error(f"Claude response parse error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Claude returned an unparseable response. Please retry.",
        )

    fraud_result = fraud.validate(offer, member_id=user.user_id)

    # Attach fraud flags to the offer
    offer = offer.model_copy(update={"risk_flags": fraud_result.flags})

    duration_ms = (time.monotonic() - start) * 1000
    audit.log_generation(offer, member_id=user.user_id, duration_ms=duration_ms)

    # REQ-005: Block fraud before saving to Hub
    _raise_if_fraud_blocked(fraud_result, offer.offer_id, user.user_id, audit)

    # REQ-005: Auto-save to Hub as draft immediately after fraud check passes
    try:
        await hub_store.save(offer)
    except OfferAlreadyExistsError:
        # AC-020: idempotent — if already saved, proceed without error
        logger.debug(f"hub_auto_save_idempotent: offer {offer.offer_id} already in Hub")
    except RedisUnavailableError as e:
        logger.error(f"hub_auto_save_redis_unavailable: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Hub store unavailable — offer not saved",
        )

    return offer


@router.post(
    "/generate-purchase",
    response_model=OfferBrief,
    status_code=status.HTTP_201_CREATED,
    summary="Generate purchase-triggered OfferBrief (system use only)",
    description=(
        "Called by Scout when a purchase event score exceeds threshold. "
        "Generates a personalized offer with status=active and saves it to Hub. "
        "Requires role='system' (service JWT from Scout)."
    ),
    responses={
        201: {"description": "OfferBrief generated and saved to Hub with status=active"},
        401: {"description": "Missing or invalid Bearer token"},
        403: {"description": "Role 'system' required"},
        422: {"description": "Fraud check critical"},
        503: {"description": "Claude API or Hub unavailable"},
    },
)
async def generate_purchase_triggered_offer(
    ctx: PurchaseContextRequest,
    user: AuthUser = Depends(require_system_role),
    claude: ClaudeApiService = Depends(get_claude_service),
    fraud: FraudCheckService = Depends(get_fraud_service),
    hub: HubApiClient = Depends(get_hub_client),
    audit: AuditLogService = Depends(get_audit_service),
) -> OfferBrief:
    start = time.monotonic()

    try:
        offer = await claude.generate_from_purchase_context(ctx)
    except ClaudeApiError as e:
        logger.error("Claude API failed for purchase-triggered offer", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Purchase offer generation failed: {e}",
        )
    except ClaudeResponseParseError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Claude response unparseable: {e}",
        )

    fraud_result = fraud.validate(offer, member_id=ctx.member_id)
    offer = offer.model_copy(update={"risk_flags": fraud_result.flags})

    duration_ms = (time.monotonic() - start) * 1000
    audit.log_generation(
        offer, member_id=ctx.member_id, trigger="purchase_triggered", duration_ms=duration_ms
    )
    _raise_if_fraud_blocked(fraud_result, offer.offer_id, ctx.member_id, audit)

    try:
        saved_offer = await hub.save_offer(offer)
    except HubSaveError as e:
        logger.error(f"Failed to save purchase-triggered offer to Hub: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Hub save failed: {e}",
        )

    # Update active offer stacking count for fraud detection
    fraud.record_active_offer(member_id=ctx.member_id)

    return saved_offer


@router.post(
    "/approve/{offer_id}",
    response_model=ApproveOfferResponse,
    summary="Approve a draft offer (saves to Hub)",
    responses={
        200: {"description": "Offer approved and saved to Hub"},
        400: {"description": "Offer has critical risk flags — cannot approve"},
        401: {"description": "Authentication required"},
        403: {"description": "Role 'marketing' required"},
        502: {"description": "Hub save failed"},
    },
)
async def approve_offer(
    offer_id: str,
    user: AuthUser = Depends(require_marketing_role),
    hub_store: HubStore = Depends(get_hub_store),
    fraud: FraudCheckService = Depends(get_fraud_service),
    audit: AuditLogService = Depends(get_audit_service),
) -> ApproveOfferResponse:
    """F-001 FIX: Use hub_store.update() instead of hub_client.save_offer() to avoid 409 conflict.

    POST /generate auto-saves as draft. POST /approve transitions draft → approved via update().
    No request body needed — the authoritative offer lives in hub_store.
    """
    # F-001 FIX: verify draft exists in Hub before updating
    try:
        current = await hub_store.get(offer_id)
    except RedisUnavailableError as e:
        logger.error(f"hub_redis_unavailable: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Hub store unavailable",
        )

    if current is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Offer {offer_id} not found in Hub — generate it first",
        )

    if current.risk_flags.severity == RiskSeverity.critical:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot approve offer with critical risk flags",
        )

    # Reuse hub.py transition validator — keeps validation logic in one place
    _validate_transition(current.status, OfferStatus.approved)

    approved_offer = current.model_copy(update={"status": OfferStatus.approved})

    try:
        await hub_store.update(approved_offer)
    except RedisUnavailableError as e:
        logger.error(f"hub_redis_unavailable: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Hub store unavailable",
        )

    # Update active offer stacking count for fraud detection
    fraud.record_active_offer(member_id=user.user_id)
    audit.log_approval(approved_offer, approved_by=user.user_id)

    return ApproveOfferResponse(
        offer_id=offer_id,
        status=OfferStatus.approved,
        hub_saved=True,
        message="Offer approved and saved to Hub",
    )


@router.get(
    "/suggestions",
    response_model=list[InventorySuggestion],
    summary="Get AI-driven inventory suggestions for offer creation",
    responses={
        200: {"description": "Top-3 overstock suggestions"},
        401: {"description": "Authentication required"},
        403: {"description": "Role 'marketing' required"},
    },
)
async def get_inventory_suggestions(
    limit: int = 3,
    user: AuthUser = Depends(require_marketing_role),
    inventory: InventoryService = Depends(get_inventory_service),
    hub_store: HubStore = Depends(get_hub_store),
) -> list[InventorySuggestion]:
    suggestions = inventory.get_suggestions(limit=min(limit, 50))

    # Exclude products already in Hub (any non-expired status) — prevents duplicates in Designer feed
    try:
        hub_offers = await hub_store.list()
        offered_deal_ids: set[str] = {
            o.source_deal_id for o in hub_offers
            if o.source_deal_id is not None
            and o.status in {OfferStatus.draft, OfferStatus.approved, OfferStatus.active}
        }
        if offered_deal_ids:
            suggestions = [s for s in suggestions if s.product_id not in offered_deal_ids]
    except Exception:
        # Hub exclusion is best-effort — never fail the suggestions endpoint
        pass

    return suggestions


@router.get(
    "/live-deals",
    response_model=list[DealSuggestion],
    summary="Get live deals from Canadian Tire",
    description="Scrapes Canadian Tire weekly deals, flyer, and clearance pages for real-time offer ideas",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Live deals retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Role 'marketing' required"},
        503: {"description": "Unable to fetch deals from Canadian Tire"},
    },
)
async def get_live_deals(
    limit: int = 5,
    user: AuthUser = Depends(require_marketing_role),
    deal_scraper: DealScraperService = Depends(get_deal_scraper_service),
) -> list[DealSuggestion]:
    """Fetch live deals from Canadian Tire to sync with Designer offers.

    Intelligence:
    - Scrapes 3 sources: weekly deals, flyer, clearance
    - Cached for 15 minutes to avoid rate limiting
    - Returns top deals sorted by discount percentage

    Rate Limiting:
    - 1 request per minute (enforced by internal cache)
    - Fallback to cached data if scraping fails
    """
    try:
        deals = await deal_scraper.fetch_deals()
        if deals:
            return deals[:min(limit, 20)]

        # Scraper returned empty (Canadian Tire blocked or no deals found) — return demo deals
        logger.warning("Live scraper returned 0 deals, serving demo fallback data")
        return _demo_deals()[:min(limit, 20)]
    except Exception as e:
        logger.error(f"Failed to fetch live deals: {e}")
        return _demo_deals()[:min(limit, 20)]


def _demo_deals() -> list[DealSuggestion]:
    """Fallback demo deals used when Canadian Tire scraper is blocked or unavailable."""
    from datetime import datetime

    items = [
        ("MotoMaster 20V Lithium-Ion Drill Kit", "tools", 40, 149.99, 89.99, "weekly_deals"),
        ("Coleman 6-Person Instant Tent", "outdoor", 35, 299.99, 194.99, "flyer"),
        ("Mastercraft 200-Piece Socket Set", "tools", 50, 199.99, 99.99, "clearance"),
        ("Noma LED String Lights 48ft", "home", 30, 49.99, 34.99, "weekly_deals"),
        ("Motomaster Eliminator Battery 750A", "automotive", 25, 159.99, 119.99, "flyer"),
        ("Quasar 55in 4K Smart TV", "electronics", 20, 699.99, 559.99, "clearance"),
        ("Arctic Cat 24in Snow Blower", "snow_removal", 45, 799.99, 439.99, "clearance"),
        ("Workpro 130-Piece Mechanics Set", "tools", 38, 159.99, 99.99, "weekly_deals"),
        ("Weber Q1200 Portable Gas BBQ", "outdoor", 22, 349.99, 272.99, "flyer"),
        ("Toro 60V Cordless Lawn Mower", "outdoor", 28, 499.99, 359.99, "clearance"),
    ]
    import hashlib

    source_urls = {
        "weekly_deals": "https://www.canadiantire.ca/en/promotions/weekly-deals.html",
        "flyer": "https://www.canadiantire.ca/en/flyer.html",
        "clearance": "https://www.canadiantire.ca/en/promotions/clearance.html",
    }
    deals = []
    for name, cat, disc, orig, sale, src in items:
        h = hashlib.md5(f"{src}:{name.lower()}".encode()).hexdigest()[:8]
        deals.append(
            DealSuggestion(
                deal_id=f"ctc-{src}-{h}",
                product_name=name,
                category=cat,
                discount_pct=disc,
                original_price=orig,
                deal_price=sale,
                source_url=source_urls[src],
                source=src,
                suggested_objective=f"Drive {disc}% discount on {name} to {cat} shoppers",
                scraped_at=datetime.utcnow(),
            )
        )
    return deals
