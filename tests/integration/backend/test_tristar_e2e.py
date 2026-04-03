"""E2E cross-layer integration tests — Hub CRUD chain → Scout activation chain.

Phase 1: Full offer lifecycle through Hub API status transitions.
Phase 2: Scout activation endpoint tests with mocked service.
"""

import uuid
from copy import deepcopy
from pathlib import Path
import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.backend.api.deps import get_hub_store, get_scout_match_service
from src.backend.main import app
from src.backend.models.scout_match import MatchResponse, ScoutOutcome, ScoringMethod
from src.backend.services.scout_match_service import ScoutMatchService

FIXTURES = json.loads(
    (Path(__file__).parents[2] / "fixtures/offer_brief_responses.json").read_text()
)

SYSTEM_HEADERS = {"Authorization": "Bearer system-token"}
MARKETING_HEADERS = {"Authorization": "Bearer marketing-token"}


@pytest.fixture(autouse=True)
def clear_hub_store():
    """Wipe in-memory Hub store before and after each test."""
    get_hub_store().clear()
    yield
    get_hub_store().clear()


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
def system_token_patch():
    return patch(
        "src.backend.core.security._decode_token",
        return_value={"sub": "scout-service", "role": "system"},
    )


@pytest.fixture
def marketing_token_patch():
    return patch(
        "src.backend.core.security._decode_token",
        return_value={"sub": "user-1", "role": "marketing"},
    )


def _fresh_offer() -> dict:
    """Return a deep copy of the marketer offer fixture with a unique offer_id."""
    data = deepcopy(FIXTURES["valid_marketer_offer"])
    data["offer_id"] = str(uuid.uuid4())
    return data


# ── Phase 1: Hub CRUD chain ────────────────────────────────────────────────────

