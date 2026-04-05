"""Partner Trigger Service — Haiku classification + Sonnet offer generation for partner purchases.

Pipeline (runs as BackgroundTask — HTTP 202 returned before this executes):
  1. Classify partner purchase context using Claude Haiku (few-shot prompt)
  2. On Haiku failure: use fallback category from _PARTNER_FALLBACK_CATEGORIES
  3. Generate full OfferBrief using Claude Sonnet via claude_api.py
  4. Run fraud check — block if severity == critical
  5. Save to Hub as status=active with valid_until=now+24h

Partners supported at launch: tim_hortons
Architecture designed for extension: add entry to _PARTNER_FALLBACK_CATEGORIES
and _PARTNER_SYSTEM_PROMPTS to support a new partner.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from anthropic import Anthropic
from loguru import logger

from src.backend.core.config import settings
from src.backend.models.offer_brief import (
    Channel,
    ChannelType,
    Construct,
    KPIs,
    OfferBrief,
    OfferStatus,
    PaymentSplit,
    RiskFlags,
    RiskSeverity,
    Segment,
    TriggerType,
)
from src.backend.models.partner_event import PartnerPurchaseEvent
from src.backend.services.canadian_holiday_service import CanadianHolidayService, TimeType
from src.backend.services.ctc_store_fixtures import CTCStoreFixtures
from src.backend.services.fraud_check_service import FraudBlockedError, FraudCheckService
from src.backend.services.hub_api_client import HubApiClient
from src.backend.services.location_zone_service import LocationZone, LocationZoneService

# ─── Partner Configuration ───────────────────────────────────────────────────

# Fallback CTC category per partner + location zone when Haiku classification fails
# Key: (partner_id, LocationZone) → category
_PARTNER_FALLBACK_CATEGORIES: dict[tuple[str, LocationZone], str] = {
    # Tim Hortons by zone
    ("tim_hortons", LocationZone.hill_station): "winter_automotive",
    ("tim_hortons", LocationZone.cottage_lakes): "marine_fishing",
    ("tim_hortons", LocationZone.highway): "automotive_accessories",
    ("tim_hortons", LocationZone.urban): "automotive_cleaning",
    # WestJet by zone
    ("westjet", LocationZone.hill_station): "outdoor_camping",
    ("westjet", LocationZone.cottage_lakes): "travel_accessories",
    ("westjet", LocationZone.highway): "automotive_accessories",
    ("westjet", LocationZone.urban): "luggage",
    # Sport Chek by zone
    ("sport_chek", LocationZone.hill_station): "outdoor_camping",
    ("sport_chek", LocationZone.cottage_lakes): "marine_fishing",
    ("sport_chek", LocationZone.highway): "sporting_goods",
    ("sport_chek", LocationZone.urban): "fitness",
    # Default fallback (any partner, any zone)
    ("default", LocationZone.urban): "seasonal_promotions",
}

# Few-shot system prompts per partner for Haiku classification
_PARTNER_SYSTEM_PROMPTS: dict[str, str] = {
    "tim_hortons": (
        "You classify Canadian Tire cross-sell opportunities from Tim Hortons purchases.\n"
        "Examples:\n"
        "- coffee/beverage purchase at ski resort / mountain → winter_automotive (snow tires, winter gear)\n"
        "- coffee/beverage at hill station → ski_accessories\n"
        "- drive-through coffee (urban) → automotive_cleaning\n"
        "- coffee/beverage purchase (urban) → travel_mugs\n"
        "- food/baked goods purchase → kitchen_storage\n"
        "- large order / group → entertaining_supplies\n"
        "Return ONLY a single CTC product category string, no explanation, no punctuation."
    ),
    "westjet": (
        "You classify Canadian Tire cross-sell opportunities from WestJet flight purchases.\n"
        "Examples:\n"
        "- domestic flight → luggage or car_accessories\n"
        "- international flight → travel_accessories\n"
        "- family booking → outdoor_camping\n"
        "Return ONLY a single CTC product category string, no explanation, no punctuation."
    ),
    "default": (
        "Classify the most relevant Canadian Tire product category for this partner purchase.\n"
        "Return ONLY a single product category string, no explanation."
    ),
}

# Dedup window: ignore same event_id within 60 seconds
_DEDUP_WINDOW_SECONDS = 60
_partner_seen_events: dict[str, datetime] = {}  # Isolated from purchase_event_handler._seen_events


def _is_duplicate_partner_event(event_id: str) -> bool:
    """Check if this partner event_id was seen in the last 60 seconds."""
    cutoff = datetime.utcnow() - timedelta(seconds=_DEDUP_WINDOW_SECONDS)
    stale = [eid for eid, ts in _partner_seen_events.items() if ts < cutoff]
    for eid in stale:
        del _partner_seen_events[eid]

    # Prefix with "partner:" namespace to avoid cross-contamination
    key = f"partner:{event_id}"
    if key in _partner_seen_events:
        return True
    _partner_seen_events[key] = datetime.utcnow()
    return False


class PartnerTriggerService:
    """Classifies partner purchases and generates CTC cross-sell offers."""

    def __init__(
        self,
        hub_client: HubApiClient,
        fraud_service: FraudCheckService,
        location_zone_service: LocationZoneService,
        holiday_service: CanadianHolidayService,
        store_fixtures: Optional[CTCStoreFixtures] = None,
    ) -> None:
        self._hub = hub_client
        self._fraud = fraud_service
        self._location_zone = location_zone_service
        self._holiday = holiday_service
        self._claude = Anthropic(api_key=settings.CLAUDE_API_KEY)
        self._store_fixtures = store_fixtures or CTCStoreFixtures()

    def is_duplicate(self, event_id: str) -> bool:
        """Return True if this event_id was already processed within the dedup window."""
        return _is_duplicate_partner_event(event_id)

    async def classify_and_generate(self, event: PartnerPurchaseEvent) -> Optional[OfferBrief]:
        """Classify partner purchase and generate a CTC offer. Saves to Hub as active.

        Returns the generated OfferBrief, or None if fraud check blocked it.
        Errors are caught and logged — this runs as a BackgroundTask.
        """
        try:
            # Step 0: Classify location zone and time type for contextual intelligence
            location_zone = self._location_zone.classify(event.location, event.store_name)
            time_type = self._holiday.get_time_type(event.timestamp)

            logger.info(
                "Partner event context classified",
                extra={
                    "member_id": event.member_id,
                    "partner_id": event.partner_id,
                    "location_zone": location_zone.value,
                    "time_type": time_type.value,
                },
            )

            # Step 1: Classify with Haiku (now with zone + time context)
            category = await self._classify_with_haiku(event, location_zone, time_type)

            # Step 2: Generate OfferBrief with predictive location + time context
            offer = await self._generate_offer(event, category, location_zone, time_type)

            # Step 3: Fraud check — block if critical
            fraud_result = self._fraud.validate(offer, member_id=event.member_id)
            if fraud_result.severity == RiskSeverity.critical:
                logger.warning(
                    "Partner offer blocked by fraud check",
                    extra={"member_id": event.member_id, "partner_id": event.partner_id,
                           "severity": fraud_result.severity},
                )
                return None

            # Step 4: Save to Hub as active
            await self._hub.save_offer(offer)
            logger.info(
                "Partner-triggered offer saved to Hub",
                extra={"member_id": event.member_id, "offer_id": offer.offer_id,
                       "partner_id": event.partner_id, "category": category},
            )
            return offer

        except Exception as exc:
            logger.error(
                "Partner trigger pipeline failed",
                extra={"member_id": event.member_id, "partner_id": event.partner_id,
                       "error": str(exc)},
            )
            return None

    async def _classify_with_haiku(
        self, event: PartnerPurchaseEvent, location_zone: LocationZone, time_type: TimeType
    ) -> str:
        """Classify partner purchase → CTC product category using Claude Haiku.

        Includes location zone and time type context for contextual intelligence.
        Falls back to _PARTNER_FALLBACK_CATEGORIES on any failure.
        """
        try:
            system_prompt = _PARTNER_SYSTEM_PROMPTS.get(
                event.partner_id, _PARTNER_SYSTEM_PROMPTS["default"]
            )
            # Cap input fields to prevent prompt injection
            safe_category = event.purchase_category[:100]
            safe_partner = event.partner_name[:100]

            # Build contextual message with location zone and time type
            zone_context = {
                LocationZone.hill_station: "Customer is at a mountain/resort location.",
                LocationZone.cottage_lakes: "Customer is at a lake/cottage country location.",
                LocationZone.highway: "Customer is traveling on a major highway corridor.",
                LocationZone.urban: "Customer is in an urban/city center location.",
            }
            time_context = {
                TimeType.long_weekend: "It is a long weekend (stat holiday period).",
                TimeType.weekend: "It is the weekend.",
                TimeType.weekday: "It is a weekday.",
            }

            user_message = (
                f"Partner: {safe_partner}\n"
                f"Purchase category: {safe_category}\n"
                f"Amount: ${event.purchase_amount:.2f}\n"
                f"Location zone: {location_zone.value}\n"
                f"Time type: {time_type.value}\n\n"
                f"Context: {zone_context[location_zone]} {time_context[time_type]}\n\n"
                f"Predict the most relevant Canadian Tire product category for immediate cross-sell.\n"
                f"Consider travel needs, outdoor activities, and seasonal context.\n\n"
                f"Return ONLY a single product category string."
            )

            response = await asyncio.to_thread(
                self._claude.messages.create,
                model="claude-haiku-4-5-20251001",
                max_tokens=50,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            category = response.content[0].text.strip().lower().replace(" ", "_")
            if not category:
                raise ValueError("Empty category from Haiku")
            return category

        except Exception as exc:
            logger.warning(
                "Haiku classification failed, using fallback",
                extra={"partner_id": event.partner_id, "location_zone": location_zone.value, "error": str(exc)},
            )
            return self._fallback_category(event.partner_id, location_zone)

    def _fallback_category(self, partner_id: str, location_zone: LocationZone) -> str:
        """Return fallback CTC category for a partner + zone. Always returns a non-empty string."""
        try:
            # Try partner_id + zone key
            key = (partner_id, location_zone)
            if key in _PARTNER_FALLBACK_CATEGORIES:
                return _PARTNER_FALLBACK_CATEGORIES[key]

            # Fallback to default + urban
            return _PARTNER_FALLBACK_CATEGORIES.get(
                ("default", LocationZone.urban), "seasonal_promotions"
            )
        except Exception:
            return "seasonal_promotions"

    # Approximate marketplace premium over CTC regular price, by category
    _MARKETPLACE_PREMIUM: dict[str, float] = {
        "outdoor_camping": 1.18,
        "camping_gear": 1.18,
        "winter_automotive": 1.16,
        "ski_accessories": 1.22,
        "marine_fishing": 1.15,
        "automotive_accessories": 1.12,
        "automotive_cleaning": 1.10,
        "travel_mugs": 1.20,
        "kitchen_storage": 1.15,
        "entertaining_supplies": 1.12,
        "fitness": 1.15,
        "sporting_goods": 1.14,
        "luggage": 1.20,
        "travel_accessories": 1.18,
        "seasonal_promotions": 1.10,
    }

    def _build_predictive_context(
        self, event: PartnerPurchaseEvent, category: str,
        location_zone: LocationZone, time_type: "TimeType",
    ) -> tuple[str, str, str]:
        """Return (objective, push_message, product_name) enriched with location, store, and payment split."""
        from src.backend.services.canadian_holiday_service import TimeType as TT

        display_category = category.replace("_", " ").title()

        # Single best-fit product per zone (seasonal & location-aware)
        zone_product: dict[LocationZone, str] = {
            LocationZone.hill_station: "Winter Tires",
            LocationZone.cottage_lakes: "Marine Accessories",
            LocationZone.highway: "Car Emergency Kit",
            LocationZone.urban: "Power Drill Kit",
        }
        product_hint = zone_product.get(location_zone, display_category)

        # Time-based urgency copy
        time_copy = {
            TT.long_weekend: "before the long weekend crowds hit",
            TT.weekend: "this weekend",
            TT.weekday: "today",
        }.get(time_type, "today")

        # Marketplace price comparison — no brand names, generic market comparison
        premium_mult = self._MARKETPLACE_PREMIUM.get(category, 1.12)
        ctc_price_note = f"~{int((premium_mult - 1) * 100)}% below market price"

        # Nearest CTC store — expand radius for partner trigger (partner stores may be farther)
        nearby = self._store_fixtures.get_nearby(event.location, radius_km=10.0) if event.location else []
        if nearby:
            nearest = nearby[0]
            store_line = f"Canadian Tire {nearest.store_name} ({nearest.distance_km:.1f}km away)"
        else:
            store_line = "your nearest Canadian Tire"

        # 75/25 Triangle Rewards payment split copy — tied to the specific product offer
        discount_pct = 15  # matches the offer construct value in _generate_offer
        offer_value = event.purchase_amount * (discount_pct / 100)
        max_points_value = offer_value * 0.75
        min_cash_value = offer_value * 0.25
        payment_line = (
            f"Use up to 75% Triangle points (~${max_points_value:.0f} in points), "
            f"pay min 25% by card (~${min_cash_value:.0f})"
        )

        objective = (
            f"Cross-sell {product_hint} to {event.partner_name} customer"
            f" ({location_zone.value.replace('_', ' ')} / {time_type.value.replace('_', ' ')})"
        )
        message = (
            f"You stopped at {event.partner_name}! "
            f"Get 15% off {product_hint} at {store_line} {time_copy} — {ctc_price_note}. "
            f"{payment_line}. Tap to see deal."
        )
        return objective, message, product_hint

    async def _generate_offer(
        self,
        event: PartnerPurchaseEvent,
        category: str,
        location_zone: Optional[LocationZone] = None,
        time_type: Optional["TimeType"] = None,
    ) -> OfferBrief:
        """Generate a full OfferBrief for the predicted CTC category.

        Uses location zone + time type for predictive messaging and marketplace price comparison.
        Builds inline (no extra Claude call) to stay within the 2s background SLA.
        """
        from src.backend.services.canadian_holiday_service import TimeType as TT

        offer_id = str(uuid.uuid4())
        valid_until = datetime.now(timezone.utc) + timedelta(hours=24)
        display_category = category.replace("_", " ").title()

        # Build rich predictive context if zone/time available
        product_name = display_category  # fallback
        if location_zone is not None and time_type is not None:
            objective, push_message, product_name = self._build_predictive_context(
                event, category, location_zone, time_type
            )
        else:
            nearby = self._store_fixtures.get_nearby(event.location, radius_km=10.0) if event.location else []
            store_line = (
                f"Canadian Tire {nearby[0].store_name} ({nearby[0].distance_km:.1f}km away)"
                if nearby else "your nearest Canadian Tire"
            )
            objective = (
                f"Cross-sell Canadian Tire {display_category} to member who just visited "
                f"{event.partner_name}"
            )
            push_message = (
                f"You visited {event.partner_name}! "
                f"Get 15% off {display_category} at {store_line}. "
                f"Use up to 75% Triangle points, pay min 25% by card. Offer valid 24h."
            )

        return OfferBrief(
            offer_id=offer_id,
            objective=objective,
            segment=Segment(
                name="partner_triggered_segment",
                definition=f"Members who made a {event.partner_name} purchase",
                estimated_size=1,
                criteria=[f"partner:{event.partner_id}", f"category:{category}"],
            ),
            construct=Construct(
                type="percentage_off",
                value=15.0,  # Conservative 15% discount — below fraud threshold
                description=f"15% off {product_name} at Canadian Tire",
                payment_split=PaymentSplit(points_max_pct=75.0, cash_min_pct=25.0),
            ),
            channels=[Channel(
                channel_type=ChannelType.push,
                priority=1,
                message_template=push_message,
            )],
            kpis=KPIs(
                expected_redemption_rate=0.08,
                expected_uplift_pct=12.0,
                target_segment_size=1,
            ),
            risk_flags=RiskFlags(
                over_discounting=False,
                cannibalization=False,
                frequency_abuse=False,
                offer_stacking=False,
                severity=RiskSeverity.low,
                warnings=[],
            ),
            status=OfferStatus.active,
            trigger_type=TriggerType.partner_triggered,
            valid_until=valid_until,
        )
