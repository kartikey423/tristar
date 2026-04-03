"""Unit tests for ScoutMatchService — activation pipeline, constraints, outcomes."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.backend.models.offer_brief import OfferBrief
from src.backend.models.purchase_event import GeoPoint, WeatherConditions
from src.backend.models.scout_match import (
    DayContext,
    MatchRequest,
    MatchResponse,
    NoMatchResponse,
    ScoutOutcome,
    ScoringMethod,
)
from src.backend.services.claude_context_scoring_service import ClaudeScoreResult
from src.backend.services.scout_match_service import ScoutMatchService


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_request(**kwargs) -> MatchRequest:
    defaults = dict(
        member_id="demo-001",
        purchase_location=GeoPoint(lat=43.649, lon=-79.398),
        purchase_category="food_beverage",
        rewards_earned=120,
        day_context=DayContext.weekday,
    )
    defaults.update(kwargs)
    return MatchRequest(**defaults)


def _make_offer(offer_id: str = "offer-001") -> MagicMock:
    offer = MagicMock(spec=OfferBrief)
    offer.offer_id = offer_id
    return offer


def _make_score_result(score: float, method: ScoringMethod = ScoringMethod.claude) -> ClaudeScoreResult:
    return ClaudeScoreResult(
        score=score,
        rationale="Test rationale",
        notification_text="Test notification",
        scoring_method=method,
    )


def _make_service(
    active_offers=None,
    score_result=None,
    can_deliver=(True, None),
    retry_after=0,
) -> ScoutMatchService:
    hub = AsyncMock()
    hub.get_active_offers.return_value = active_offers or []

    scorer = AsyncMock()
    scorer.score.return_value = score_result or _make_score_result(75.0)

    constraints = MagicMock()
    constraints.can_deliver.return_value = can_deliver
    constraints.retry_after_seconds.return_value = retry_after
    constraints.record_delivery = MagicMock()
    constraints.queue_for_morning = MagicMock()

    audit = AsyncMock()
    audit.log_activation = AsyncMock()

    member_store = MagicMock()
    member_store.get.return_value = None

    store_fixtures = MagicMock()
    store_fixtures.get_nearby.return_value = []

    return ScoutMatchService(
        hub_client=hub,
        scorer=scorer,
        constraints=constraints,
        audit=audit,
        member_store=member_store,
        store_fixtures=store_fixtures,
    )


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestScoutMatchService:

    async def test_returns_no_match_when_no_active_offers(self):
        svc = _make_service(active_offers=[])
        result = await svc.match(_make_request())
        assert isinstance(result, NoMatchResponse)
        assert "No active offers" in result.message

    async def test_returns_no_match_when_all_scores_below_threshold(self):
        svc = _make_service(
            active_offers=[_make_offer()],
            score_result=_make_score_result(55.0),  # ≤ 60
        )
        result = await svc.match(_make_request())
        assert isinstance(result, NoMatchResponse)
        assert "threshold" in result.message.lower()

    async def test_con001_threshold_is_strictly_greater_than_60(self):
        """CON-001: score must be strictly > 60 to activate."""
        svc = _make_service(
            active_offers=[_make_offer()],
            score_result=_make_score_result(60.0),  # exactly 60 — should NOT activate
        )
        result = await svc.match(_make_request())
        assert isinstance(result, NoMatchResponse)

    async def test_activates_when_score_above_threshold(self):
        svc = _make_service(
            active_offers=[_make_offer("offer-abc")],
            score_result=_make_score_result(75.0),
            can_deliver=(True, None),
        )
        result = await svc.match(_make_request())
        assert isinstance(result, MatchResponse)
        assert result.outcome == ScoutOutcome.activated
        assert result.offer_id == "offer-abc"
        assert result.score == 75.0

    async def test_returns_rate_limited_when_constrained(self):
        svc = _make_service(
            active_offers=[_make_offer()],
            score_result=_make_score_result(80.0),
            can_deliver=(False, "Rate limit: member already received an offer within 6h"),
            retry_after=18000,
        )
        result = await svc.match(_make_request())
        assert isinstance(result, MatchResponse)
        assert result.outcome == ScoutOutcome.rate_limited
        assert result.retry_after_seconds == 18000

    async def test_returns_queued_during_quiet_hours(self):
        svc = _make_service(
            active_offers=[_make_offer()],
            score_result=_make_score_result(80.0),
            can_deliver=(False, "Quiet hours: delivery queued for 8am"),
        )
        result = await svc.match(_make_request())
        assert isinstance(result, MatchResponse)
        assert result.outcome == ScoutOutcome.queued
        assert result.queued is True
        assert result.delivery_time == "08:00"

    async def test_f005_candidate_cap_limits_scoring_calls(self):
        """F-005: at most CANDIDATE_CAP=5 offers are scored."""
        offers = [_make_offer(f"offer-{i}") for i in range(10)]
        svc = _make_service(
            active_offers=offers,
            score_result=_make_score_result(30.0),  # None activate → score all candidates
        )
        await svc.match(_make_request())
        # scorer.score should be called at most 5 times
        assert svc._scorer.score.call_count <= 5

    async def test_early_exit_on_first_match(self):
        """Early-exit: stop scoring after first offer scores > 60."""
        offers = [_make_offer(f"offer-{i}") for i in range(5)]
        scorer = AsyncMock()
        scorer.score.return_value = _make_score_result(85.0)  # First offer matches

        svc = _make_service(active_offers=offers)
        svc._scorer = scorer

        await svc.match(_make_request())
        # Only 1 call — early exit after first match
        assert scorer.score.call_count == 1

    async def test_record_delivery_called_on_activation(self):
        svc = _make_service(
            active_offers=[_make_offer()],
            score_result=_make_score_result(75.0),
            can_deliver=(True, None),
        )
        await svc.match(_make_request())
        from unittest.mock import ANY
        svc._constraints.record_delivery.assert_called_once_with("demo-001", now=ANY)

    async def test_audit_log_written_on_activation(self):
        svc = _make_service(
            active_offers=[_make_offer("offer-logged")],
            score_result=_make_score_result(75.0),
            can_deliver=(True, None),
        )
        await svc.match(_make_request())
        svc._audit.log_activation.assert_awaited_once()
        record = svc._audit.log_activation.call_args[0][0]
        assert record.member_id == "demo-001"
        assert record.offer_id == "offer-logged"
        assert record.outcome == "activated"

    async def test_pii_compliance_no_gps_in_record(self):
        """AC-017: ScoutActivationRecord must not contain GPS coordinates."""
        svc = _make_service(
            active_offers=[_make_offer()],
            score_result=_make_score_result(75.0),
            can_deliver=(True, None),
        )
        await svc.match(_make_request())
        record = svc._audit.log_activation.call_args[0][0]
        assert not hasattr(record, "lat")
        assert not hasattr(record, "lon")
        assert not hasattr(record, "purchase_location")

    async def test_weather_condition_override_used_in_context(self):
        """If weather_condition is set in request, skip API call."""
        req = _make_request(weather_condition="snow")
        svc = _make_service(
            active_offers=[_make_offer()],
            score_result=_make_score_result(75.0),
        )
        # Should not raise; weather from override
        result = await svc.match(req)
        assert result is not None

    async def test_casl_opt_out_passes_notifications_disabled_to_can_deliver(self):
        """CASL: member with notifications_enabled=False → can_deliver called with False."""
        mock_member = MagicMock()
        mock_member.notifications_enabled = False

        svc = _make_service(
            active_offers=[_make_offer()],
            score_result=_make_score_result(75.0),
            can_deliver=(True, None),
        )
        svc._member_store.get.return_value = mock_member

        await svc.match(_make_request())

        svc._constraints.can_deliver.assert_called_once()
        kwargs = svc._constraints.can_deliver.call_args.kwargs
        assert kwargs["member_notifications_enabled"] is False

    async def test_casl_opt_out_with_unknown_member_defaults_to_enabled(self):
        """CASL: unknown member (get returns None) → member_notifications_enabled defaults to True."""
        svc = _make_service(
            active_offers=[_make_offer()],
            score_result=_make_score_result(75.0),
            can_deliver=(True, None),
        )
        svc._member_store.get.return_value = None

        await svc.match(_make_request())

        svc._constraints.can_deliver.assert_called_once()
        kwargs = svc._constraints.can_deliver.call_args.kwargs
        assert kwargs["member_notifications_enabled"] is True
