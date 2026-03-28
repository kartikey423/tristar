"""Integration tests for POST /api/scout/match — F-004 fixes, outcomes, auth."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.backend.api.deps import get_scout_match_service
from src.backend.main import app
from src.backend.models.scout_match import ScoutOutcome, ScoringMethod
from src.backend.services.claude_context_scoring_service import ClaudeScoreResult
from src.backend.services.scout_match_service import ScoutMatchService


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _valid_payload(**kwargs):
    defaults = {
        "member_id": "demo-001",
        "purchase_location": {"lat": 43.649, "lon": -79.398},
        "purchase_category": "food_beverage",
        "rewards_earned": 120,
        "day_context": "weekday",
        "weather_condition": "clear",
    }
    defaults.update(kwargs)
    return defaults


def _mock_match_service_activated():
    from src.backend.models.scout_match import MatchResponse, ScoutOutcome, ScoringMethod
    svc = AsyncMock(spec=ScoutMatchService)
    svc.match.return_value = MatchResponse(
        score=78.5,
        rationale="Great match",
        notification_text="20% off outdoor gear!",
        offer_id="offer-demo-001",
        outcome=ScoutOutcome.activated,
        scoring_method=ScoringMethod.claude,
    )
    return svc


def _mock_match_service_no_match():
    from src.backend.models.scout_match import NoMatchResponse
    svc = AsyncMock(spec=ScoutMatchService)
    svc.match.return_value = NoMatchResponse(message="No offers scored above activation threshold")
    return svc


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.integration
class TestScoutMatchEndpoint:

    async def test_f004_missing_purchase_location_returns_400(self, client):
        """F-004: Missing purchase_location → HTTP 400 (not 422)."""
        payload = {
            "member_id": "demo-001",
            "purchase_category": "food_beverage",
            # purchase_location intentionally omitted
        }
        resp = await client.post("/api/scout/match", json=payload)
        assert resp.status_code == 400
        assert "purchase_location" in resp.json()["detail"].lower()

    async def test_valid_request_returns_200_on_activation(self, client):
        mock_svc = _mock_match_service_activated()
        app.dependency_overrides[get_scout_match_service] = lambda: mock_svc
        try:
            resp = await client.post("/api/scout/match", json=_valid_payload())
        finally:
            app.dependency_overrides.pop(get_scout_match_service, None)

        assert resp.status_code == 200
        data = resp.json()
        assert data["outcome"] == "activated"
        assert data["score"] == pytest.approx(78.5)
        assert data["offer_id"] == "offer-demo-001"
        assert data["scoring_method"] == "claude"
        assert data["notification_text"] == "20% off outdoor gear!"

    async def test_no_match_returns_200_with_empty_matches(self, client):
        mock_svc = _mock_match_service_no_match()
        app.dependency_overrides[get_scout_match_service] = lambda: mock_svc
        try:
            resp = await client.post("/api/scout/match", json=_valid_payload())
        finally:
            app.dependency_overrides.pop(get_scout_match_service, None)

        assert resp.status_code == 200
        data = resp.json()
        assert "message" in data

    async def test_rate_limited_returns_retry_after(self, client):
        from src.backend.models.scout_match import MatchResponse
        svc = AsyncMock(spec=ScoutMatchService)
        svc.match.return_value = MatchResponse(
            score=80.0,
            rationale="Rate limited",
            notification_text="",
            offer_id="offer-x",
            outcome=ScoutOutcome.rate_limited,
            scoring_method=ScoringMethod.fallback,
            retry_after_seconds=21600,
        )
        app.dependency_overrides[get_scout_match_service] = lambda: svc
        try:
            resp = await client.post("/api/scout/match", json=_valid_payload())
        finally:
            app.dependency_overrides.pop(get_scout_match_service, None)

        assert resp.status_code == 200
        assert resp.json()["outcome"] == "rate_limited"
        assert resp.json()["retry_after_seconds"] == 21600

    async def test_queued_response_has_delivery_time(self, client):
        from src.backend.models.scout_match import MatchResponse
        svc = AsyncMock(spec=ScoutMatchService)
        svc.match.return_value = MatchResponse(
            score=75.0,
            rationale="Quiet hours",
            notification_text="",
            offer_id="offer-y",
            outcome=ScoutOutcome.queued,
            scoring_method=ScoringMethod.claude,
            queued=True,
            delivery_time="08:00",
        )
        app.dependency_overrides[get_scout_match_service] = lambda: svc
        try:
            resp = await client.post("/api/scout/match", json=_valid_payload())
        finally:
            app.dependency_overrides.pop(get_scout_match_service, None)

        assert resp.status_code == 200
        data = resp.json()
        assert data["outcome"] == "queued"
        assert data["queued"] is True
        assert data["delivery_time"] == "08:00"

    async def test_invalid_member_id_returns_422(self, client):
        payload = _valid_payload(member_id="")
        resp = await client.post("/api/scout/match", json=payload)
        assert resp.status_code == 422

    async def test_disabled_feature_returns_503(self, client):
        with patch("src.backend.api.scout.settings") as mock_settings:
            mock_settings.SCOUT_MATCH_ENABLED = False
            resp = await client.post("/api/scout/match", json=_valid_payload())
        assert resp.status_code == 503