@pytest.mark.integration
class TestHubCrudChain:
    """Full offer lifecycle: create → approve → activate → expire."""

    async def test_create_offer_returns_201_with_draft_status(self, client, system_token_patch):
        offer = _fresh_offer()
        with system_token_patch:
            resp = await client.post("/api/hub/offers", json=offer, headers=SYSTEM_HEADERS)

        assert resp.status_code == 201
        assert resp.json()["status"] == "draft"
        assert resp.json()["offer_id"] == offer["offer_id"]

    async def test_get_offer_after_create_returns_draft(self, client, system_token_patch):
        offer = _fresh_offer()
        with system_token_patch:
            await client.post("/api/hub/offers", json=offer, headers=SYSTEM_HEADERS)
            resp = await client.get(
                f"/api/hub/offers/{offer['offer_id']}", headers=SYSTEM_HEADERS
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "draft"

    async def test_draft_to_approved_transition(self, client, system_token_patch):
        offer = _fresh_offer()
        with system_token_patch:
            await client.post("/api/hub/offers", json=offer, headers=SYSTEM_HEADERS)
            resp = await client.put(
                f"/api/hub/offers/{offer['offer_id']}/status",
                params={"new_status": "approved"},
                headers=SYSTEM_HEADERS,
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    async def test_approved_to_active_transition(self, client, system_token_patch):
        offer = _fresh_offer()
        with system_token_patch:
            await client.post("/api/hub/offers", json=offer, headers=SYSTEM_HEADERS)
            await client.put(
                f"/api/hub/offers/{offer['offer_id']}/status",
                params={"new_status": "approved"},
                headers=SYSTEM_HEADERS,
            )
            resp = await client.put(
                f"/api/hub/offers/{offer['offer_id']}/status",
                params={"new_status": "active"},
                headers=SYSTEM_HEADERS,
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

    async def test_list_active_offers_contains_activated_offer(
        self, client, system_token_patch, marketing_token_patch
    ):
        offer = _fresh_offer()
        offer_id = offer["offer_id"]

        with system_token_patch:
            await client.post("/api/hub/offers", json=offer, headers=SYSTEM_HEADERS)
            await client.put(
                f"/api/hub/offers/{offer_id}/status",
                params={"new_status": "approved"},
                headers=SYSTEM_HEADERS,
            )
            await client.put(
                f"/api/hub/offers/{offer_id}/status",
                params={"new_status": "active"},
                headers=SYSTEM_HEADERS,
            )

        with marketing_token_patch:
            resp = await client.get(
                "/api/hub/offers", params={"status": "active"}, headers=MARKETING_HEADERS
            )

        assert resp.status_code == 200
        offer_ids = [o["offer_id"] for o in resp.json()["offers"]]
        assert offer_id in offer_ids

    async def test_invalid_backward_transition_returns_422(self, client, system_token_patch):
        """AC-010: active → draft is an invalid backward transition."""
        offer = _fresh_offer()
        offer_id = offer["offer_id"]

        with system_token_patch:
            await client.post("/api/hub/offers", json=offer, headers=SYSTEM_HEADERS)
            await client.put(
                f"/api/hub/offers/{offer_id}/status",
                params={"new_status": "approved"},
                headers=SYSTEM_HEADERS,
            )
            await client.put(
                f"/api/hub/offers/{offer_id}/status",
                params={"new_status": "active"},
                headers=SYSTEM_HEADERS,
            )
            resp = await client.put(
                f"/api/hub/offers/{offer_id}/status",
                params={"new_status": "draft"},
                headers=SYSTEM_HEADERS,
            )

        assert resp.status_code == 422

    async def test_active_to_expired_transition(self, client, system_token_patch):
        offer = _fresh_offer()
        offer_id = offer["offer_id"]

        with system_token_patch:
            await client.post("/api/hub/offers", json=offer, headers=SYSTEM_HEADERS)
            await client.put(
                f"/api/hub/offers/{offer_id}/status",
                params={"new_status": "approved"},
                headers=SYSTEM_HEADERS,
            )
            await client.put(
                f"/api/hub/offers/{offer_id}/status",
                params={"new_status": "active"},
                headers=SYSTEM_HEADERS,
            )
            resp = await client.put(
                f"/api/hub/offers/{offer_id}/status",
                params={"new_status": "expired"},
                headers=SYSTEM_HEADERS,
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "expired"


# ── Phase 2: Scout activation chain ───────────────────────────────────────────

@pytest.mark.integration
class TestScoutActivationChain:
    """Scout match endpoint with mocked service and feature-flag tests."""

    def _valid_payload(self, member_id: str = "demo-001") -> dict:
        return {
            "member_id": member_id,
            "purchase_location": {"lat": 43.649, "lon": -79.398},
            "purchase_category": "sporting_goods",
            "rewards_earned": 150,
            "day_context": "weekday",
            "weather_condition": "clear",
        }

    async def test_scout_activation_returns_200_with_all_fields(self, client):
        svc = AsyncMock(spec=ScoutMatchService)
        svc.match.return_value = MatchResponse(
            score=78.5,
            rationale="Outdoor fan near CTC store",
            notification_text="Earn 3× points on outdoor gear today!",
            offer_id="offer-demo-001",
            outcome=ScoutOutcome.activated,
            scoring_method=ScoringMethod.claude,
        )
        app.dependency_overrides[get_scout_match_service] = lambda: svc
        try:
            resp = await client.post("/api/scout/match", json=self._valid_payload())
        finally:
            app.dependency_overrides.pop(get_scout_match_service, None)

        assert resp.status_code == 200
        data = resp.json()
        assert data["outcome"] == "activated"
        assert data["offer_id"] == "offer-demo-001"
        assert data["score"] == pytest.approx(78.5)
        assert data["scoring_method"] == "claude"
        assert "rationale" in data
        assert "notification_text" in data

    async def test_scout_activation_log_returns_list(self, client):
        resp = await client.get("/api/scout/activation-log/demo-001")

        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_scout_rate_limited_response_shape(self, client):
        svc = AsyncMock(spec=ScoutMatchService)
        svc.match.return_value = MatchResponse(
            score=75.0,
            rationale="Rate limited",
            notification_text="",
            offer_id="offer-x",
            outcome=ScoutOutcome.rate_limited,
            scoring_method=ScoringMethod.fallback,
            retry_after_seconds=21600,
        )
        app.dependency_overrides[get_scout_match_service] = lambda: svc
        try:
            resp = await client.post(
                "/api/scout/match", json=self._valid_payload(member_id="demo-005")
            )
        finally:
            app.dependency_overrides.pop(get_scout_match_service, None)

        assert resp.status_code == 200
        data = resp.json()
        assert data["outcome"] == "rate_limited"
        assert data["retry_after_seconds"] == 21600

    async def test_scout_feature_flag_off_returns_503(self, client):
        with patch("src.backend.api.scout.settings") as mock_settings:
            mock_settings.SCOUT_MATCH_ENABLED = False
            resp = await client.post("/api/scout/match", json=self._valid_payload())

        assert resp.status_code == 503
