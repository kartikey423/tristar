"""Claude AI context scoring service for Scout match activation.

Design Review F-001 fix: Uses anthropic SDK directly via asyncio.to_thread() with
asyncio.wait_for(timeout=3.0) — single attempt only. Does NOT use ClaudeApiService
(which has a 3x retry loop totalling 7s, incompatible with the 3s Scout budget).

Fallback: existing ContextScoringService (deterministic 7-factor formula) fires on:
  - asyncio.TimeoutError (Claude >3s)
  - Any anthropic SDK exception
  - JSON parse failure in response

Context hash for P2 cache (REQ-009 / AC-026):
  SHA256(offer_id + ":" + purchase_category + ":" + hour_bucket + ":" + weather_condition)
  hour_bucket = str(hour // 3 * 3)  — 3-hour buckets to reduce cache misses
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import anthropic
from loguru import logger

from src.backend.core.config import settings
from src.backend.models.offer_brief import OfferBrief
from src.backend.models.scout_match import EnrichedMatchContext, ScoringMethod
from src.backend.services.context_scoring_service import ContextScoringService

_SCOUT_ACTIVATION_THRESHOLD = 60.0  # CON-001: strictly > 60


@dataclass
class ClaudeScoreResult:
    score: float
    rationale: str
    notification_text: str
    scoring_method: ScoringMethod


_SCORING_PROMPT_TEMPLATE = """\
You are the TriStar Scout activation engine for Triangle (Canadian Tire loyalty program).
Score how well this CTC offer matches the member's current context.

Return ONLY valid JSON with exactly these three fields — no explanation:
{{"score": <0-100>, "rationale": "<2-3 sentences>", "notification_text": "<push notification copy>"}}

## Context Signals
- Purchase just made: {purchase_category} at {store_name} (+{rewards_earned} Triangle points)
- Day context: {day_context}
- Time: {hour}:00 UTC
- Member ID: {member_id} (use to personalise — different members must get different notifications)
{member_section}
{weather_section}
{location_section}

## Candidate Offer
- Offer ID: {offer_id}
- Description: {offer_description}
- Value: {construct_type} — {construct_value}
- Target segment: {segment_name}
- Payment rule: max {points_max_pct:.0f}% Triangle points, min {cash_min_pct:.0f}% card payment

## Scoring Criteria (0-100)
Score based on: relevance to predicted next destination, contextual fit with the purchase,
member behavioral alignment, timing appropriateness.
Score EXACTLY 60 or below = NOT activated. Score 61+ = activated.

