"""Scout API routes — purchase event processing and offer activation."""

from __future__ import annotations

from typing import Optional

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
from loguru import logger

from src.backend.api.deps import (
    get_audit_service,
    get_context_scoring_service,
    get_delivery_constraint_service,
    get_notification_service,
    get_partner_trigger_service,
    get_purchase_event_handler,
    get_scout_audit_service,
    get_scout_match_service,
)
from src.backend.core.config import settings
from src.backend.core.security import verify_webhook_signature
from src.backend.models.offer_brief import OfferBrief
from src.backend.models.partner_event import PartnerPurchaseEvent, PartnerTriggerResponse
from src.backend.models.purchase_event import PurchaseContextRequest, PurchaseEventPayload
from src.backend.models.scout_match import MatchRequest, MatchResponse, NoMatchResponse
from src.backend.services.audit_log_service import AuditLogService
from src.backend.services.context_scoring_service import ContextScoringService
from src.backend.services.delivery_constraint_service import DeliveryConstraintService
from src.backend.services.notification_service import NotificationService
from src.backend.services.partner_trigger_service import PartnerTriggerService
from src.backend.services.purchase_event_handler import PurchaseEventHandler
from src.backend.services.scout_audit_service import ScoutAuditService
from src.backend.services.scout_match_service import ScoutMatchService
from src.backend.services.scout_service_auth import scout_auth

router = APIRouter()



@router.post(
    "/purchase-event",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Process a purchase event from the rewards system",
    description=(
        "Receives a purchase event webhook from the Triangle rewards system. "
        "Validates signature, scores context, and triggers offer generation if score > 70. "
        "Returns 202 Accepted immediately (processing is asynchronous)."
    ),
    responses={
        202: {"description": "Event accepted for processing"},
        400: {"description": "Invalid payload (refund, missing fields, or duplicate)"},
        401: {"description": "Invalid webhook signature"},
    },
)
async def process_purchase_event(
    request: Request,
    event: PurchaseEventPayload,
    x_webhook_signature: Optional[str] = Header(default=None),
    handler: PurchaseEventHandler = Depends(get_purchase_event_handler),
    scorer: ContextScoringService = Depends(get_context_scoring_service),
    constraint: DeliveryConstraintService = Depends(get_delivery_constraint_service),
    notification: NotificationService = Depends(get_notification_service),
    audit: AuditLogService = Depends(get_audit_service),
) -> dict:
    # Validate webhook signature in non-development environments
    if settings.ENVIRONMENT != "development":
        body = await request.body()
        if not verify_webhook_signature(body, x_webhook_signature, settings.SCOUT_WEBHOOK_SECRET):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature",
            )

    # Reject refunds at route level
    if event.is_refund:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Refund events are not eligible for offer generation",
        )

    if event.amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Purchase amount must be greater than 0",
        )

    # Process event (handles feature flag, dedup, enrichment)
    enriched = await handler.handle(event)

    if enriched is None:
        # Feature disabled, not in pilot, or duplicate — accepted but no action
        return {"status": "accepted", "action": "skipped", "offer_generated": False}

    # Score the enriched context
    score = scorer.score(enriched)

    audit.log_purchase_trigger(
        member_id=event.member_id,
        event_id=event.event_id,
        store_name=event.store_name,
        store_id=event.store_id,
        amount=event.amount,
        context_score=score.total,
        triggered=score.should_trigger,
        skip_reason=None if score.should_trigger else f"Score {score.total:.1f} ≤ threshold {settings.PURCHASE_TRIGGER_SCORE_THRESHOLD}",
    )

    if not score.should_trigger:
        return {
            "status": "accepted",
            "action": "scored_below_threshold",
            "context_score": score.total,
            "threshold": settings.PURCHASE_TRIGGER_SCORE_THRESHOLD,
            "offer_generated": False,
        }

    # Check delivery constraints
    can_deliver, reason = constraint.can_deliver(event.member_id, event.amount)

    if not can_deliver:
        if "Quiet hours" in (reason or ""):
            constraint.queue_for_morning(event.member_id, f"pending-{event.event_id}")
            return {
                "status": "accepted",
                "action": "queued_for_morning",
                "offer_generated": False,
            }
        return {
            "status": "accepted",
            "action": "delivery_blocked",
            "reason": reason,
            "offer_generated": False,
        }

    # Call Designer API to generate purchase-triggered offer
    nearby_store_names = [s.store_name for s in enriched.nearby_stores[:3]]
    weather_condition = enriched.weather.condition if enriched.weather else None
    member_segment = enriched.member.segment if enriched.member else "standard"

    purchase_ctx = PurchaseContextRequest(
        member_id=event.member_id,
        event_id=event.event_id,
        purchase_amount=event.amount,
        store_name=event.store_name,
        partner_brand=event.partner_brand,
        member_segment=member_segment,
        nearby_ctc_stores=nearby_store_names,
        weather_condition=weather_condition,
        context_score=score.total,
        score_breakdown=score.breakdown,
    )

    # Internal call to Designer (Scout → Designer using service JWT)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.DESIGNER_API_URL}/api/designer/generate-purchase",
                json=purchase_ctx.model_dump(mode="json"),
                headers=scout_auth.bearer_header(),
            )

        if response.status_code == 201:
            offer_data = response.json()
            offer = OfferBrief(**offer_data)

            constraint.record_delivery(event.member_id)

            # Send push notification
            await notification.send_push(event.member_id, offer)

            return {
                "status": "accepted",
                "action": "offer_generated_and_delivered",
                "offer_id": offer.offer_id,
                "context_score": score.total,
                "offer_generated": True,
            }
        else:
            logger.warning(
                "Designer API returned non-201 for purchase-triggered offer",
                extra={"status_code": response.status_code},
            )
            return {
                "status": "accepted",
                "action": "designer_generation_failed",
                "offer_generated": False,
            }

    except Exception as e:
        logger.error("Scout → Designer call failed", extra={"error": str(e)})
        return {
            "status": "accepted",
            "action": "error",
            "offer_generated": False,
        }


