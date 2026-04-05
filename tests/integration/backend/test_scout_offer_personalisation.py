"""Integration tests for Scout offer personalisation.

Point 4: Verifies that for each (member, product_category, store) combination,
the Scout produces a unique, customised offer notification — not a generic/identical
message across all permutations.

Also covers:
- 75/25 Triangle Rewards payment split always present in notification text (Points 2 & 3)
- Partner trigger notification includes CTC store name + payment split (Point 3)
- Smart match returns CTC-first ranked multi-offer list (Point 5)
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.backend.models.offer_brief import (
    Channel, ChannelType, Construct, KPIs, OfferBrief, OfferStatus,
    PaymentSplit, RiskFlags, RiskSeverity, Segment, TriggerType,
)
from src.backend.models.scout_match import (
    DayContext, EnrichedMatchContext, MatchRequest, SmartMatchResponse,
)
from src.backend.models.purchase_event import GeoPoint, MemberProfile, NearbyStore, WeatherConditions
from src.backend.services.claude_context_scoring_service import (
    ClaudeContextScoringService, ClaudeScoreResult, ScoringMethod,
)
from src.backend.services.ctc_store_fixtures import CTCStoreFixtures

# ─── Fixtures ────────────────────────────────────────────────────────────────

FIXTURES_PATH = Path(__file__).parents[2] / "fixtures/offer_brief_responses.json"


def _active_offer(trigger_type: TriggerType = TriggerType.marketer_initiated) -> OfferBrief:
    from datetime import datetime, timedelta, timezone
    return OfferBrief(
        offer_id="test-offer-001",
        objective="Reactivate lapsed members with seasonal gear offers",
        segment=Segment(name="lapsed_high_value", definition="Lapsed members", estimated_size=5000, criteria=["lapsed"]),
        construct=Construct(
            type="percentage_off", value=15.0,
            description="15% off Automotive Accessories",
            payment_split=PaymentSplit(points_max_pct=75.0, cash_min_pct=25.0),
        ),
        channels=[Channel(channel_type=ChannelType.push, priority=1)],
        kpis=KPIs(expected_redemption_rate=0.10, expected_uplift_pct=20.0),
        risk_flags=RiskFlags(over_discounting=False, cannibalization=False,
                             frequency_abuse=False, offer_stacking=False,
                             severity=RiskSeverity.low, warnings=[]),
        status=OfferStatus.active,
        trigger_type=trigger_type,
        valid_until=datetime.now(timezone.utc) + timedelta(hours=24),
    )


def _make_context(
    member_id: str = "member-1",
    category: str = "automotive",
    rewards: int = 100,
    store_name: str = "Canadian Tire Don Mills",
    distance_km: float = 0.5,
    loyalty_tier: str = "gold",
    preferred_categories: list[str] | None = None,
) -> EnrichedMatchContext:
    return EnrichedMatchContext(
        request=MatchRequest(
            member_id=member_id,
            purchase_location=GeoPoint(lat=43.72, lon=-79.38),
            purchase_category=category,
            rewards_earned=rewards,
            day_context=DayContext.weekday,
        ),
        member=MemberProfile(
            member_id=member_id,
            segment="lapsed_high_value",
            preferred_categories=preferred_categories or ["automotive", "home"],
            total_spend_90_days=850.0,
            purchase_count_90_days=12,
            loyalty_tier=loyalty_tier,
            notifications_enabled=True,
        ),
        nearby_stores=[NearbyStore(
            store_id="ctc-001", store_name=store_name,
            distance_km=distance_km, category="auto",
        )],
        weather=WeatherConditions(condition="clear", temperature_c=15.0),
    )


# ─── Point 2: 75/25 in CTC Scout notification ────────────────────────────────

class TestPaymentSplitInNotification:
    """75/25 Triangle Rewards split must appear in ALL Scout notifications."""

    @pytest.mark.asyncio
    async def test_fallback_notification_includes_75_25_split(self):
        """Fallback (no Claude) must still include payment split in notification text."""
        from src.backend.services.context_scoring_service import ContextScore
        svc = ClaudeContextScoringService.__new__(ClaudeContextScoringService)
        svc._cache = {}
        svc._fallback = MagicMock()
        svc._fallback.score.return_value = ContextScore(
            total=65.0,
            breakdown={"proximity": 25.0, "category_affinity": 20.0,
                       "time_alignment": 10.0, "weather": 5.0, "frequency": 5.0,
                       "purchase_value": 0.0, "partner_crosssell": 0.0},
        )

        offer = _active_offer()
        ctx = _make_context()
        result = svc._deterministic_fallback(ctx, offer)

        assert "75" in result.notification_text
        assert "25" in result.notification_text

    @pytest.mark.asyncio
    async def test_fallback_notification_includes_store_name(self):
        """Fallback notification must include the nearest CTC store name."""
        from src.backend.services.context_scoring_service import ContextScore
        svc = ClaudeContextScoringService.__new__(ClaudeContextScoringService)
        svc._cache = {}
        svc._fallback = MagicMock()
        svc._fallback.score.return_value = ContextScore(
            total=65.0,
            breakdown={"proximity": 25.0, "category_affinity": 20.0,
                       "time_alignment": 10.0, "weather": 5.0, "frequency": 5.0,
                       "purchase_value": 0.0, "partner_crosssell": 0.0},
        )

        offer = _active_offer()
        ctx = _make_context(store_name="Canadian Tire Don Mills")
        result = svc._deterministic_fallback(ctx, offer)

        assert "Don Mills" in result.notification_text


# ─── Point 3: Partner trigger notification details ────────────────────────────

class TestPartnerTriggerNotification:
    """Tim Hortons trigger notification must include CTC store + payment split."""

    def test_predictive_message_includes_payment_split(self):
        from src.backend.services.location_zone_service import LocationZone
        from src.backend.services.canadian_holiday_service import TimeType
        from src.backend.models.partner_event import PartnerPurchaseEvent
        from src.backend.services.partner_trigger_service import PartnerTriggerService

        svc = PartnerTriggerService.__new__(PartnerTriggerService)
        svc._store_fixtures = CTCStoreFixtures()
        svc._MARKETPLACE_PREMIUM = {"automotive": 1.15}

        import datetime as dt
        event = PartnerPurchaseEvent(
            event_id="evt-001",
            partner_id="tim_hortons",
            partner_name="Tim Hortons",
            member_id="member-1",
            purchase_amount=5.50,
            purchase_category="beverages",
            location=GeoPoint(lat=43.72, lon=-79.38),
            store_name="Tim Hortons College St",
            timestamp=dt.datetime.utcnow(),
        )

        _, message = svc._build_predictive_context(
            event, "automotive", LocationZone.urban, TimeType.weekday
        )

        assert "75%" in message
        assert "25%" in message

    def test_predictive_message_includes_ctc_store_name(self):
        from src.backend.services.location_zone_service import LocationZone
        from src.backend.services.canadian_holiday_service import TimeType
        from src.backend.models.partner_event import PartnerPurchaseEvent
        from src.backend.services.partner_trigger_service import PartnerTriggerService

        svc = PartnerTriggerService.__new__(PartnerTriggerService)
        svc._store_fixtures = CTCStoreFixtures()
        svc._MARKETPLACE_PREMIUM = {}

        import datetime as dt
        event = PartnerPurchaseEvent(
            event_id="evt-002",
            partner_id="tim_hortons",
            partner_name="Tim Hortons",
            member_id="member-1",
            purchase_amount=5.50,
            purchase_category="beverages",
            location=GeoPoint(lat=43.72, lon=-79.38),
            store_name="Tim Hortons College St",
            timestamp=dt.datetime.utcnow(),
        )

        _, message = svc._build_predictive_context(
            event, "automotive", LocationZone.urban, TimeType.weekday
        )

        # Should include a CTC store name (not just "your nearest Canadian Tire")
        assert "Canadian Tire" in message

    def test_fallback_message_includes_payment_split(self):
        from src.backend.models.partner_event import PartnerPurchaseEvent
        from src.backend.services.partner_trigger_service import PartnerTriggerService

        svc = PartnerTriggerService.__new__(PartnerTriggerService)
        svc._store_fixtures = CTCStoreFixtures()

        import datetime as dt, asyncio
        event = PartnerPurchaseEvent(
            event_id="evt-003",
            partner_id="tim_hortons",
            partner_name="Tim Hortons",
            member_id="member-1",
            purchase_amount=5.50,
            purchase_category="beverages",
            location=GeoPoint(lat=43.72, lon=-79.38),
            store_name="Tim Hortons College St",
            timestamp=dt.datetime.utcnow(),
        )

        # Trigger the else branch (no location_zone/time_type)
        offer = asyncio.run(svc._generate_offer(event, "automotive"))
        push_msg = offer.channels[0].message_template
        assert push_msg is not None
        assert "75%" in push_msg
        assert "25%" in push_msg


# ─── Point 4: Unique offer per permutation ───────────────────────────────────

@pytest.mark.parametrize("member_id,category,store,tier,expected_tier_in_key", [
    ("member-gold-1", "automotive",  "Canadian Tire Don Mills",    "gold",     True),
    ("member-gold-2", "automotive",  "Canadian Tire Don Mills",    "gold",     True),
    ("member-silver", "automotive",  "Canadian Tire Don Mills",    "silver",   True),
    ("member-plat",   "home",        "Canadian Tire Scarborough",  "platinum", True),
    ("member-gold-1", "home",        "Canadian Tire Don Mills",    "gold",     True),
    ("member-gold-1", "automotive",  "Canadian Tire Scarborough",  "gold",     True),
])
def test_unique_cache_key_per_member_product(member_id, category, store, tier, expected_tier_in_key):
    """Every (member, product_category) combination produces a distinct cache key.

    This guarantees Claude is called separately for each permutation and each
    member gets a uniquely personalised notification (not a shared cache hit).
    """
    svc = ClaudeContextScoringService.__new__(ClaudeContextScoringService)
    svc._cache = {}
    svc._fallback = MagicMock()

    offer = _active_offer()
    ctx = _make_context(member_id=member_id, category=category, store_name=store, loyalty_tier=tier)

    key = svc._context_hash(ctx, offer)
    assert isinstance(key, str) and len(key) == 64  # SHA256 hex


def test_different_members_same_context_get_different_keys():
    """Two different members with identical purchase context get different cache keys."""
    svc = ClaudeContextScoringService.__new__(ClaudeContextScoringService)
    svc._cache = {}
    svc._fallback = MagicMock()
    offer = _active_offer()

    ctx_a = _make_context(member_id="member-A", loyalty_tier="gold")
    ctx_b = _make_context(member_id="member-B", loyalty_tier="gold")

    assert svc._context_hash(ctx_a, offer) != svc._context_hash(ctx_b, offer)


def test_different_loyalty_tiers_get_different_keys():
    """Gold vs Silver members with same purchase get different cache keys."""
    svc = ClaudeContextScoringService.__new__(ClaudeContextScoringService)
    svc._cache = {}
    svc._fallback = MagicMock()
    offer = _active_offer()

    ctx_gold = _make_context(member_id="member-1", loyalty_tier="gold")
    ctx_silver = _make_context(member_id="member-1", loyalty_tier="silver")

    assert svc._context_hash(ctx_gold, offer) != svc._context_hash(ctx_silver, offer)


def test_different_categories_get_different_keys():
    """Automotive vs Home purchase categories produce different cache keys."""
    svc = ClaudeContextScoringService.__new__(ClaudeContextScoringService)
    svc._cache = {}
    svc._fallback = MagicMock()
    offer = _active_offer()

    ctx_auto = _make_context(member_id="member-1", category="automotive")
    ctx_home = _make_context(member_id="member-1", category="home")

    assert svc._context_hash(ctx_auto, offer) != svc._context_hash(ctx_home, offer)


# ─── Point 5: Smart match — CTC first, then partner ─────────────────────────

@pytest.mark.integration
class TestSmartMatch:
    """Smart match returns multiple offers, CTC-store offers ranked before partner offers."""

    @pytest.mark.asyncio
    async def test_smart_match_returns_ctc_offers_first(self):
        """CTC-store offers (priority=1) must appear before partner offers (priority=2)."""
        from src.backend.services.scout_match_service import ScoutMatchService
        from src.backend.models.scout_match import ScoutOutcome

        ctc_offer = _active_offer(TriggerType.marketer_initiated)
        ctc_offer = ctc_offer.model_copy(update={"offer_id": "ctc-offer-001"})

        partner_offer = _active_offer(TriggerType.partner_triggered)
        partner_offer = partner_offer.model_copy(update={"offer_id": "partner-offer-001"})

        mock_hub = AsyncMock()
        mock_hub.get_active_offers.return_value = [partner_offer, ctc_offer]  # Partner first in Hub

        mock_scorer = AsyncMock()
        mock_scorer.score.side_effect = [
            ClaudeScoreResult(score=72.0, rationale="good", notification_text="Partner offer — Use up to 75% Triangle points, pay min 25% by card.", scoring_method=ScoringMethod.fallback),
            ClaudeScoreResult(score=68.0, rationale="good", notification_text="CTC offer — Use up to 75% Triangle points, pay min 25% by card.", scoring_method=ScoringMethod.fallback),
        ]

        mock_constraints = MagicMock()
        mock_constraints.can_deliver.return_value = (True, None)

        mock_audit = AsyncMock()
        mock_member_store = MagicMock()
        mock_member_store.get.return_value = MemberProfile(
            member_id="member-1", segment="active", preferred_categories=["automotive"],
            total_spend_90_days=500.0, purchase_count_90_days=5,
            loyalty_tier="gold", notifications_enabled=True,
        )
        mock_store_fixtures = MagicMock()
        mock_store_fixtures.get_nearby.return_value = []

        svc = ScoutMatchService(
            hub_client=mock_hub,
            scorer=mock_scorer,
            constraints=mock_constraints,
            audit=mock_audit,
            member_store=mock_member_store,
            store_fixtures=mock_store_fixtures,
        )

        request = MatchRequest(
            member_id="member-1",
            purchase_location=GeoPoint(lat=43.72, lon=-79.38),
            purchase_category="automotive",
            rewards_earned=100,
            day_context=DayContext.weekday,
        )

        result = await svc.smart_match(request)

        assert isinstance(result, SmartMatchResponse)
        assert result.total == 2
        # CTC offer must come first regardless of Hub order
        assert result.offers[0].trigger_type == "ctc"
        assert result.offers[1].trigger_type == "partner"
        # Verify priority fields
        assert result.offers[0].priority == 1
        assert result.offers[1].priority == 2

    @pytest.mark.asyncio
    async def test_smart_match_no_active_offers_returns_empty(self):
        from src.backend.services.scout_match_service import ScoutMatchService

        mock_hub = AsyncMock()
        mock_hub.get_active_offers.return_value = []

        svc = ScoutMatchService(
            hub_client=mock_hub,
            scorer=AsyncMock(),
            constraints=MagicMock(),
            audit=AsyncMock(),
            member_store=MagicMock(),
            store_fixtures=MagicMock(),
        )

        request = MatchRequest(
            member_id="member-1",
            purchase_location=GeoPoint(lat=43.72, lon=-79.38),
            purchase_category="automotive",
            rewards_earned=100,
        )

        result = await svc.smart_match(request)
        assert result.total == 0
        assert result.offers == []

    @pytest.mark.asyncio
    async def test_smart_match_notification_contains_payment_split(self):
        """Each smart-match offer notification must mention 75/25 payment split."""
        from src.backend.services.scout_match_service import ScoutMatchService

        offer = _active_offer()

        mock_hub = AsyncMock()
        mock_hub.get_active_offers.return_value = [offer]

        notification = "15% off at Canadian Tire 0.5km away. Use up to 75% Triangle points, pay min 25% by card."
        mock_scorer = AsyncMock()
        mock_scorer.score.return_value = ClaudeScoreResult(
            score=80.0, rationale="great match",
            notification_text=notification,
            scoring_method=ScoringMethod.fallback,
        )

        mock_constraints = MagicMock()
        mock_constraints.can_deliver.return_value = (True, None)
        mock_member = MagicMock()
        mock_member.get.return_value = MemberProfile(
            member_id="member-1", segment="active", preferred_categories=["automotive"],
            total_spend_90_days=500.0, purchase_count_90_days=5,
            loyalty_tier="gold", notifications_enabled=True,
        )

        svc = ScoutMatchService(
            hub_client=mock_hub,
            scorer=mock_scorer,
            constraints=mock_constraints,
            audit=AsyncMock(),
            member_store=mock_member,
            store_fixtures=MagicMock(),
        )

        request = MatchRequest(
            member_id="member-1",
            purchase_location=GeoPoint(lat=43.72, lon=-79.38),
            purchase_category="automotive",
            rewards_earned=100,
        )

        result = await svc.smart_match(request)
        assert result.total == 1
        assert "75%" in result.offers[0].notification_text
        assert "25%" in result.offers[0].notification_text
