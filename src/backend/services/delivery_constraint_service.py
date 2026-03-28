"""Delivery constraint enforcement — rate limits, dedup, quiet hours.

F-002 FIX (MVP): Uses in-memory dict to track recent offers per member.
TODO(production): Replace with Hub query endpoint:
    GET /api/hub/offers?member_id={id}&trigger_type=purchase_triggered&since={iso_ts}
    This is a Hub design requirement documented in design_review.md F-002.

Scout-layer addition: RedisDeliveryConstraintService — Redis-backed rate limiting
that survives process restarts (CON-005 / AC-011).
Design review F-003 fix: all public methods catch redis.RedisError and return
fail-open defaults (allow activation) so Redis unavailability never propagates.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import redis as _redis_lib
from loguru import logger

from src.backend.core.config import settings


def _is_quiet_hours(now: Optional[datetime] = None) -> bool:
    """Check if current time falls within quiet hours (default: 10pm–8am)."""
    current = now or datetime.utcnow()
    hour = current.hour
    start = settings.QUIET_HOURS_START  # 22
    end = settings.QUIET_HOURS_END      # 8
    # Quiet hours wrap midnight: 22 → 0 → 8
    if start > end:
        return hour >= start or hour < end
    return start <= hour < end


class DeliveryConstraintService:
    def __init__(self) -> None:
        # F-002 (MVP): In-memory tracking per member_id → list of delivery timestamps
        self._delivery_log: dict[str, list[datetime]] = {}
        # Queued offers for morning delivery: member_id → (offer_id, queued_at)
        self._morning_queue: dict[str, tuple[str, datetime]] = {}

    def _get_deliveries_since(self, member_id: str, since: datetime) -> list[datetime]:
        """Return delivery timestamps for a member after a given point in time."""
        return [
            ts for ts in self._delivery_log.get(member_id, [])
            if ts >= since
        ]

    def retry_after_seconds(self, member_id: str) -> int:
        """Seconds until rate-limit window expires. In-memory fallback: returns constant."""
        return settings.PURCHASE_TRIGGER_RATE_LIMIT_HOURS * 3600

    def can_deliver(
        self,
        member_id: str,
        amount: float,
        now: Optional[datetime] = None,
        member_notifications_enabled: bool = True,
    ) -> tuple[bool, Optional[str]]:
        """Check all delivery constraints. Returns (allowed, reason_if_blocked).

        Constraints:
        0. Opt-out: member must have notifications enabled (CASL compliance)
        1. Rate limit: max 1 purchase-triggered offer per member per 6h
        2. Dedup: no duplicate offers within 24h (unless purchase > $100)
        3. Quiet hours: 10pm–8am → queue for 8am delivery

        Note: In production, member_notifications_enabled should be sourced from the
        member profile API (Hub or CRM). For MVP it defaults to True (no behaviour change).
        TODO(production): wire from real member preference store.
        """
        # Constraint 0: CASL compliance — respect notification opt-out
        if not member_notifications_enabled:
            logger.info(
                "Delivery suppressed — member opted out",
                extra={"member_id": member_id},
            )
            return False, "Member has opted out of marketing notifications"
        current = now or datetime.utcnow()

        # Constraint 1: 6-hour rate limit
        rate_limit_window = current - timedelta(hours=settings.PURCHASE_TRIGGER_RATE_LIMIT_HOURS)
        recent_6h = self._get_deliveries_since(member_id, rate_limit_window)
        if recent_6h:
            return False, f"Rate limit: member already received an offer within {settings.PURCHASE_TRIGGER_RATE_LIMIT_HOURS}h"

        # Constraint 2: 24-hour dedup (bypassed for high-value purchases)
        if amount <= settings.HIGH_VALUE_PURCHASE_THRESHOLD:
            dedup_window = current - timedelta(hours=settings.DEDUP_WINDOW_HOURS)
            recent_24h = self._get_deliveries_since(member_id, dedup_window)
            if recent_24h:
                return False, (
                    f"Dedup: member received an offer within {settings.DEDUP_WINDOW_HOURS}h "
                    f"(bypass threshold: ${settings.HIGH_VALUE_PURCHASE_THRESHOLD:.0f})"
                )

        # Constraint 3: Quiet hours
        if _is_quiet_hours(current):
            return False, "Quiet hours: delivery queued for 8am"

        return True, None

    def record_delivery(self, member_id: str, now: Optional[datetime] = None) -> None:
        """Record that a delivery was made to a member."""
        current = now or datetime.utcnow()
        if member_id not in self._delivery_log:
            self._delivery_log[member_id] = []
        self._delivery_log[member_id].append(current)

        # Prune old entries (keep only last 48h to bound memory)
        cutoff = current - timedelta(hours=48)
        self._delivery_log[member_id] = [
            ts for ts in self._delivery_log[member_id] if ts >= cutoff
        ]

    def queue_for_morning(self, member_id: str, offer_id: str) -> None:
        """Queue an offer for 8am delivery (quiet hours bypass)."""
        self._morning_queue[member_id] = (offer_id, datetime.utcnow())
        logger.info(
            "Offer queued for morning delivery",
            extra={"member_id": member_id, "offer_id": offer_id},
        )


class RedisDeliveryConstraintService:
    """Redis-backed delivery constraint enforcement (CON-005 / AC-011).

    Survives process restarts. Interface mirrors DeliveryConstraintService.

    F-003: every public method catches redis.RedisError and returns a fail-open
    default so Redis unavailability never blocks offer activation.

    Redis keys (all scoped to scout layer):
      scout:rate:<member_id>  — 6-hour rate-limit sentinel  (TTL = PURCHASE_TRIGGER_RATE_LIMIT_HOURS * 3600)
      scout:dedup:<member_id> — 24-hour dedup sentinel      (TTL = DEDUP_WINDOW_HOURS * 3600)
      scout:morning:<member_id> — morning-queue sentinel    (TTL = 86400)
    """

    _KEY_RATE = "scout:rate:{member_id}"
    _KEY_DEDUP = "scout:dedup:{member_id}"
    _KEY_MORNING = "scout:morning:{member_id}"

    def __init__(self, redis_url: Optional[str] = None) -> None:
        url = redis_url or settings.REDIS_URL
        self._redis = _redis_lib.Redis.from_url(url, decode_responses=True)

    def can_deliver(
        self,
        member_id: str,
        amount: float,
        now: Optional[datetime] = None,
        member_notifications_enabled: bool = True,
    ) -> tuple[bool, Optional[str]]:
        """Check all delivery constraints. Returns (allowed, reason_if_blocked).

        Fail-open on any redis.RedisError — Redis unavailability never blocks delivery.
        """
        # Constraint 0: CASL compliance
        if not member_notifications_enabled:
            logger.info(
                "Delivery suppressed — member opted out",
                extra={"member_id": member_id},
            )
            return False, "Member has opted out of marketing notifications"

        current = now or datetime.utcnow()

        # Constraint 1: 6-hour rate limit (fail-open on RedisError)
        try:
            key_rate = self._KEY_RATE.format(member_id=member_id)
            if self._redis.exists(key_rate):
                return False, (
                    f"Rate limit: member already received an offer within "
                    f"{settings.PURCHASE_TRIGGER_RATE_LIMIT_HOURS}h"
                )
        except _redis_lib.RedisError as exc:
            logger.warning(
                "redis_error:rate_limit_check — fail-open",
                extra={"member_id": member_id, "error": str(exc)},
            )

        # Constraint 2: 24-hour dedup (bypassed for high-value purchases; fail-open)
        if amount <= settings.HIGH_VALUE_PURCHASE_THRESHOLD:
            try:
                key_dedup = self._KEY_DEDUP.format(member_id=member_id)
                if self._redis.exists(key_dedup):
                    return False, (
                        f"Dedup: member received an offer within {settings.DEDUP_WINDOW_HOURS}h "
                        f"(bypass threshold: ${settings.HIGH_VALUE_PURCHASE_THRESHOLD:.0f})"
                    )
            except _redis_lib.RedisError as exc:
                logger.warning(
                    "redis_error:dedup_check — fail-open",
                    extra={"member_id": member_id, "error": str(exc)},
                )

        # Constraint 3: Quiet hours
        if _is_quiet_hours(current):
            return False, "Quiet hours: delivery queued for 8am"

        return True, None

    def record_delivery(self, member_id: str, now: Optional[datetime] = None) -> None:
        """Atomically set rate-limit and dedup keys. Silent on RedisError."""
        rate_ttl = settings.PURCHASE_TRIGGER_RATE_LIMIT_HOURS * 3600
        dedup_ttl = settings.DEDUP_WINDOW_HOURS * 3600
        try:
            pipe = self._redis.pipeline()
            pipe.set(self._KEY_RATE.format(member_id=member_id), "1", ex=rate_ttl)
            pipe.set(self._KEY_DEDUP.format(member_id=member_id), "1", ex=dedup_ttl)
            pipe.execute()
        except _redis_lib.RedisError as exc:
            logger.warning(
                "redis_error:record_delivery — keys not written",
                extra={"member_id": member_id, "error": str(exc)},
            )

    def retry_after_seconds(self, member_id: str) -> int:
        """Seconds until rate-limit key expires. Returns 0 on RedisError or no key."""
        try:
            ttl_ms = self._redis.pttl(self._KEY_RATE.format(member_id=member_id))
            if ttl_ms <= 0:
                return 0
            return max(1, (ttl_ms + 999) // 1000)  # ceiling division to full seconds
        except _redis_lib.RedisError:
            return 0

    def queue_for_morning(self, member_id: str, offer_id: str) -> None:
        """Queue an offer for 8am delivery. Silent on RedisError."""
        try:
            self._redis.setex(self._KEY_MORNING.format(member_id=member_id), 86400, offer_id)
        except _redis_lib.RedisError as exc:
            logger.warning(
                "redis_error:queue_for_morning — offer not queued in Redis",
                extra={"member_id": member_id, "offer_id": offer_id, "error": str(exc)},
            )
        logger.info(
            "Offer queued for morning delivery",
            extra={"member_id": member_id, "offer_id": offer_id},
        )
