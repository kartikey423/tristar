"""HTTP client for the Hub API — saves and retrieves offers from the shared state store.

F-003 FIX: Client-side assertion enforces that status=active is ONLY sent
when trigger_type=purchase_triggered. The Hub server also enforces this with a 422.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import httpx
from loguru import logger

from src.backend.core.config import settings
from src.backend.models.offer_brief import OfferBrief, OfferStatus, TriggerType
from src.backend.services.scout_service_auth import scout_auth


class HubSaveError(Exception):
    """Raised when the Hub API returns an error while saving an offer."""

    pass


class HubApiClient:
    def __init__(self, base_url: Optional[str] = None) -> None:
        self._base_url = (base_url or settings.HUB_API_URL).rstrip("/")
        self._client = httpx.AsyncClient(timeout=10.0)

    async def close(self) -> None:
        """Close the underlying HTTP client. Call during app shutdown."""
        await self._client.aclose()

    async def save_offer(self, offer: OfferBrief) -> OfferBrief:
        """POST offer to Hub. Returns the saved offer with Hub-assigned metadata.

        F-003: Asserts that only purchase_triggered offers can be saved with status=active.
        """
        if offer.status == OfferStatus.active and offer.trigger_type != TriggerType.purchase_triggered:
            raise ValueError(
                "BUG: Attempted to save an offer with status=active and "
                f"trigger_type={offer.trigger_type.value}. "
                "Only purchase_triggered offers may be directly activated. "
                "Marketer-initiated offers must go through draft → approved first."
            )

        payload = offer.model_dump(mode="json")

        try:
            response = await self._client.post(
                f"{self._base_url}/offers",
                json=payload,
                headers=scout_auth.bearer_header(),
            )

            if response.status_code == 422:
                error_detail = response.json().get("detail", "Validation error")
                raise HubSaveError(f"Hub rejected offer (422): {error_detail}")

            if response.status_code == 409:
                raise HubSaveError(
                    f"Duplicate offer_id {offer.offer_id} already exists in Hub"
                )

            response.raise_for_status()

        except httpx.RequestError as e:
            raise HubSaveError(f"Hub API unreachable: {e}") from e
        except HubSaveError:
            raise
        except httpx.HTTPStatusError as e:
            raise HubSaveError(
                f"Hub API error {e.response.status_code}: {e.response.text}"
            ) from e

        saved = response.json()
        logger.info(
            "Offer saved to Hub",
            extra={"offer_id": offer.offer_id, "status": offer.status.value},
        )
        return OfferBrief(**saved)

    async def get_offer(self, offer_id: str) -> OfferBrief:
        """GET offer by ID from Hub."""
        try:
            response = await self._client.get(
                f"{self._base_url}/offers/{offer_id}",
                headers=scout_auth.bearer_header(),
            )
            response.raise_for_status()
            return OfferBrief(**response.json())
        except httpx.HTTPStatusError as e:
            raise HubSaveError(
                f"Hub API error {e.response.status_code} for offer {offer_id}"
            ) from e
        except httpx.RequestError as e:
            raise HubSaveError(f"Hub API unreachable: {e}") from e

    async def get_recent_member_offers(
        self,
        member_id: str,
        since: datetime,
        trigger_type: Optional[TriggerType] = None,
    ) -> list[OfferBrief]:
        """GET Hub offers for a member since a given timestamp.

        NOTE (F-002): This endpoint is required for production rate limiting in
        DeliveryConstraintService. The Hub layer must implement:
            GET /api/hub/offers?member_id=<id>&trigger_type=<type>&since=<iso_ts>
        The MVP uses in-memory tracking in delivery_constraint_service.py instead.
        """
        params: dict = {"member_id": member_id, "since": since.isoformat()}
        if trigger_type:
            params["trigger_type"] = trigger_type.value

        try:
            response = await self._client.get(
                f"{self._base_url}/offers",
                params=params,
                headers=scout_auth.bearer_header(),
            )
            response.raise_for_status()
            data = response.json()
            return [OfferBrief(**o) for o in data.get("offers", [])]
        except httpx.HTTPStatusError as e:
            logger.warning(
                f"Hub member offer query failed: {e.response.status_code}. "
                "Falling back to in-memory tracking."
            )
            return []
        except httpx.RequestError as e:
            logger.warning(f"Hub API unreachable for member query. Falling back. Error: {e}")
            return []
