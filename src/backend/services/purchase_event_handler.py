"""Purchase event handler — enriches context and prepares it for scoring.

F-008 FIX: Enrichment calls (member history, nearby stores, weather) are
executed concurrently using asyncio.gather to minimize latency.

F-009: Respects PURCHASE_TRIGGER_ENABLED flag and PILOT_MEMBER_IDS allowlist.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Optional

import httpx
from loguru import logger

from src.backend.core.config import settings
from src.backend.models.purchase_event import (
    EnrichedContext,
    MemberProfile,
    NearbyStore,
    PurchaseEventPayload,
    WeatherConditions,
)

# Deduplication window: same event_id within 60s is a split/duplicate transaction
_DEDUP_WINDOW_SECONDS = 60
_seen_events: dict[str, datetime] = {}


def _is_duplicate_event(event_id: str) -> bool:
    """Check if this event_id was seen in the last 60 seconds."""
    cutoff = datetime.utcnow() - timedelta(seconds=_DEDUP_WINDOW_SECONDS)
    # Prune stale entries
    stale = [eid for eid, ts in _seen_events.items() if ts < cutoff]
    for eid in stale:
        del _seen_events[eid]

    if event_id in _seen_events:
        return True

    _seen_events[event_id] = datetime.utcnow()
    return False


async def _fetch_member_history(member_id: str) -> Optional[MemberProfile]:
    """Fetch member profile and purchase history from CRM/loyalty service.

    MVP: Returns a mock MemberProfile. Production: Call loyalty API.
    """
    # Mock: simulate ~50ms API call
    await asyncio.sleep(0)  # yield to event loop
    return MemberProfile(
        member_id=member_id,
        segment="active",
        total_spend_90_days=250.0,
        purchase_count_90_days=4,
        preferred_categories=["sporting_goods", "outdoor"],
        last_ctc_purchase_days_ago=5,
        loyalty_tier="silver",
    )


async def _find_nearby_ctc_stores(lat: float, lon: float) -> list[NearbyStore]:
    """Find CTC stores within 2km of the given coordinates.

    MVP: Returns mock nearby stores. Production: Call location service.
    """
    await asyncio.sleep(0)  # yield to event loop
    # Mock stores — production would query a geospatial service
    return [
        NearbyStore(
            store_id="CTC-ON-001",
            store_name="Canadian Tire - Downtown",
            distance_km=0.8,
            category="general",
        ),
        NearbyStore(
            store_id="SC-ON-001",
            store_name="Sport Chek - Downtown",
            distance_km=1.2,
            category="sporting_goods",
        ),
    ]


async def _get_weather(lat: float, lon: float) -> Optional[WeatherConditions]:
    """Fetch current weather conditions for the given coordinates.

    MVP: Returns mock weather. Production: Call OpenWeatherMap API.
    Note: lat/lon are used only for the API call, never logged (F-007).
    """
    await asyncio.sleep(0)  # yield to event loop
    return WeatherConditions(
        condition="clear",
        temperature_c=5.0,
        is_adverse=False,
    )


class PurchaseEventHandler:
    def __init__(self) -> None:
        self._enabled = settings.PURCHASE_TRIGGER_ENABLED
        self._pilot_ids = settings.pilot_member_ids

    def _is_allowed(self, member_id: str) -> tuple[bool, Optional[str]]:
        """Check feature flag and pilot allowlist before processing."""
        if not self._enabled:
            return False, "PURCHASE_TRIGGER_ENABLED is False"

        # If pilot_ids is non-empty, only those members are allowed
        if self._pilot_ids and member_id not in self._pilot_ids:
            return False, f"Member {member_id} not in pilot allowlist"

        return True, None

    async def handle(self, event: PurchaseEventPayload) -> Optional[EnrichedContext]:
        """Process a purchase event and return enriched context if allowed.

        Returns None if:
        - Feature is disabled (F-009)
        - Member not in pilot list (F-009)
        - Event is a duplicate within 60s window

        Note: Refund events must be rejected by the caller before invoking this method.

        F-008 FIX: member history, nearby stores, and weather are fetched
        concurrently via asyncio.gather to minimize enrichment latency.
        """
        # Gate 0: Reject refund events — no offer should be triggered for a refund
        if event.is_refund:
            logger.debug("Purchase event skipped: refund", extra={"event_id": event.event_id})
            return None

        # Gate 1: Feature flag + pilot check
        allowed, reason = self._is_allowed(event.member_id)
        if not allowed:
            logger.debug(
                f"Purchase event skipped: {reason}",
                extra={"event_id": event.event_id},
            )
            return None

        # Gate 2: Deduplication (refund check is handled at route level)
        if _is_duplicate_event(event.event_id):
            logger.debug(
                "Purchase event skipped: duplicate within 60s window",
                extra={"event_id": event.event_id},
            )
            return None

        # F-008 FIX: Concurrent enrichment — all 3 calls in parallel
        start = asyncio.get_running_loop().time()
        member, nearby_stores, weather = await asyncio.gather(
            _fetch_member_history(event.member_id),
            _find_nearby_ctc_stores(event.location.lat, event.location.lon),
            _get_weather(event.location.lat, event.location.lon),
            return_exceptions=True,  # R-010: handle individual failures gracefully
        )

        # Handle partial failures from gather
        if isinstance(member, Exception):
            logger.warning(f"Member enrichment failed: {member}")
            member = None
        if isinstance(nearby_stores, Exception):
            logger.warning(f"Nearby stores enrichment failed: {nearby_stores}")
            nearby_stores = []
        if isinstance(weather, Exception):
            logger.warning(f"Weather enrichment failed: {weather}")
            weather = None

        duration_ms = (asyncio.get_running_loop().time() - start) * 1000

        return EnrichedContext(
            event=event,
            member=member,
            nearby_stores=nearby_stores or [],
            weather=weather,
            enrichment_duration_ms=round(duration_ms, 2),
        )
