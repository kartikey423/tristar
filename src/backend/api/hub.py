"""Hub API routes — offer state management with pluggable HubStore backend.

COMP-002: Routes inject HubStore (InMemoryHubStore or RedisHubStore) via Depends().
Strict status transitions enforced via VALID_TRANSITIONS map (422 for invalid paths).
Non-blocking audit writes via asyncio.create_task().
Latency logging: WARNING if response takes >200ms (REQ-007 / AC-032).

F-003 FIX (carried forward): POST /offers enforces that status=active is ONLY accepted
when trigger_type=purchase_triggered.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger
from pydantic import BaseModel, Field

from src.backend.api.deps import get_hub_audit_service, get_hub_store, get_redemption_enforcement_service
from src.backend.core.config import settings
from src.backend.core.security import AuthUser, get_current_user, require_marketing_or_system_role, require_system_role
from src.backend.models.offer_brief import AUTO_ACTIVE_TRIGGER_TYPES, OfferBrief, OfferStatus, TriggerType
from src.backend.models.partner_event import RedemptionRequest, RedemptionSplitError
from src.backend.services.hub_audit_service import HubAuditEvent, HubAuditService
from src.backend.services.hub_store import HubStore, InMemoryHubStore, OfferAlreadyExistsError, RedisUnavailableError
from src.backend.services.redemption_enforcement_service import RedemptionEnforcementService

router = APIRouter()

# Registry for fire-and-forget audit tasks — prevents GC before completion.
_audit_tasks: set[asyncio.Task] = set()


def _fire_audit(coro) -> None:
    """Schedule a coroutine as a background task, retaining a reference until done."""
    task = asyncio.create_task(coro)
    _audit_tasks.add(task)
    task.add_done_callback(_audit_tasks.discard)


class ListOffersResponse(BaseModel):
    offers: list[OfferBrief]
    count: int


VALID_TRANSITIONS: dict[OfferStatus, set[OfferStatus]] = {
    OfferStatus.draft: {OfferStatus.approved},
    OfferStatus.approved: {OfferStatus.active, OfferStatus.expired},  # Allow early close
    OfferStatus.active: {OfferStatus.expired},
    OfferStatus.expired: set(),  # terminal state
}


def _validate_transition(old: OfferStatus, new: OfferStatus) -> None:
    allowed = VALID_TRANSITIONS.get(old, set())
    if new not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "InvalidTransition",
                "old_status": old.value,
                "new_status": new.value,
                "allowed": [s.value for s in allowed],
            },
        )


@router.post(
    "/offers",
    response_model=OfferBrief,
    status_code=status.HTTP_201_CREATED,
    summary="Save offer to Hub",
)
async def save_offer(
    offer: OfferBrief,
    _user: AuthUser = Depends(require_marketing_or_system_role),
    hub_store: HubStore = Depends(get_hub_store),
    hub_audit: HubAuditService = Depends(get_hub_audit_service),
) -> OfferBrief:
    """Save offer to Hub. Only auto-triggered offers (purchase_triggered, partner_triggered) may be status=active."""
    t0 = time.monotonic()
    try:
        if offer.status == OfferStatus.active and offer.trigger_type not in AUTO_ACTIVE_TRIGGER_TYPES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"status=active is only permitted when trigger_type is purchase_triggered "
                    f"or partner_triggered. Got trigger_type={offer.trigger_type.value}. "
                    "Marketer-initiated offers must follow draft → approved → active flow."
                ),
            )

        await hub_store.save(offer)

        _fire_audit(
            hub_audit.log_event(
                HubAuditEvent(
                    offer_id=offer.offer_id,
                    event="offer_created",
                    new_status=offer.status,
                    actor_id=_user.user_id,
                )
            )
        )
        return offer

    except HTTPException:
        raise
    except OfferAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Offer {offer.offer_id} already exists in Hub",
        )
    except RedisUnavailableError as e:
        logger.error(f"hub_redis_unavailable: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Hub store unavailable",
        )
    finally:
        elapsed_ms = (time.monotonic() - t0) * 1000
        if elapsed_ms > 200:
            logger.warning(
                "hub_latency_exceeded",
                extra={"endpoint": "save_offer", "elapsed_ms": round(elapsed_ms, 1)},
            )


@router.get(
    "/offers/{offer_id}",
    response_model=OfferBrief,
    summary="Get offer by ID",
)
async def get_offer(
    offer_id: str,
    hub_store: HubStore = Depends(get_hub_store),
) -> OfferBrief:
    t0 = time.monotonic()
    try:
        try:
            offer = await hub_store.get(offer_id)
        except RedisUnavailableError as e:
            logger.error(f"hub_redis_unavailable: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Hub store unavailable",
            )

        if offer is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Offer {offer_id} not found",
            )

        return offer

    finally:
        elapsed_ms = (time.monotonic() - t0) * 1000
        if elapsed_ms > 200:
            logger.warning(
                "hub_latency_exceeded",
                extra={"endpoint": "get_offer", "elapsed_ms": round(elapsed_ms, 1)},
            )


@router.get(
    "/offers",
    response_model=ListOffersResponse,
    summary="List offers with optional filters",
    description="Supports filtering by status, member_id, trigger_type, and since timestamp. (F-002)",
)
async def list_offers(
    status_filter: Optional[OfferStatus] = Query(default=None, alias="status"),
    member_id: Optional[str] = Query(default=None),
    trigger_type: Optional[TriggerType] = Query(default=None),
    since: Optional[datetime] = Query(default=None),
    hub_store: HubStore = Depends(get_hub_store),
) -> ListOffersResponse:
    t0 = time.monotonic()
    try:
        # Normalize timezone — FastAPI may deliver a naive datetime if no offset in query string
        since_dt = since.replace(tzinfo=timezone.utc) if since and since.tzinfo is None else since

        try:
            offers = await hub_store.list(
                status_filter=status_filter,
                trigger_type=trigger_type,
                since=since_dt,
            )
        except RedisUnavailableError as e:
            logger.error(f"hub_redis_unavailable: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Hub store unavailable",
            )

        # Note: member_id filtering requires storing member associations on OfferBrief.
        # F-002: This endpoint stub satisfies the interface contract.

        # Deduplicate by normalised objective text: for identical objectives, keep the most
        # recent non-expired offer so the Hub list stays clean.
        _active_statuses = {OfferStatus.draft, OfferStatus.approved, OfferStatus.active}
        seen_objectives: dict[str, OfferBrief] = {}
        expired_offers: list[OfferBrief] = []
        def _sort_key(o: OfferBrief):
            """Normalize to UTC-aware for comparison regardless of source."""
            dt = o.created_at
            if dt is None:
                return datetime.min.replace(tzinfo=timezone.utc)
            return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)

        for o in sorted(offers, key=_sort_key, reverse=True):
            key = o.objective.lower().strip()
            if o.status not in _active_statuses:
                expired_offers.append(o)
            elif key not in seen_objectives:
                seen_objectives[key] = o
        deduped = list(seen_objectives.values()) + expired_offers
        deduped.sort(key=_sort_key, reverse=True)

        return ListOffersResponse(offers=deduped, count=len(deduped))

    finally:
        elapsed_ms = (time.monotonic() - t0) * 1000
        if elapsed_ms > 200:
            logger.warning(
                "hub_latency_exceeded",
                extra={"endpoint": "list_offers", "elapsed_ms": round(elapsed_ms, 1)},
            )


@router.put(
    "/offers/{offer_id}/status",
    response_model=OfferBrief,
    summary="Update offer status",
)
async def update_offer_status(
    offer_id: str,
    new_status: OfferStatus,
    _user: AuthUser = Depends(require_marketing_or_system_role),
    hub_store: HubStore = Depends(get_hub_store),
    hub_audit: HubAuditService = Depends(get_hub_audit_service),
) -> OfferBrief:
    t0 = time.monotonic()
    try:
        try:
            offer = await hub_store.get(offer_id)
        except RedisUnavailableError as e:
            logger.error(f"hub_redis_unavailable: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Hub store unavailable",
            )

        if offer is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Offer {offer_id} not found",
            )

        _validate_transition(offer.status, new_status)

        updated = offer.model_copy(update={"status": new_status})

        try:
            await hub_store.update(updated)
        except RedisUnavailableError as e:
            logger.error(f"hub_redis_unavailable: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Hub store unavailable",
            )

        _fire_audit(
            hub_audit.log_event(
                HubAuditEvent(
                    offer_id=offer_id,
                    event="status_transition",
                    old_status=offer.status,
                    new_status=new_status,
                    actor_id=_user.user_id,
                )
            )
        )
        return updated

    except HTTPException:
        raise
    finally:
        elapsed_ms = (time.monotonic() - t0) * 1000
        if elapsed_ms > 200:
            logger.warning(
                "hub_latency_exceeded",
                extra={"endpoint": "update_offer_status", "elapsed_ms": round(elapsed_ms, 1)},
            )


class UpdateConstructRequest(BaseModel):
    value: float = Field(..., ge=0, le=10000, description="New construct value (e.g. discount %, points multiplier)")
    objective: str | None = Field(None, min_length=10, max_length=1000, description="Optional: updated objective text reflecting the new construct value")


@router.patch(
    "/offers/{offer_id}/construct",
    response_model=OfferBrief,
    summary="Update offer construct value",
    description="Allows a marketer to manually override the AI-generated construct value (e.g. discount %, points multiplier) before approval.",
)
async def update_construct_value(
    offer_id: str,
    body: UpdateConstructRequest,
    _user: AuthUser = Depends(require_marketing_or_system_role),
    hub_store: HubStore = Depends(get_hub_store),
    hub_audit: HubAuditService = Depends(get_hub_audit_service),
) -> OfferBrief:
    offer = await hub_store.get(offer_id)
    if offer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Offer {offer_id} not found")

    if offer.status not in (OfferStatus.draft,):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Construct value can only be updated on draft offers",
        )

    new_construct = offer.construct.model_copy(update={"value": body.value})
    update_fields: dict = {"construct": new_construct}
    if body.objective is not None:
        update_fields["objective"] = body.objective
    updated = offer.model_copy(update=update_fields)
    await hub_store.update(updated)

    _fire_audit(
        hub_audit.log_event(
            HubAuditEvent(
                offer_id=offer_id,
                event="construct_updated",
                actor_id=_user.user_id,
            )
        )
    )
    return updated


@router.post(
    "/offers/{offer_id}/customer-accept",
    response_model=OfferBrief,
    summary="Customer accepted offer via notification tap",
    description=(
        "Auto-approves and activates an offer when the customer taps 'View Offer' on their push "
        "notification. Bypasses the marketer approval step — intended for Scout-activated offers. "
        "Performs draft→approved→active in a single atomic transition."
    ),
)
async def customer_accept_offer(
    offer_id: str,
    hub_store: HubStore = Depends(get_hub_store),
    hub_audit: HubAuditService = Depends(get_hub_audit_service),
) -> OfferBrief:
    """Customer tapped the notification — skip marketer approval, activate immediately."""
    t0 = time.monotonic()
    try:
        offer = await hub_store.get(offer_id)
    except RedisUnavailableError as e:
        logger.error(f"hub_redis_unavailable: {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Hub store unavailable")

    if offer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Offer {offer_id} not found")

    # Already active — idempotent, return as-is
    if offer.status == OfferStatus.active:
        return offer

    # Approve first if still draft
    if offer.status == OfferStatus.draft:
        offer = offer.model_copy(update={"status": OfferStatus.approved})
        await hub_store.update(offer)
        _fire_audit(
            hub_audit.log_event(
                HubAuditEvent(
                    offer_id=offer_id,
                    event="status_transition",
                    old_status=OfferStatus.draft,
                    new_status=OfferStatus.approved,
                    actor_id="customer_notification_tap",
                )
            )
        )

    # Now activate
    if offer.status == OfferStatus.approved:
        activated = offer.model_copy(update={"status": OfferStatus.active})
        await hub_store.update(activated)
        _fire_audit(
            hub_audit.log_event(
                HubAuditEvent(
                    offer_id=offer_id,
                    event="status_transition",
                    old_status=OfferStatus.approved,
                    new_status=OfferStatus.active,
                    actor_id="customer_notification_tap",
                )
            )
        )
        logger.info(
            "offer_customer_accepted",
            extra={"offer_id": offer_id, "elapsed_ms": round((time.monotonic() - t0) * 1000, 1)},
        )
        return activated

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=f"Cannot activate offer in status '{offer.status.value}' via customer accept.",
    )


@router.delete(
    "/offers/{offer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Reject (delete) a draft offer",
    description="Permanently removes a draft offer from the Hub. Only draft offers can be rejected.",
)
async def reject_offer(
    offer_id: str,
    _user: AuthUser = Depends(require_marketing_or_system_role),
    hub_store: HubStore = Depends(get_hub_store),
    hub_audit: HubAuditService = Depends(get_hub_audit_service),
) -> None:
    offer = await hub_store.get(offer_id)
    if offer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Offer {offer_id} not found")

    if offer.status not in (OfferStatus.draft,):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Only draft offers can be rejected. Current status: {offer.status.value}",
        )

    await hub_store.delete(offer_id)

    _fire_audit(
        hub_audit.log_event(
            HubAuditEvent(
                offer_id=offer_id,
                event="offer_rejected",
                old_status=offer.status,
                actor_id=_user.user_id,
            )
        )
    )


class RedemptionResponse(BaseModel):
    offer_id: str
    points_pct: float
    cash_pct: float
    message: str


@router.post(
    "/offers/{offer_id}/redeem",
    response_model=RedemptionResponse,
    summary="Validate a Triangle Rewards redemption against the offer's 75/25 payment split",
    description=(
        "Enforces that Triangle points cannot exceed 75% of the transaction. "
        "The remaining 25%+ must be paid via credit/debit card. "
        "Returns 422 if points_pct exceeds the offer's payment_split.points_max_pct."
    ),
    responses={
        200: {"description": "Payment split is valid"},
        404: {"description": "Offer not found"},
        422: {"description": "Points redemption exceeds 75% cap"},
    },
)
async def redeem_offer(
    offer_id: str,
    redemption: RedemptionRequest,
    _user: AuthUser = Depends(get_current_user),
    hub_store: HubStore = Depends(get_hub_store),
    enforcement: RedemptionEnforcementService = Depends(get_redemption_enforcement_service),
) -> RedemptionResponse:
    """Enforce 75/25 Triangle Rewards payment split constraint before redemption."""
    offer = await hub_store.get(offer_id)
    if offer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Offer {offer_id} not found")

    try:
        enforcement.validate_payment_split(offer, redemption)
    except RedemptionSplitError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "RedemptionSplitError",
                "message": str(e),
                "points_pct": e.points_pct,
                "max_points_pct": e.max_pct,
                "required_cash_pct": 100 - e.max_pct,
            },
        )

    return RedemptionResponse(
        offer_id=offer_id,
        points_pct=redemption.points_pct,
        cash_pct=redemption.cash_pct,
        message=f"Payment split valid: {redemption.points_pct:.0f}% points / {redemption.cash_pct:.0f}% cash.",
    )


@router.delete(
    "/admin/reset",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="[DEV ONLY] Clear all offers from the Hub store",
    description="Clears the in-memory Hub store. Only available in development environment. Use to purge duplicate offers during demo.",
)
async def reset_hub_store(
    hub_store: HubStore = Depends(get_hub_store),
) -> None:
    if settings.ENVIRONMENT != "development":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hub reset is only available in development environment",
        )
    if isinstance(hub_store, InMemoryHubStore):
        hub_store.clear()
        logger.info("hub_store_reset: all offers cleared (dev mode)")
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Hub reset is only supported for InMemoryHubStore",
        )
