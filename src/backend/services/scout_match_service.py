"""Scout match service — orchestrates POST /api/scout/match activation pipeline.

Pipeline per request:
  1. Concurrently enrich context: member profile, nearby stores, weather.
  2. Fetch up to CANDIDATE_CAP active offers from Hub.
    3. Score each offer with ClaudeContextScoringService and keep the best score.
    4. If best score is <= 60 → return NoMatchResponse.
  5. Check delivery constraints (CASL, rate-limit, dedup, quiet-hours).
  6. Dispatch outcome: activated | queued | rate_limited.
  7. Append ScoutActivationRecord to audit log (no GPS — CON-002 / AC-017).

Design review fixes applied:
  F-005: _CANDIDATE_CAP = 5 prevents unbounded Claude calls.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Union

import httpx
from loguru import logger

from src.backend.core.config import settings
from src.backend.models.offer_brief import OfferBrief
from src.backend.models.purchase_event import GeoPoint, MemberProfile, NearbyStore, WeatherConditions
from src.backend.models.scout_match import (
    EnrichedMatchContext,
    MatchRequest,
    MatchResponse,
    NoMatchResponse,
    ScoutActivationRecord,
    ScoutOutcome,
    SmartMatchResponse,
    SmartOfferItem,
)
from src.backend.services.claude_context_scoring_service import (
    ClaudeContextScoringService,
    ClaudeScoreResult,
)
from src.backend.services.ctc_store_fixtures import CTCStoreFixtures
from src.backend.services.delivery_constraint_service import (
    DeliveryConstraintService,
    RedisDeliveryConstraintService,
)
from src.backend.services.hub_api_client import HubApiClient
from src.backend.services.mock_member_profile_store import MockMemberProfileStore
from src.backend.services.scout_audit_service import ScoutAuditService

_ACTIVATION_THRESHOLD = 60.0  # CON-001: strictly > 60 to activate
_CANDIDATE_CAP = 5  # F-005: evaluate at most N offers per request


ConstraintService = Union[DeliveryConstraintService, RedisDeliveryConstraintService]


class ScoutMatchService:
    """Orchestrates the Scout match-activation pipeline for POST /api/scout/match."""

    def __init__(
        self,
        hub_client: HubApiClient,
        scorer: ClaudeContextScoringService,
        constraints: ConstraintService,
        audit: ScoutAuditService,
        member_store: MockMemberProfileStore,
        store_fixtures: CTCStoreFixtures,
    ) -> None:
        self._hub = hub_client
        self._scorer = scorer
        self._constraints = constraints
        self._audit = audit
        self._member_store = member_store
        self._store_fixtures = store_fixtures
        # Shared HTTP client — avoids creating a new connection pool per weather fetch
        self._http_client = httpx.AsyncClient(timeout=2.0)

    async def match(
        self, request: MatchRequest
    ) -> Union[MatchResponse, NoMatchResponse]:
        """Execute the full match pipeline for one purchase event context."""
        # Concurrently enrich context AND fetch active Hub offers (no data dependency)
        context, offers = await asyncio.gather(
            self._enrich_context(request),
            self._hub.get_active_offers(),
        )
        if not offers:
            logger.info("scout.no_active_offers", extra={"member_id": request.member_id})
            return NoMatchResponse(message="No active offers available")
        candidates: list[OfferBrief] = offers[:_CANDIDATE_CAP]

        # Score each candidate and keep the best match.
        best_offer: OfferBrief | None = None
        best_result: ClaudeScoreResult | None = None
        for offer in candidates:
            result = await self._scorer.score(context, offer)
            logger.info(
                "scout.offer_scored",
                extra={
                    "member_id": request.member_id,
                    "offer_id": offer.offer_id,
                    "score": result.score,
                    "method": result.scoring_method.value,
                },
            )
            if best_result is None or result.score > best_result.score:
                best_offer = offer
                best_result = result

        if (
            best_offer is None
            or best_result is None
            or best_result.score <= _ACTIVATION_THRESHOLD
        ):
            return NoMatchResponse(message="No offers scored above activation threshold")

        return await self._dispatch_outcome(request.member_id, best_offer, best_result)

    async def smart_match(self, request: MatchRequest) -> SmartMatchResponse:
        """Route-aware multi-offer match — returns ALL scored offers above threshold.

        Point 5: CTC-store offers are ranked first (priority=1), partner-triggered
        offers second (priority=2). Within each priority group, sorted by score desc.
        This gives members visibility into all relevant nearby offers, not just the top 1.
        """
        context, offers = await asyncio.gather(
            self._enrich_context(request),
            self._hub.get_active_offers(),
        )
        if not offers:
            return SmartMatchResponse(offers=[], total=0, message="No active offers available")

        now = datetime.utcnow()
        member = self._member_store.get(request.member_id)
        member_notifications_enabled = member.notifications_enabled if member else True
        allowed, reason = self._constraints.can_deliver(
            member_id=request.member_id,
            amount=0.0,
            now=now,
            member_notifications_enabled=member_notifications_enabled,
        )

        # Score ALL candidates (not just best) — cap at 2×CANDIDATE_CAP for smart match
        smart_cap = min(len(offers), _CANDIDATE_CAP * 2)
        scored: list[tuple[OfferBrief, ClaudeScoreResult]] = []
        for offer in offers[:smart_cap]:
            result = await self._scorer.score(context, offer)
            if result.score > _ACTIVATION_THRESHOLD:
                scored.append((offer, result))

        if not scored:
            return SmartMatchResponse(offers=[], total=0, message="No offers scored above activation threshold")

        # Rank: CTC-store offers (marketer_initiated / purchase_triggered) = priority 1
        # Partner-triggered offers = priority 2. Within group: sort by score desc.
        from src.backend.models.offer_brief import TriggerType
        smart_items: list[SmartOfferItem] = []
        for offer, result in scored:
            is_partner = offer.trigger_type == TriggerType.partner_triggered
            priority = 2 if is_partner else 1
            outcome = ScoutOutcome.queued if not allowed else ScoutOutcome.activated
            smart_items.append(SmartOfferItem(
                offer_id=offer.offer_id,
                score=result.score,
                notification_text=result.notification_text,
                outcome=outcome,
                trigger_type="partner" if is_partner else "ctc",
                priority=priority,
                scoring_method=result.scoring_method,
                queued=True if outcome == ScoutOutcome.queued else None,
                delivery_time="08:00" if outcome == ScoutOutcome.queued else None,
            ))

        smart_items.sort(key=lambda x: (x.priority, -x.score))

        # Audit only the top-1 offer (avoid audit spam for multi-offer)
        top = smart_items[0]
        top_offer, top_result = next(
            (o, r) for o, r in scored if o.offer_id == top.offer_id
        )
        await self._audit.log_activation(ScoutActivationRecord(
            member_id=request.member_id, offer_id=top.offer_id,
            score=top_result.score, rationale=top_result.rationale,
            scoring_method=top_result.scoring_method, outcome=top.outcome,
        ))

        return SmartMatchResponse(
            offers=smart_items,
            total=len(smart_items),
            message=f"{len(smart_items)} offer(s) matched your route",
        )

    async def _dispatch_outcome(
        self,
        member_id: str,
        offer: OfferBrief,
        score_result: ClaudeScoreResult,
    ) -> MatchResponse:
        """Apply delivery constraints and return the appropriate MatchResponse outcome."""
        now = datetime.utcnow()
        member = self._member_store.get(member_id)
        member_notifications_enabled = member.notifications_enabled if member else True
        allowed, reason = self._constraints.can_deliver(
            member_id=member_id,
            amount=0.0,
            now=now,
            member_notifications_enabled=member_notifications_enabled,
        )

        if not allowed:
            if reason and "Rate limit" in reason:
                retry_after = self._constraints.retry_after_seconds(member_id)
                outcome = ScoutOutcome.rate_limited
                await self._audit.log_activation(ScoutActivationRecord(
                    member_id=member_id, offer_id=offer.offer_id,
                    score=score_result.score, rationale=score_result.rationale,
                    scoring_method=score_result.scoring_method, outcome=outcome,
                ))
                return MatchResponse(
                    score=score_result.score, rationale=score_result.rationale,
                    notification_text=score_result.notification_text, offer_id=offer.offer_id,
                    outcome=outcome, scoring_method=score_result.scoring_method,
                    retry_after_seconds=retry_after,
                )

            # Quiet hours → queue for 8am delivery
            self._constraints.queue_for_morning(member_id, offer.offer_id)
            outcome = ScoutOutcome.queued
            await self._audit.log_activation(ScoutActivationRecord(
                member_id=member_id, offer_id=offer.offer_id,
                score=score_result.score, rationale=score_result.rationale,
                scoring_method=score_result.scoring_method, outcome=outcome,
            ))
            return MatchResponse(
                score=score_result.score, rationale=score_result.rationale,
                notification_text=score_result.notification_text, offer_id=offer.offer_id,
                outcome=outcome, scoring_method=score_result.scoring_method,
                queued=True, delivery_time="08:00",
            )

        # ── Activate ──────────────────────────────────────────────────────────────
        self._constraints.record_delivery(member_id, now=now)
        await self._audit.log_activation(ScoutActivationRecord(
            member_id=member_id, offer_id=offer.offer_id,
            score=score_result.score, rationale=score_result.rationale,
            scoring_method=score_result.scoring_method, outcome=ScoutOutcome.activated,
        ))
        logger.info(
            "scout.offer_activated",
            extra={"member_id": member_id, "offer_id": offer.offer_id, "score": score_result.score},
        )
        return MatchResponse(
            score=score_result.score, rationale=score_result.rationale,
            notification_text=score_result.notification_text, offer_id=offer.offer_id,
            outcome=ScoutOutcome.activated, scoring_method=score_result.scoring_method,
        )

    async def _enrich_context(self, request: MatchRequest) -> EnrichedMatchContext:
        """Concurrently fetch member profile, nearby stores, and weather.

        Uses asyncio.gather with return_exceptions=True so a single enrichment
        failure never blocks the pipeline (REQ-004 graceful degradation).
        """
        member_coro = asyncio.to_thread(self._member_store.get, request.member_id)
        stores_coro = asyncio.to_thread(
            self._store_fixtures.get_nearby,
            request.purchase_location,
        )
        weather_coro = self._fetch_weather(
            request.purchase_location,
            request.weather_condition,
        )

        member_r, stores_r, weather_r = await asyncio.gather(
            member_coro, stores_coro, weather_coro, return_exceptions=True
        )

        absent_signals: list[str] = []

        member: MemberProfile | None = (
            member_r if isinstance(member_r, MemberProfile) else None
        )
        if member is None:
            absent_signals.append("behavioral_profile")

        nearby_stores: list[NearbyStore] = (
            stores_r if isinstance(stores_r, list) else []
        )
        if not nearby_stores:
            absent_signals.append("nearby_stores")

        weather: WeatherConditions | None = (
            weather_r if isinstance(weather_r, WeatherConditions) else None
        )
        if weather is None:
            absent_signals.append("weather")

        return EnrichedMatchContext(
            request=request,
            member=member,
            nearby_stores=nearby_stores,
            weather=weather,
            enrichment_partial=bool(absent_signals),
            absent_signals=absent_signals,
        )

    async def _fetch_weather(
        self,
        location: GeoPoint | None,
        condition_override: str | None,
    ) -> WeatherConditions | None:
        """Return WeatherConditions from request override or live OpenWeatherMap API.

        Returns None (absent signal) when no key, no location, or request fails.
        """
        if condition_override:
            adverse = condition_override.lower() in {
                "snow", "rain", "thunderstorm", "drizzle", "blizzard", "freezing_rain"
            }
            return WeatherConditions(
                condition=condition_override,
                temperature_c=3.0 if adverse else 18.0,
                is_adverse=adverse,
            )

        if not settings.WEATHER_API_KEY or location is None:
            return None

        try:
            resp = await self._http_client.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={
                    "lat": location.lat,
                    "lon": location.lon,
                    "appid": settings.WEATHER_API_KEY,
                    "units": "metric",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            condition = data["weather"][0]["main"].lower()
            temp: float = data["main"]["temp"]
            adverse = condition in {"snow", "rain", "thunderstorm", "drizzle"}
            return WeatherConditions(
                condition=condition,
                temperature_c=temp,
                is_adverse=adverse,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "scout.weather_fetch_failed — absent signal",
                extra={"error": str(exc)},
            )
            return None