@router.post(
    "/match",
    response_model=None,  # Union[MatchResponse, NoMatchResponse] — FastAPI infers from return
    summary="Match active Hub offers to a member purchase context",
    description=(
        "Scores Claude-approved Hub offers against real-time context signals "
        "(location, time, weather, behavioral profile). "
        "Returns the best match if score > 60, or a no-match response. "
        "Enforces CASL opt-out, 6h rate limit, 24h dedup, and quiet-hours (F-004)."
    ),
    responses={
        200: {"description": "Match result — activated, queued, rate_limited, or no match"},
        400: {"description": "Missing purchase_location or SCOUT_MATCH_ENABLED=false"},
        503: {"description": "Feature disabled via SCOUT_MATCH_ENABLED flag"},
    },
)
async def scout_match(
    request: MatchRequest,
    match_service: ScoutMatchService = Depends(get_scout_match_service),
) -> MatchResponse | NoMatchResponse:
    """POST /api/scout/match — Hub-offer activation engine.

    Design review F-004 fix: purchase_location is Optional in MatchRequest (avoids
    Pydantic 422); route validates presence and returns HTTP 400 if absent (AC-007).
    """
    if not settings.SCOUT_MATCH_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scout match endpoint is disabled (SCOUT_MATCH_ENABLED=false)",
        )

    # F-004: route-level validation — 400 (not 422) when purchase_location absent
    if request.purchase_location is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="purchase_location is required for Scout match activation",
        )

    result = await match_service.match(request)
    return result


@router.get(
    "/activation-log/{member_id}",
    summary="Return recent Scout activation records for a member",
    responses={
        200: {"description": "List of activation records (newest first)"},
    },
)
async def get_activation_log(
    member_id: str,
    limit: int = 20,
    scout_audit: ScoutAuditService = Depends(get_scout_audit_service),
) -> list[dict]:
    """GET /api/scout/activation-log/{member_id} — used by ContextDashboard (AC-021)."""
    return await scout_audit.get_recent(member_id, limit=limit)


@router.post(
    "/partner-trigger",
    response_model=PartnerTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Process a partner purchase event and trigger a CTC cross-sell offer",
    description=(
        "Receives a purchase event from a CTC partner store (Tim Hortons, WestJet, etc.). "
        "Authenticates via HMAC signature, deduplicates by event_id, then asynchronously "
        "classifies the purchase context using Claude Haiku and generates a CTC offer. "
        "Returns 202 immediately — offer generation happens in the background."
    ),
    responses={
        202: {"description": "Event accepted — offer generation queued"},
        400: {"description": "Duplicate event_id within 60s window"},
        401: {"description": "Invalid or missing X-Webhook-Signature"},
    },
)
async def partner_trigger(
    request: Request,
    event: PartnerPurchaseEvent,
    background_tasks: BackgroundTasks,
    x_webhook_signature: Optional[str] = Header(default=None),
    partner_service: PartnerTriggerService = Depends(get_partner_trigger_service),
) -> PartnerTriggerResponse:
    """Process a partner purchase event and asynchronously generate a CTC cross-sell offer."""
    # Verify HMAC signature in non-development environments
    if settings.ENVIRONMENT != "development":
        body = await request.body()
        if not verify_webhook_signature(body, x_webhook_signature, settings.SCOUT_WEBHOOK_SECRET):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing X-Webhook-Signature",
            )

    # Deduplicate events within 60s window
    if partner_service.is_duplicate(event.event_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Duplicate event_id '{event.event_id}' — already processed within 60s window",
        )

    # Queue Haiku classification + offer generation as background task
    # Returns 202 immediately — satisfies < 2s latency SLA
    background_tasks.add_task(partner_service.classify_and_generate, event)

    logger.info(
        "Partner trigger accepted",
        extra={"member_id": event.member_id, "partner_id": event.partner_id,
               "event_id": event.event_id},
    )
    return PartnerTriggerResponse(
        status="accepted",
        message=f"Partner purchase event from {event.partner_name} accepted for processing",
    )
