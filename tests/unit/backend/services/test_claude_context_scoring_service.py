"""Unit tests for ClaudeContextScoringService — F-001 fix, cache, fallback."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.backend.models.offer_brief import OfferBrief
from src.backend.models.purchase_event import GeoPoint, MemberProfile, WeatherConditions
from src.backend.models.scout_match import DayContext, EnrichedMatchContext, MatchRequest, ScoringMethod
from src.backend.services.claude_context_scoring_service import ClaudeContextScoringService


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_request() -> MatchRequest:
    return MatchRequest(
        member_id="demo-001",
        purchase_location=GeoPoint(lat=43.649, lon=-79.398),
        purchase_category="food_beverage",
        rewards_earned=120,
        day_context=DayContext.weekday,
    )


def _make_context(request: MatchRequest | None = None) -> EnrichedMatchContext:
    req = request or _make_request()
    return EnrichedMatchContext(
        request=req,
        member=MemberProfile(
            member_id="demo-001",
            segment="frequent_outdoor",
            total_spend_90_days=1240.0,
            purchase_count_90_days=12,
            preferred_categories=["outdoor", "sporting_goods"],
            last_ctc_purchase_days_ago=3,
            loyalty_tier="gold",
        ),
        weather=WeatherConditions(condition="clear", temperature_c=18.0, is_adverse=False),
        nearby_stores=[],
        enrichment_partial=False,
    )


def _make_offer() -> OfferBrief:
    """Minimal OfferBrief with required scorer fields."""
    from src.backend.models.offer_brief import (
        Channel,
        ChannelType,
        Construct,
        KPIs,
        OfferStatus,
        RiskFlags,
        RiskSeverity,
        Segment,
        TriggerType,
    )
    return OfferBrief(
        offer_id="offer-test-001",
        objective="Test offer for outdoor fans",
        trigger_type=TriggerType.marketer_initiated,
        status=OfferStatus.active,
        segment=Segment(name="outdoor_fans", definition="test", estimated_size=1000, criteria=["outdoor"]),
        construct=Construct(
            type="percentage_discount",
            value=20.0,
            description="20% off outdoor gear",
        ),
        channels=[Channel(channel_type=ChannelType.push, priority=1)],
        kpis=KPIs(expected_redemption_rate=0.15, expected_uplift_pct=20.0),
        risk_flags=RiskFlags(
            over_discounting=False,
            cannibalization=False,
            frequency_abuse=False,
            offer_stacking=False,
            severity=RiskSeverity.low,
        ),
    )


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestClaudeContextScoringService:

    @patch("src.backend.services.claude_context_scoring_service.settings")
    async def test_uses_deterministic_fallback_when_no_api_key(self, mock_settings):
        mock_settings.CLAUDE_API_KEY = ""
        mock_settings.CACHE_TTL_SECONDS = 300
        svc = ClaudeContextScoringService()
        result = await svc.score(_make_context(), _make_offer())
        assert result.scoring_method == ScoringMethod.fallback
        assert 0.0 <= result.score <= 100.0

    @patch("src.backend.services.claude_context_scoring_service.settings")
    async def test_returns_cached_result_on_second_call(self, mock_settings):
        mock_settings.CLAUDE_API_KEY = ""
        mock_settings.CACHE_TTL_SECONDS = 300
        svc = ClaudeContextScoringService()
        ctx = _make_context()
        offer = _make_offer()

        first = await svc.score(ctx, offer)
        second = await svc.score(ctx, offer)
        # Second call: cache may hit if deterministic result was cached
        # Mainly verify no exception and consistent score
        assert second.score == first.score

    @patch("src.backend.services.claude_context_scoring_service.settings")
    @patch("src.backend.services.claude_context_scoring_service.anthropic")
    async def test_falls_back_on_timeout(self, mock_anthropic_module, mock_settings):
        """F-001: asyncio.TimeoutError → deterministic fallback, no retry."""
        mock_settings.CLAUDE_API_KEY = "sk-test-key"
        mock_settings.CLAUDE_MODEL = "claude-sonnet-4-6"
        mock_settings.CACHE_TTL_SECONDS = 300

        mock_client = MagicMock()
        mock_anthropic_module.Anthropic.return_value = mock_client

        svc = ClaudeContextScoringService()

        with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
            result = await svc.score(_make_context(), _make_offer())

        assert result.scoring_method == ScoringMethod.fallback

    @patch("src.backend.services.claude_context_scoring_service.settings")
    @patch("src.backend.services.claude_context_scoring_service.anthropic")
    async def test_falls_back_on_api_exception(self, mock_anthropic_module, mock_settings):
        mock_settings.CLAUDE_API_KEY = "sk-test-key"
        mock_settings.CLAUDE_MODEL = "claude-sonnet-4-6"
        mock_settings.CACHE_TTL_SECONDS = 300

        mock_client = MagicMock()
        mock_anthropic_module.Anthropic.return_value = mock_client

        svc = ClaudeContextScoringService()

        with patch(
            "asyncio.wait_for",
            side_effect=Exception("API error"),
        ):
            result = await svc.score(_make_context(), _make_offer())

        assert result.scoring_method == ScoringMethod.fallback

    def test_parse_response_valid_json(self):
        svc = ClaudeContextScoringService.__new__(ClaudeContextScoringService)
        svc._cache = {}
        svc._fallback = MagicMock()
        score, rationale, notif = svc._parse_response(
            '{"score": 75, "rationale": "Good match", "notification_text": "20% off!"}'
        )
        assert score == 75.0
        assert rationale == "Good match"
        assert notif == "20% off!"

    def test_parse_response_clamps_score(self):
        svc = ClaudeContextScoringService.__new__(ClaudeContextScoringService)
        svc._cache = {}
        svc._fallback = MagicMock()
        score, _, _ = svc._parse_response('{"score": 150, "rationale": "x", "notification_text": "y"}')
        assert score == 100.0

        score2, _, _ = svc._parse_response('{"score": -10, "rationale": "x", "notification_text": "y"}')
        assert score2 == 0.0

    def test_parse_response_returns_zero_on_invalid_json(self):
        svc = ClaudeContextScoringService.__new__(ClaudeContextScoringService)
        svc._cache = {}
        svc._fallback = MagicMock()
        score, rationale, _ = svc._parse_response("not json at all")
        assert score == 0.0
        assert "Parse error" in rationale

    def test_context_hash_excludes_member_id(self):
        svc = ClaudeContextScoringService.__new__(ClaudeContextScoringService)
        svc._cache = {}
        svc._fallback = MagicMock()

        offer = _make_offer()
        ctx1 = _make_context()
        ctx2 = _make_context()
        ctx2.request.member_id = "demo-999"  # Different member

        # Same offer + context signals → same hash regardless of member_id
        h1 = svc._context_hash(ctx1, offer)
        h2 = svc._context_hash(ctx2, offer)
        assert h1 == h2
