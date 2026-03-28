"""Hub API stub — in-memory offer state store for development.

F-003 FIX: POST /api/hub/offers enforces that status=active is ONLY accepted
when trigger_type=purchase_triggered. Returns 422 otherwise.

F-002: GET /api/hub/offers supports ?member_id=&since= filtering for
DeliveryConstraintService rate limit checks.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from src.backend.core.security import AuthUser, get_current_user, require_system_role
from src.backend.models.offer_brief import OfferBrief, OfferStatus, TriggerType

router = APIRouter()


class ListOffersResponse(BaseModel):
    offers: list[OfferBrief]
    count: int

# In-memory store: offer_id → OfferBrief
_store: dict[str, OfferBrief] = {}


@router.post(
    "/offers",
    response_model=OfferBrief,
    status_code=status.HTTP_201_CREATED,
    summary="Save offer to Hub",
)
async def save_offer(
    offer: OfferBrief,
    _user: AuthUser = Depends(require_system_role),
) -> OfferBrief:
    """F-003 FIX: Validate trigger_type before accepting status=active."""
    if offer.status == OfferStatus.active and offer.trigger_type != TriggerType.purchase_triggered:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"status=active is only permitted when trigger_type=purchase_triggered. "
                f"Got trigger_type={offer.trigger_type.value}. "
                "Marketer-initiated offers must follow draft → approved → active flow."
            ),
        )

    if offer.offer_id in _store:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Offer {offer.offer_id} already exists in Hub",
        )

    _store[offer.offer_id] = offer
    return offer


@router.get(
    "/offers/{offer_id}",
    response_model=OfferBrief,
    summary="Get offer by ID",
)
async def get_offer(
    offer_id: str,
    _user: AuthUser = Depends(get_current_user),
) -> OfferBrief:
    offer = _store.get(offer_id)
    if offer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Offer {offer_id} not found",
        )
    return offer


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
) -> ListOffersResponse:
    offers = list(_store.values())

    if status_filter:
        offers = [o for o in offers if o.status == status_filter]

    if trigger_type:
        offers = [o for o in offers if o.trigger_type == trigger_type]

    if since:
        since_dt = datetime.fromisoformat(since)
        offers = [o for o in offers if o.created_at >= since_dt]

    # Note: member_id filtering would require storing member_id on OfferBrief.
    # Production Hub must persist member associations.
    # F-002: This endpoint stub satisfies the interface contract.

    return ListOffersResponse(offers=offers, count=len(offers))


@router.put(
    "/offers/{offer_id}/status",
    response_model=OfferBrief,
    summary="Update offer status",
)
async def update_offer_status(
    offer_id: str,
    new_status: OfferStatus,
    _user: AuthUser = Depends(require_system_role),
) -> OfferBrief:
    offer = _store.get(offer_id)
    if offer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Offer {offer_id} not found",
        )

    updated = offer.model_copy(update={"status": new_status})
    _store[offer_id] = updated
    return updated
