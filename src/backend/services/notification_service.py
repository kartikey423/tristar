"""Push notification service — delivers offers to members.

MVP implementation: logs + returns success. Production: calls push provider.
Fallback: email after 3 push failures.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import httpx
from loguru import logger

from src.backend.core.config import settings
from src.backend.models.offer_brief import OfferBrief


@dataclass
class NotificationResult:
    delivered: bool
    channel: str
    attempted_at: datetime
    delivered_at: Optional[datetime] = None
    error: Optional[str] = None


class NotificationService:
    def __init__(self, provider_url: Optional[str] = None) -> None:
        self._provider_url = provider_url or settings.NOTIFICATION_PROVIDER_URL

    async def _send_push_attempt(self, member_id: str, offer: OfferBrief) -> bool:
        """Single push notification attempt. Returns True on success."""
        payload = {
            "member_id": member_id,
            "offer_id": offer.offer_id,
            "title": "Exclusive offer for you",
            "body": offer.construct.description,
            "valid_until": offer.valid_until.isoformat() if offer.valid_until else None,
        }
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(
                    f"{self._provider_url}/push", json=payload
                )
            return response.status_code == 200
        except Exception as e:
            logger.debug(f"Push attempt failed: {e}")
            return False

    async def send_push(self, member_id: str, offer: OfferBrief) -> NotificationResult:
        """Send push notification with 3 retries.

        Falls back to email on 3 consecutive push failures.
        """
        attempted_at = datetime.utcnow()

        for attempt in range(1, 4):
            success = await self._send_push_attempt(member_id, offer)
            if success:
                logger.info(
                    "Push notification delivered",
                    extra={
                        "member_id": member_id,
                        "offer_id": offer.offer_id,
                        "attempt": attempt,
                    },
                )
                return NotificationResult(
                    delivered=True,
                    channel="push",
                    attempted_at=attempted_at,
                    delivered_at=datetime.utcnow(),
                )
            if attempt < 3:
                await asyncio.sleep(0.5 * attempt)

        # All push attempts failed — fall back to email
        logger.warning(
            "Push notification failed after 3 attempts, falling back to email",
            extra={"member_id": member_id, "offer_id": offer.offer_id},
        )
        return await self.send_email_fallback(member_id, offer)

    async def send_email_fallback(
        self, member_id: str, offer: OfferBrief
    ) -> NotificationResult:
        """Send email notification as fallback after push failures."""
        attempted_at = datetime.utcnow()
        try:
            payload = {
                "member_id": member_id,
                "offer_id": offer.offer_id,
                "subject": f"Exclusive offer: {offer.objective[:60]}",
                "body": offer.construct.description,
            }
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(
                    f"{self._provider_url}/email", json=payload
                )

            if response.status_code == 200:
                return NotificationResult(
                    delivered=True,
                    channel="email",
                    attempted_at=attempted_at,
                    delivered_at=datetime.utcnow(),
                )
        except Exception as e:
            logger.error(
                f"Email fallback also failed: {e}",
                extra={"member_id": member_id, "offer_id": offer.offer_id},
            )

        return NotificationResult(
            delivered=False,
            channel="email",
            attempted_at=attempted_at,
            error="Both push and email delivery failed",
        )
