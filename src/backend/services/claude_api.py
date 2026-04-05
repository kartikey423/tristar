"""Claude API client for OfferBrief generation.

Features:
- 3× retry with exponential backoff (1s → 2s → 4s)
- 5-minute TTL in-process cache keyed on SHA-256(lowercase objective)
- F-001 FIX: On cache hit, generates a fresh UUID4 for offer_id to prevent
  Hub 409 Conflict when multiple marketers approve the same cached offer
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from datetime import datetime, timedelta
from typing import Optional

import anthropic
from loguru import logger

from src.backend.core.config import settings
from src.backend.models.offer_brief import (
    Channel,
    Construct,
    KPIs,
    OfferBrief,
    RiskFlags,
    RiskSeverity,
    Segment,
    TriggerType,
)
from src.backend.models.purchase_event import PurchaseContextRequest

# ─── Custom Exceptions ────────────────────────────────────────────────────────


class ClaudeApiError(Exception):
    """Raised when Claude API fails after all retries."""

    pass


class ClaudeResponseParseError(Exception):
    """Raised when Claude response cannot be parsed into OfferBrief."""

    pass


# ─── In-process cache ─────────────────────────────────────────────────────────

_CACHE_MAX_SIZE = 500  # maximum number of cached objectives
_cache: dict[str, tuple[OfferBrief, datetime]] = {}  # key → (offer, expires_at)


def _cache_key(objective: str) -> str:
    return hashlib.sha256(objective.lower().strip().encode()).hexdigest()


def _get_from_cache(objective: str) -> Optional[OfferBrief]:
    key = _cache_key(objective)
    entry = _cache.get(key)
    if entry is None:
        return None
    offer, expires_at = entry
    if datetime.utcnow() > expires_at:
        del _cache[key]
        return None
    return offer


def _store_in_cache(objective: str, offer: OfferBrief) -> None:
    key = _cache_key(objective)
    # Evict oldest entry if cache is at capacity (prevents unbounded growth)
    if len(_cache) >= _CACHE_MAX_SIZE and key not in _cache:
        oldest_key = next(iter(_cache))
        del _cache[oldest_key]
    expires_at = datetime.utcnow() + timedelta(seconds=settings.CACHE_TTL_SECONDS)
    _cache[key] = (offer, expires_at)


# ─── System Context for Prompt Caching ───────────────────────────────────────

_SYSTEM_CONTEXT = """You are a loyalty marketing expert for Triangle (Canadian Tire's loyalty program).

Triangle Rewards is Canadian Tire Corporation's loyalty program with 13M+ active members.
Partner brands: Canadian Tire, Sport Chek, Mark's Work Wearhouse, PartSource, Atmosphere.
Currency: Canadian dollars (CAD). Points redemption: 1000 points = $1 CAD.

Offer Types:
- discount: Percentage or fixed amount off (e.g., "20% off winter tires")
- points_multiplier: Bonus points earning rate (e.g., "5× points on automotive")
- bonus_points: Fixed points bonus (e.g., "1000 bonus points on $50+ purchase")
- free_item: Free product with qualifying purchase

Member Segments:
- high_value_members: Top 15% by annual spend
- lapsed_high_value: Previously active, no purchase in 90+ days
- active_triangle_members: At least 1 purchase in last 60 days
- seasonal_buyers: Category-specific purchase patterns
- senior_loyalists: Age 55+, tenure 5+ years

Risk Factors:
- over_discounting: Discount >25% (margin risk)
- cannibalization: May reduce full-price sales
- frequency_abuse: Member may exploit offer repeatedly
- offer_stacking: Can be combined with other promotions

CRITICAL: All JSON responses must be valid, parseable JSON objects."""

# ─── Prompts ──────────────────────────────────────────────────────────────────

_MARKETER_PROMPT = """You are a loyalty marketing expert for Triangle (Canadian Tire's loyalty program).

Generate a structured OfferBrief JSON for the following marketing objective:
"{objective}"
{segment_hints_section}

The OfferBrief MUST be a valid JSON object with these exact fields:
{{
  "offer_id": "<uuid-v4>",
  "objective": "<the given objective>",
  "segment": {{
    "name": "<segment name>",
    "definition": "<1-2 sentence definition>",
    "estimated_size": <integer>,
    "criteria": ["<criterion1>", "<criterion2>"]
  }},
  "construct": {{
    "type": "<discount|points_multiplier|bonus_points|free_item>",
    "value": <number>,
    "description": "<human-readable description>"
  }},
  "channels": [
    {{"channel_type": "<push|email|sms|in_app>", "priority": <1-3>}}
  ],
  "kpis": {{
    "expected_redemption_rate": <0.0-1.0>,
    "expected_uplift_pct": <number>
  }},
  "risk_flags": {{
    "over_discounting": <true|false>,
    "cannibalization": <true|false>,
    "frequency_abuse": <true|false>,
    "offer_stacking": <true|false>,
    "severity": "<low|medium|critical>",
    "warnings": ["<warning text if any>"]
  }},
  "status": "draft",
  "trigger_type": "marketer_initiated",
  "created_at": "<ISO 8601 timestamp>"
}}

Return ONLY the JSON object, no explanation."""

_PURCHASE_PROMPT = """You are a real-time loyalty marketing engine for Triangle (Canadian Tire).

A customer just made a purchase and we need to generate a personalized offer immediately.

Purchase Context:
- Member ID: {member_id}
- Store: {store_name}{partner_brand_line}
- Purchase Amount: ${purchase_amount:.2f} CAD
- Member Segment: {member_segment}
- Context Score: {context_score:.1f}/100
- Nearby CTC Stores: {nearby_stores}
- Weather: {weather}

Generate a highly personalized OfferBrief that capitalizes on the customer's active
purchasing mindset. The offer should:
1. Be relevant to the purchase context and nearby stores
2. Provide urgency (valid for 4 hours only)
3. Drive the customer toward a nearby Canadian Tire store
4. Have construct.value ≤ 25% (avoid over-discounting)

Return the same JSON structure as the standard OfferBrief but with:
- status: "active" (auto-activated, no marketer approval needed)
- trigger_type: "purchase_triggered"
- valid_until: ISO 8601 timestamp 4 hours from now

Return ONLY the JSON object, no explanation."""


# ─── Claude API Service ───────────────────────────────────────────────────────


def _build_mock_offer(objective: str, trigger_type: TriggerType) -> OfferBrief:
    """Deterministic fallback offer generation when Claude API key is not configured.

    Parses keywords from the objective to produce a realistic OfferBrief without
    calling the Claude API.  Mirrors the deterministic fallback pattern used in
    ClaudeContextScoringService.
    """
    obj_lower = objective.lower()

    # Infer segment from objective keywords
    if "lapsed" in obj_lower:
        segment_name = "lapsed_high_value"
        segment_def = "Members who were active in the past 12 months but have not purchased in 90+ days."
        criteria = ["lapsed_90_days", "previously_high_value"]
        estimated_size = 18_500
    elif "high value" in obj_lower or "vip" in obj_lower or "premium" in obj_lower:
        segment_name = "high_value_members"
        segment_def = "Top 15% of Triangle Rewards members by annual spend."
        criteria = ["annual_spend_top_15pct", "active_last_60_days"]
        estimated_size = 42_000
    elif "senior" in obj_lower or "mature" in obj_lower or "older" in obj_lower:
        segment_name = "senior_loyalists"
        segment_def = "Members aged 55+ with 5+ years on the Triangle program."
        criteria = ["age_55_plus", "tenure_5y_plus", "seasonal_category_buyer"]
        estimated_size = 31_200
    elif "winter" in obj_lower or "snow" in obj_lower or "clearance" in obj_lower:
        segment_name = "seasonal_clearance_shoppers"
        segment_def = "Members who regularly purchase seasonal and home-care categories."
        criteria = ["seasonal_buyer", "active_last_30_days", "proximity_under_5km"]
        estimated_size = 55_000
    else:
        segment_name = "active_triangle_members"
        segment_def = "Triangle Rewards members with at least one purchase in the last 60 days."
        criteria = ["active_last_60_days", "opted_in_push"]
        estimated_size = 120_000

    # Infer construct from objective keywords
    if "points" in obj_lower or "multiplier" in obj_lower or "earn" in obj_lower:
        construct_type = "points_multiplier"
        construct_value = 5.0
        construct_desc = "5× Triangle Points on eligible purchases this weekend"
    elif "discount" in obj_lower or "off" in obj_lower or "clearance" in obj_lower or "%" in obj_lower:
        construct_type = "discount"
        construct_value = 20.0
        construct_desc = "20% off selected items in-store and online"
    elif "bonus" in obj_lower:
        construct_type = "bonus_points"
        construct_value = 1000.0
        construct_desc = "Earn 1,000 bonus Triangle Points on your next eligible purchase"
    else:
        construct_type = "points_multiplier"
        construct_value = 3.0
        construct_desc = "3× Triangle Points on your next visit"

    # Default channels
    channels = [
        Channel(channel_type="push", priority=1),
        Channel(channel_type="email", priority=2),
    ]

    now = datetime.utcnow()
    valid_until = now + timedelta(hours=settings.OFFER_VALID_UNTIL_HOURS if trigger_type == TriggerType.purchase_triggered else 168)

    return OfferBrief(
        offer_id=str(uuid.uuid4()),
        objective=objective,
        segment=Segment(
            name=segment_name,
            definition=segment_def,
            estimated_size=estimated_size,
            criteria=criteria,
        ),
        construct=Construct(
            type=construct_type,
            value=construct_value,
            description=construct_desc,
        ),
        channels=channels,
        kpis=KPIs(expected_redemption_rate=0.14, expected_uplift_pct=22.0),
        risk_flags=RiskFlags(
            over_discounting=construct_value > 25,
            cannibalization=False,
            frequency_abuse=False,
            offer_stacking=False,
            severity=RiskSeverity.low,
            warnings=[] if construct_value <= 25 else ["Discount exceeds 25% threshold — verify margin impact"],
        ),
        status="draft" if trigger_type == TriggerType.marketer_initiated else "active",
        trigger_type=trigger_type,
        created_at=now,
        valid_until=valid_until,
    )


class ClaudeApiService:
    def __init__(self, api_key: Optional[str] = None) -> None:
        resolved_key = api_key or settings.CLAUDE_API_KEY
        self._api_key_present = bool(resolved_key and resolved_key.strip())
        self._client = anthropic.Anthropic(api_key=resolved_key) if self._api_key_present else None
        self._retry_delays = [1.0, 2.0, 4.0]

    def _select_model(self, prompt: str) -> str:
        """Select cost-efficient model based on task complexity.

        Intelligence Strategy:
        - Haiku ($0.25/M tokens): Classification, scoring, simple extraction
        - Sonnet ($3/M tokens): Offer generation, complex reasoning
        - NO Opus: Exceeds cost budget
        """
        prompt_lower = prompt.lower()

        # Use Haiku for classification/scoring tasks
        if any(keyword in prompt_lower for keyword in ["score", "classify", "match", "evaluate", "rate"]):
            return settings.CLAUDE_MODEL_HAIKU

        # Use Sonnet for generation tasks
        return settings.CLAUDE_MODEL_DEFAULT

    async def _call_with_retry(self, prompt: str) -> str:
        """Call Claude API with exponential backoff. Returns raw response text."""
        if not self._api_key_present or self._client is None:
            raise ClaudeApiError(
                "Claude API key not configured — using deterministic fallback"
            )

        last_error: Optional[Exception] = None

        for attempt, delay in enumerate(self._retry_delays, start=1):
            try:
                # Use asyncio.to_thread since anthropic SDK is synchronous
                # Prompt caching: Cache system context for 5 minutes (90% cost reduction on hits)
                response = await asyncio.to_thread(
                    self._client.messages.create,
                    model=self._select_model(prompt),
                    max_tokens=1500,
                    system=[
                        {
                            "type": "text",
                            "text": _SYSTEM_CONTEXT,
                            "cache_control": {"type": "ephemeral"} if settings.USE_PROMPT_CACHING else None,
                        }
                    ] if settings.USE_PROMPT_CACHING else _SYSTEM_CONTEXT,
                    messages=[{"role": "user", "content": prompt}],
                )
                return response.content[0].text
            except anthropic.RateLimitError as e:
                last_error = e
                logger.warning(
                    f"Claude API rate limited (attempt {attempt}/{len(self._retry_delays)}), "
                    f"retrying in {delay}s"
                )
            except anthropic.APIStatusError as e:
                last_error = e
                logger.warning(
                    f"Claude API error {e.status_code} (attempt {attempt}/{len(self._retry_delays)}), "
                    f"retrying in {delay}s"
                )
            except Exception as e:
                last_error = e
                logger.error("Unexpected Claude API error (attempt {}): {}", attempt, str(e)[:200])

            if attempt < len(self._retry_delays):
                await asyncio.sleep(delay)

        raise ClaudeApiError(
            f"Claude API failed after {len(self._retry_delays)} attempts: {last_error}"
        )

    def _parse_offer_brief(self, raw: str, trigger_type: TriggerType) -> OfferBrief:
        """Parse Claude's JSON response into an OfferBrief model."""
        try:
            # Extract JSON block if Claude wraps it in markdown
            text = raw.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(
                    line for line in lines if not line.startswith("```")
                )

            data = json.loads(text)
            # Ensure trigger_type matches expected value
            data["trigger_type"] = trigger_type.value
            return OfferBrief(**data)
        except (json.JSONDecodeError, ValueError) as e:
            raise ClaudeResponseParseError(
                f"Failed to parse Claude response into OfferBrief: {e}\nRaw: {raw[:500]}"
            )

    async def generate_from_objective(
        self,
        objective: str,
        segment_hints: Optional[list[str]] = None,
    ) -> OfferBrief:
        """Generate OfferBrief from marketer objective. Uses cache with fresh UUID on hit.

        Falls back to deterministic mock generation when CLAUDE_API_KEY is not set,
        so the Designer always produces a result regardless of API key availability.
        """
        cached = _get_from_cache(objective)
        if cached is not None:
            # F-001 FIX: Generate a fresh offer_id so each marketer gets a unique identifier.
            fresh_offer = cached.model_copy(update={"offer_id": str(uuid.uuid4())})
            logger.debug(f"Cache hit for objective (fresh UUID assigned): {objective[:60]}")
            return fresh_offer

        # Fast path: no API key → use deterministic fallback immediately (no retries)
        if not self._api_key_present:
            logger.info(
                "Claude API key not set — using deterministic fallback for offer generation",
                extra={"objective": objective[:80]},
            )
            offer = _build_mock_offer(objective, TriggerType.marketer_initiated)
            _store_in_cache(objective, offer)
            return offer

        hints_section = ""
        if segment_hints:
            hints_section = f"\nSegment hints to consider: {', '.join(segment_hints)}"

        prompt = _MARKETER_PROMPT.format(
            objective=objective,
            segment_hints_section=hints_section,
        )

        try:
            raw = await self._call_with_retry(prompt)
            offer = self._parse_offer_brief(raw, TriggerType.marketer_initiated)
        except (ClaudeApiError, ClaudeResponseParseError) as e:
            logger.warning(
                "Claude API unavailable, falling back to deterministic generation: {}",
                str(e)[:200],
                extra={"objective": objective[:80]},
            )
            offer = _build_mock_offer(objective, TriggerType.marketer_initiated)

        # Override offer_id with a fresh UUID
        offer = offer.model_copy(update={"offer_id": str(uuid.uuid4())})
        _store_in_cache(objective, offer)

        logger.info("Generated OfferBrief from objective", extra={"offer_id": offer.offer_id})
        return offer

    async def generate_from_purchase_context(self, ctx: PurchaseContextRequest) -> OfferBrief:
        """Generate a purchase-triggered OfferBrief from enriched purchase context."""
        # Fast path: no API key → use deterministic fallback immediately
        if not self._api_key_present:
            logger.info(
                "Claude API key not set — using deterministic fallback for purchase context",
                extra={"member_id": ctx.member_id},
            )
            objective = f"Personalized offer for {ctx.member_segment} member at {ctx.store_name}"
            offer = _build_mock_offer(objective, TriggerType.purchase_triggered)
            valid_until = datetime.utcnow() + timedelta(hours=settings.OFFER_VALID_UNTIL_HOURS)
            return offer.model_copy(update={"offer_id": str(uuid.uuid4()), "valid_until": valid_until})

        partner_brand_line = (
            f" (partner: {ctx.partner_brand})" if ctx.partner_brand else ""
        )
        nearby = ", ".join(ctx.nearby_ctc_stores[:3]) if ctx.nearby_ctc_stores else "none nearby"
        weather = ctx.weather_condition or "unknown"

        prompt = _PURCHASE_PROMPT.format(
            member_id=ctx.member_id,
            store_name=ctx.store_name,
            partner_brand_line=partner_brand_line,
            purchase_amount=ctx.purchase_amount,
            member_segment=ctx.member_segment,
            context_score=ctx.context_score,
            nearby_stores=nearby,
            weather=weather,
        )

        try:
            raw = await self._call_with_retry(prompt)
            offer = self._parse_offer_brief(raw, TriggerType.purchase_triggered)
        except (ClaudeApiError, ClaudeResponseParseError) as e:
            logger.warning("Claude API unavailable for purchase context, using fallback: {}", str(e)[:200])
            objective = f"Personalized offer for {ctx.member_segment} member at {ctx.store_name}"
            offer = _build_mock_offer(objective, TriggerType.purchase_triggered)

        # Ensure fresh UUID and correct metadata for purchase-triggered offers
        valid_until = datetime.utcnow() + timedelta(hours=settings.OFFER_VALID_UNTIL_HOURS)
        offer = offer.model_copy(
            update={
                "offer_id": str(uuid.uuid4()),
                "status": "active",
                "trigger_type": TriggerType.purchase_triggered,
                "valid_until": valid_until,
            }
        )

        logger.info(
            "Generated purchase-triggered OfferBrief",
            extra={"offer_id": offer.offer_id, "member_id": ctx.member_id},
        )
        return offer
