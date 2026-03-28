"""Compliance audit logging service.

PII Policy:
- Log member_id ONLY — never names, emails, phone numbers
- F-007 FIX: GPS lat/lon coordinates are NEVER logged. Only store_id and store_name.
- _scrub_pii() removes emails and phone numbers from objective text
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from loguru import logger

from src.backend.models.offer_brief import OfferBrief, RiskFlags

# Regex patterns for PII scrubbing
_EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
_PHONE_PATTERN = re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")


class AuditLogService:
    def _scrub_pii(self, text: str) -> str:
        """Remove emails and phone numbers from free-text fields."""
        text = _EMAIL_PATTERN.sub("[EMAIL_REDACTED]", text)
        text = _PHONE_PATTERN.sub("[PHONE_REDACTED]", text)
        return text

    def log_generation(
        self,
        offer: OfferBrief,
        member_id: str,
        trigger: str = "marketer_initiated",
        duration_ms: Optional[float] = None,
    ) -> None:
        """Log an offer generation event."""
        logger.info(
            "offer.generated",
            extra={
                "event": "offer.generated",
                "offer_id": offer.offer_id,
                "member_id": member_id,
                "trigger": trigger,
                "objective": self._scrub_pii(offer.objective[:200]),
                "segment_name": offer.segment.name,
                "construct_type": offer.construct.type,
                "duration_ms": duration_ms,
                "timestamp": datetime.utcnow().isoformat(),
                # F-007: location fields intentionally omitted
            },
        )

    def log_approval(self, offer: OfferBrief, approved_by: str) -> None:
        """Log a marketer approval event."""
        logger.info(
            "offer.approved",
            extra={
                "event": "offer.approved",
                "offer_id": offer.offer_id,
                "approved_by": approved_by,
                "status_after": offer.status.value,
                "construct_type": offer.construct.type,
                "construct_value": offer.construct.value,
                "timestamp": datetime.utcnow().isoformat(),
                # F-007: no GPS coordinates logged
            },
        )

    def log_delivery(
        self,
        offer: OfferBrief,
        member_id: str,
        channel: str,
        store_id: Optional[str] = None,
        store_name: Optional[str] = None,
    ) -> None:
        """Log offer delivery to a member.

        F-007: Only store_id and store_name are logged — lat/lon excluded.
        """
        logger.info(
            "offer.delivered",
            extra={
                "event": "offer.delivered",
                "offer_id": offer.offer_id,
                "member_id": member_id,
                "channel": channel,
                "store_id": store_id,          # safe: store identifier
                "store_name": store_name,      # safe: store name
                # lat/lon intentionally NOT logged (F-007)
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    def log_fraud_block(
        self,
        offer_id: str,
        member_id: str,
        severity: str,
        warnings: list[str],
    ) -> None:
        """Log a fraud-blocked offer event."""
        logger.warning(
            "offer.fraud_blocked",
            extra={
                "event": "offer.fraud_blocked",
                "offer_id": offer_id,
                "member_id": member_id,
                "severity": severity,
                "warnings": warnings,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    def log_purchase_trigger(
        self,
        member_id: str,
        event_id: str,
        store_name: str,
        store_id: Optional[str],
        amount: float,
        context_score: float,
        triggered: bool,
        skip_reason: Optional[str] = None,
    ) -> None:
        """Log a purchase event processing outcome.

        F-007: purchase location lat/lon is NEVER included.
        Only store_id and store_name are safe to log.
        """
        logger.info(
            "scout.purchase_event",
            extra={
                "event": "scout.purchase_event",
                "member_id": member_id,
                "event_id": event_id,
                "store_name": store_name,   # safe
                "store_id": store_id,       # safe
                # lat/lon intentionally NOT logged (F-007)
                "amount_bucket": self._bucket_amount(amount),  # bucketed, not exact
                "context_score": round(context_score, 1),
                "triggered": triggered,
                "skip_reason": skip_reason,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    def _bucket_amount(self, amount: float) -> str:
        """Bucket purchase amount to avoid logging exact spend (privacy)."""
        if amount < 25:
            return "<25"
        if amount < 50:
            return "25-50"
        if amount < 100:
            return "50-100"
        if amount < 250:
            return "100-250"
        return "250+"
