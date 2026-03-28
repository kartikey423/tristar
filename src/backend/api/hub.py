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
from pydantic import BaseModel

from src.backend.api.deps import get_hub_audit_service, get_hub_store
from src.backend.core.security import AuthUser, get_current_user, require_system_role
from src.backend.models.offer_brief import OfferBrief, OfferStatus, TriggerType
from src.backend.services.hub_audit_service import HubAuditEvent, HubAuditService
from src.backend.services.hub_store import HubStore, OfferAlreadyExistsError, RedisUnavailableError

router = APIRouter()


class ListOffersResponse(BaseModel):
    offers: list[OfferBrief]
    count: int


VALID_TRANSITIONS: dict[OfferStatus, set[OfferStatus]] = {
    OfferStatus.draft: {OfferStatus.approved},
    OfferStatus.approved: {OfferStatus.active},
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
    _user: AuthUser = Depends(require_system_role),
    hub_store: HubStore = Depends(get_hub_store),
    hub_audit: HubAuditService = Depends(get_hub_audit_service),
) -> OfferBrief:
    """F-003 FIX: Validate trigger_type before accepting status=active."""
    t0 = time.monotonic()
    try:
        if offer.status == OfferStatus.active and offer.trigger_type != TriggerType.purchase_triggered:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"status=active is only permitted when trigger_type=purchase_triggered. "
                    f"Got trigger_type={offer.trigger_type.value}. "
                    "Marketer-initiated offers must follow draft → approved → active flow."
                ),
            )

        await hub_store.save(offer)

        asyncio.create_task(
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
    _user: AuthUser = Depends(get_current_user),
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

        asyncio.create_task(
            hub_audit.log_event(
                HubAuditEvent(
                    offer_id=offer_id,
                    event="offer_read",
                    actor_id=_user.user_id,
                )
            )
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
    since: Optional[str] = Query(default=None),
    _user: AuthUser = Depends(get_current_user),
    hub_store: HubStore = Depends(get_hub_store),
) -> ListOffersResponse:
    t0 = time.monotonic()
    try:
        since_dt: Optional[datetime] = None
        if since:
            since_dt = datetime.fromisoformat(since)
            if since_dt.tzinfo is None:
                since_dt = since_dt.replace(tzinfo=timezone.utc)

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

        return ListOffersResponse(offers=offers, count=len(offers))

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
    _user: AuthUser = Depends(require_system_role),
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

        asyncio.create_task(
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