## Notification Text Rules
1. ALWAYS mention Triangle Rewards payment split: "Use up to {points_max_pct:.0f}% Triangle points, pay min {cash_min_pct:.0f}% by card"
2. Include the nearest CTC store name and distance (from location section above)
3. Personalise to the member's purchase category and loyalty tier — every member gets unique text
4. Format: "[Rewards hook] — [Offer] at [Store], [Distance]. Use up to {points_max_pct:.0f}% Triangle points, pay min {cash_min_pct:.0f}% by card."
Example: "You earned 120 pts at Tim Hortons — 20% off Wiper Blades at Canadian Tire 400m away. Use up to 75% Triangle points, pay min 25% by card."
"""


class ClaudeContextScoringService:
    """Primary Scout scoring engine using Claude AI.

    Falls back to ContextScoringService on timeout, API error, or parse failure.
    """

    def __init__(self, fallback: Optional[ContextScoringService] = None) -> None:
        self._anthropic = anthropic.Anthropic(api_key=settings.CLAUDE_API_KEY)
        self._fallback = fallback or ContextScoringService()
        # In-process P2 cache: context_hash → (ClaudeScoreResult, expires_at)
        self._cache: dict[str, tuple[ClaudeScoreResult, datetime]] = {}

    def _context_hash(self, context: EnrichedMatchContext, offer: OfferBrief) -> str:
        """Compute cache key for (member, offer, context) combination.

        Includes member_id and loyalty_tier so different members always get
        different personalised notifications (Point 4 — per-member uniqueness).
        """
        hour_bucket = str((datetime.now(timezone.utc).hour // 3) * 3)
        weather = context.weather.condition if context.weather else "none"
        member_id = context.request.member_id
        tier = context.member.loyalty_tier if context.member else "unknown"
        raw = f"{member_id}:{tier}:{offer.offer_id}:{context.request.purchase_category}:{hour_bucket}:{weather}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _get_cached(self, context_hash: str) -> Optional[ClaudeScoreResult]:
        entry = self._cache.get(context_hash)
        if entry is None:
            return None
        result, expires_at = entry
        if datetime.now(timezone.utc) > expires_at:
            del self._cache[context_hash]
            return None
        return result

    def _store_cache(self, context_hash: str, result: ClaudeScoreResult) -> None:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.CACHE_TTL_SECONDS)
        # Evict oldest if over 200 entries
        if len(self._cache) >= 200:
            oldest = next(iter(self._cache))
            del self._cache[oldest]
        self._cache[context_hash] = (result, expires_at)

    def _build_prompt(self, context: EnrichedMatchContext, offer: OfferBrief) -> str:
        req = context.request

        # Member section — omit entirely if no behavioral data (AC-013)
        if context.member:
            member_section = (
                f"- Member behavioral profile: prefers {', '.join(context.member.preferred_categories)}, "
                f"{context.member.purchase_count_90_days} CTC purchases in 90 days, "
                f"loyalty tier: {context.member.loyalty_tier}"
            )
        else:
            member_section = "- Member behavioral profile: no behavioral data available — score on location/time/weather only"

        # Weather section — omit if absent (AC-012), note reduced confidence
        if context.weather:
            weather_section = (
                f"- Weather: {context.weather.condition} ({context.weather.temperature_c:.0f}°C)"
            )
        else:
            weather_section = "- Weather: signal unavailable — note reduced confidence in weather-based scoring"

        # Location section
        if context.nearby_stores:
            nearest = context.nearby_stores[0]
            location_section = f"- Nearest CTC store: {nearest.store_name} ({nearest.distance_km:.2f}km away)"
        else:
            location_section = "- Nearest CTC store: none within 2km of purchase location"

        now = datetime.now(timezone.utc)
        # Payment split — default to 75/25 if not set on the offer
        ps = offer.construct.payment_split
        points_max_pct = ps.points_max_pct if ps else 75.0
        cash_min_pct = ps.cash_min_pct if ps else 25.0

        return _SCORING_PROMPT_TEMPLATE.format(
            purchase_category=req.purchase_category,
            store_name="partner store",  # store name not in MatchRequest — generic
            rewards_earned=req.rewards_earned,
            day_context=req.day_context.value,
            hour=now.hour,
            member_id=req.member_id,
            member_section=member_section,
            weather_section=weather_section,
            location_section=location_section,
            offer_id=offer.offer_id,
            offer_description=offer.construct.description,
            construct_type=offer.construct.type,
            construct_value=offer.construct.value,
            segment_name=offer.segment.name,
            points_max_pct=points_max_pct,
            cash_min_pct=cash_min_pct,
        )

    def _parse_response(self, text: str) -> tuple[float, str, str]:
        """Parse Claude response JSON → (score, rationale, notification_text).

        Returns (0.0, error_message, "") on any parse failure.
        """
        try:
            data = json.loads(text.strip())
            score = float(data["score"])
            rationale = str(data["rationale"])
            notification_text = str(data.get("notification_text", ""))
            score = max(0.0, min(100.0, score))
            return score, rationale, notification_text
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            logger.warning(f"claude_response_parse_failed: {e!r}")
            return 0.0, f"Parse error: {e!r}", ""

    def _deterministic_fallback(
        self, context: EnrichedMatchContext, offer: OfferBrief
    ) -> ClaudeScoreResult:
        """Fallback to deterministic ContextScoringService. Adapts EnrichedMatchContext."""
        from src.backend.models.purchase_event import EnrichedContext, GeoPoint, PurchaseEventPayload

        # Build a minimal EnrichedContext from the match request
        loc = context.request.purchase_location or GeoPoint(lat=0.0, lon=0.0)
        minimal_event = PurchaseEventPayload(
            event_id="fallback",
            member_id=context.request.member_id,
            store_id="unknown",
            store_name="unknown",
            store_type="partner",
            amount=0.01,  # PurchaseEventPayload requires amount > 0
            location=loc,
            category=context.request.purchase_category,
            timestamp=datetime.utcnow(),
        )
        enriched = EnrichedContext(
            event=minimal_event,
            member=context.member,
            nearby_stores=context.nearby_stores,
            weather=context.weather,
        )
        result = self._fallback.score(enriched)
        rationale = (
            f"Deterministic fallback scoring (Claude unavailable). "
            f"Score breakdown: {result.breakdown}"
        )
        # Build a meaningful fallback notification with 75/25 payment split details
        ps = offer.construct.payment_split
        points_max = ps.points_max_pct if ps else 75.0
        cash_min = ps.cash_min_pct if ps else 25.0
        store_hint = (
            f"at {context.nearby_stores[0].store_name} ({context.nearby_stores[0].distance_km:.1f}km away)"
            if context.nearby_stores else "at your nearest Canadian Tire"
        )
        fallback_notification = (
            f"{offer.construct.description} {store_hint}. "
            f"Use up to {points_max:.0f}% Triangle points, pay min {cash_min:.0f}% by card. "
            f"Limited time offer."
        )
        return ClaudeScoreResult(
            score=result.total,
            rationale=rationale,
            notification_text=fallback_notification,
            scoring_method=ScoringMethod.fallback,
        )

    async def score(
        self, context: EnrichedMatchContext, offer: OfferBrief
    ) -> ClaudeScoreResult:
        """Score offer against context. Primary: Claude AI. Fallback: deterministic."""

        # P2: check cache first (REQ-009 / AC-026)
        ctx_hash = self._context_hash(context, offer)
        cached = self._get_cached(ctx_hash)
        if cached is not None:
            logger.info(
                "scout.score_cache_hit",
                extra={"offer_id": offer.offer_id, "scoring_method": "cached"},
            )
            return ClaudeScoreResult(
                score=cached.score,
                rationale=cached.rationale,
                notification_text=cached.notification_text,
                scoring_method=ScoringMethod.cached,
            )

        if not settings.CLAUDE_API_KEY:
            logger.warning("CLAUDE_API_KEY not set — using deterministic fallback")
            return self._deterministic_fallback(context, offer)

        prompt = self._build_prompt(context, offer)
        try:
            # Design Review F-001: single attempt, 3s timeout, NO retry loop
            raw_response = await asyncio.wait_for(
                asyncio.to_thread(
                    self._anthropic.messages.create,
                    model=settings.CLAUDE_MODEL,
                    max_tokens=800,
                    messages=[{"role": "user", "content": prompt}],
                ),
                timeout=3.0,
            )
            text = raw_response.content[0].text
            score, rationale, notification_text = self._parse_response(text)

            if score == 0.0 and "Parse error" in rationale:
                # Parse failed — fall back
                return self._deterministic_fallback(context, offer)

            result = ClaudeScoreResult(
                score=score,
                rationale=rationale,
                notification_text=notification_text,
                scoring_method=ScoringMethod.claude,
            )
            self._store_cache(ctx_hash, result)
            logger.info(
                "scout.score_claude",
                extra={"offer_id": offer.offer_id, "score": score},
            )
            return result

        except asyncio.TimeoutError:
            logger.warning(
                "scout.claude_timeout",
                extra={"offer_id": offer.offer_id, "timeout_s": 3.0},
            )
            return self._deterministic_fallback(context, offer)
        except Exception as e:
            logger.warning(
                "scout.claude_error",
                extra={"offer_id": offer.offer_id, "error": str(e)},
            )
            return self._deterministic_fallback(context, offer)
