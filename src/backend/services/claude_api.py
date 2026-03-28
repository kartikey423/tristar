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


class ClaudeApiService:
    def __init__(self, api_key: Optional[str] = None) -> None:
        self._client = anthropic.Anthropic(api_key=api_key or settings.CLAUDE_API_KEY)
        self._retry_delays = [1.0, 2.0, 4.0]

    async def _call_with_retry(self, prompt: str) -> str:
        """Call Claude API with exponential backoff. Returns raw response text."""
        last_error: Optional[Exception] = None

        for attempt, delay in enumerate(self._retry_delays, start=1):
            try:
                # Use asyncio.to_thread since anthropic SDK is synchronous
                response = await asyncio.to_thread(
                    self._client.messages.create,
                    model=settings.CLAUDE_MODEL,
                    max_tokens=1500,
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
                logger.error(f"Unexpected Claude API error (attempt {attempt}): {e}")

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
        """Generate OfferBrief from marketer objective. Uses cache with fresh UUID on hit."""
        cached = _get_from_cache(objective)
        if cached is not None:
            # F-001 FIX: Generate a fresh offer_id so each marketer gets a unique identifier.
            # Cache hit reuses the generated content but never shares offer_id between callers.
            fresh_offer = cached.model_copy(update={"offer_id": str(uuid.uuid4())})
            logger.debug(f"Cache hit for objective (fresh UUID assigned): {objective[:60]}")
            return fresh_offer

        hints_section = ""
        if segment_hints:
            hints_section = f"\nSegment hints to consider: {', '.join(segment_hints)}"

        prompt = _MARKETER_PROMPT.format(
            objective=objective,
            segment_hints_section=hints_section,
        )

        raw = await self._call_with_retry(prompt)
        offer = self._parse_offer_brief(raw, TriggerType.marketer_initiated)

        # Override offer_id with a fresh UUID (Claude may generate non-UUID strings)
        offer = offer.model_copy(update={"offer_id": str(uuid.uuid4())})
        _store_in_cache(objective, offer)

        logger.info("Generated OfferBrief from objective", extra={"offer_id": offer.offer_id})
        return offer

    async def generate_from_purchase_context(self, ctx: PurchaseContextRequest) -> OfferBrief:
        """Generate a purchase-triggered OfferBrief from enriched purchase context."""
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

        raw = await self._call_with_retry(prompt)
        offer = self._parse_offer_brief(raw, TriggerType.purchase_triggered)

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
