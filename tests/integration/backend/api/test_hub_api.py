"""Integration tests for Hub API routes — offer state store."""

import json
import uuid
from copy import deepcopy
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.backend.api.deps import get_hub_store
from src.backend.main import app

FIXTURES = json.loads(
    (Path(__file__).parents[3] / "fixtures/offer_brief_responses.json").read_text()
)


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


SYSTEM_HEADERS = {"Authorization": "Bearer system-token"}
MARKETING_HEADERS = {"Authorization": "Bearer marketing-token"}


@pytest.fixture
def system_token_patch():
    """Patch JWT decode to return a system-role token."""
    return patch(
        "src.backend.core.security._decode_token",
        return_value={"sub": "scout-service", "role": "system"},
    )


@pytest.fixture
def marketing_token_patch():
    """Patch JWT decode to return a marketing-role token."""
    return patch(
        "src.backend.core.security._decode_token",
        return_value={"sub": "user-1", "role": "marketing"},
    )


def marketer_offer(offer_id: str | None = None) -> dict:
    """Return a fresh draft marketer-initiated offer."""
    data = deepcopy(FIXTURES["valid_marketer_offer"])
    data["offer_id"] = offer_id or str(uuid.uuid4())
    return data


def purchase_offer(offer_id: str | None = None) -> dict:
    """Return a fresh active purchase-triggered offer."""
    data = deepcopy(FIXTURES["purchase_triggered_offer"])
    data["offer_id"] = offer_id or str(uuid.uuid4())
    return data


# ─── POST /api/hub/offers ────────────────────────────────────────────────────

@pytest.mark.integration
class TestSaveOffer:
    async def test_save_draft_offer_returns_201(self, client, system_token_patch):
        offer = marketer_offer()
        with system_token_patch:
            response = await client.post("/api/hub/offers", json=offer, headers=SYSTEM_HEADERS)

        assert response.status_code == 201
        data = response.json()
        assert data["offer_id"] == offer["offer_id"]
        assert data["status"] == "draft"

    async def test_save_purchase_triggered_active_returns_201(self, client, system_token_patch):
        """F-003: purchase_triggered offers may be saved with status=active."""
        offer = purchase_offer()
        with system_token_patch:
            response = await client.post("/api/hub/offers", json=offer, headers=SYSTEM_HEADERS)

        assert response.status_code == 201
        assert response.json()["status"] == "active"

    async def test_save_marketer_active_returns_422(self, client, system_token_patch):
        """F-003: marketer_initiated offers CANNOT be saved with status=active."""
        offer = marketer_offer()
        offer["status"] = "active"
        with system_token_patch:
            response = await client.post("/api/hub/offers", json=offer, headers=SYSTEM_HEADERS)

        assert response.status_code == 422
        assert "purchase_triggered" in response.json()["detail"]

    async def test_duplicate_offer_id_returns_409(self, client, system_token_patch):
        offer = marketer_offer()
        with system_token_patch:
            await client.post("/api/hub/offers", json=offer, headers=SYSTEM_HEADERS)
            response = await client.post("/api/hub/offers", json=offer, headers=SYSTEM_HEADERS)

        assert response.status_code == 409
        assert offer["offer_id"] in response.json()["detail"]

    async def test_save_allowed_with_marketing_role(self, client, marketing_token_patch):
        """Marketing-role callers are now allowed to save offers (marketer-initiated flow)."""
        offer = marketer_offer()
        with marketing_token_patch:
            response = await client.post("/api/hub/offers", json=offer, headers=MARKETING_HEADERS)

        assert response.status_code == 201

    async def test_save_requires_auth(self, client):
        offer = marketer_offer()
        response = await client.post("/api/hub/offers", json=offer)
        assert response.status_code == 401


# ─── GET /api/hub/offers/{offer_id} ─────────────────────────────────────────

@pytest.mark.integration
class TestGetOffer:
    async def test_get_existing_offer_returns_200(self, client, system_token_patch, marketing_token_patch):
        offer = marketer_offer()
        with system_token_patch:
            await client.post("/api/hub/offers", json=offer, headers=SYSTEM_HEADERS)

        with marketing_token_patch:
            response = await client.get(f"/api/hub/offers/{offer['offer_id']}",
                                        headers=MARKETING_HEADERS)

        assert response.status_code == 200
        assert response.json()["offer_id"] == offer["offer_id"]

    async def test_get_missing_offer_returns_404(self, client, marketing_token_patch):
        with marketing_token_patch:
            response = await client.get("/api/hub/offers/nonexistent-id",
                                        headers=MARKETING_HEADERS)

        assert response.status_code == 404

    async def test_get_missing_returns_404_no_auth_needed(self, client):
        # Auth removed from GET /offers/{id} in develop — endpoint is now public read-only
        response = await client.get("/api/hub/offers/nonexistent-id-xyz")
        assert response.status_code == 404


# ─── GET /api/hub/offers ─────────────────────────────────────────────────────

@pytest.mark.integration
class TestListOffers:
    async def test_list_returns_all_offers(self, client, system_token_patch, marketing_token_patch):
        # Two offers with identical objectives are deduplicated — only 1 returned
        with system_token_patch:
            await client.post("/api/hub/offers", json=marketer_offer(), headers=SYSTEM_HEADERS)
            await client.post("/api/hub/offers", json=marketer_offer(), headers=SYSTEM_HEADERS)

        with marketing_token_patch:
            response = await client.get("/api/hub/offers", headers=MARKETING_HEADERS)

        assert response.status_code == 200
        data = response.json()
        # Deduplication by objective text collapses duplicates to 1
        assert data["count"] == 1
        assert len(data["offers"]) == 1

    async def test_filter_by_status(self, client, system_token_patch, marketing_token_patch):
        with system_token_patch:
            await client.post("/api/hub/offers", json=marketer_offer(), headers=SYSTEM_HEADERS)
            await client.post("/api/hub/offers", json=purchase_offer(), headers=SYSTEM_HEADERS)

        with marketing_token_patch:
            response = await client.get("/api/hub/offers?status=active", headers=MARKETING_HEADERS)

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["offers"][0]["status"] == "active"

    async def test_filter_by_trigger_type(self, client, system_token_patch, marketing_token_patch):
        with system_token_patch:
            await client.post("/api/hub/offers", json=marketer_offer(), headers=SYSTEM_HEADERS)
            await client.post("/api/hub/offers", json=purchase_offer(), headers=SYSTEM_HEADERS)

        with marketing_token_patch:
            response = await client.get(
                "/api/hub/offers?trigger_type=purchase_triggered", headers=MARKETING_HEADERS
            )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["offers"][0]["trigger_type"] == "purchase_triggered"

    async def test_filter_by_since_excludes_older_offers(self, client, system_token_patch, marketing_token_patch):
        """Offers created before the since timestamp are excluded."""
        with system_token_patch:
            await client.post("/api/hub/offers", json=marketer_offer(), headers=SYSTEM_HEADERS)

        with marketing_token_patch:
            response = await client.get(
                "/api/hub/offers?since=2026-03-28T00:00:00", headers=MARKETING_HEADERS
            )

        assert response.status_code == 200
        assert response.json()["count"] == 0

    async def test_empty_store_returns_empty_list(self, client, marketing_token_patch):
        with marketing_token_patch:
            response = await client.get("/api/hub/offers", headers=MARKETING_HEADERS)

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["offers"] == []

    async def test_list_no_auth_returns_200(self, client):
        # Auth removed from GET /offers in develop — endpoint is now public read-only
        response = await client.get("/api/hub/offers")
        assert response.status_code == 200


# ─── PUT /api/hub/offers/{offer_id}/status ───────────────────────────────────

@pytest.mark.integration
class TestUpdateStatus:
    async def test_update_draft_to_approved(self, client, system_token_patch):
        offer = marketer_offer()
        with system_token_patch:
            await client.post("/api/hub/offers", json=offer, headers=SYSTEM_HEADERS)
            response = await client.put(
                f"/api/hub/offers/{offer['offer_id']}/status",
                params={"new_status": "approved"},
                headers=SYSTEM_HEADERS,
            )

        assert response.status_code == 200
        assert response.json()["status"] == "approved"

    async def test_update_approved_to_active(self, client, system_token_patch):
        offer = marketer_offer()
        offer["status"] = "approved"
        with system_token_patch:
            await client.post("/api/hub/offers", json=offer, headers=SYSTEM_HEADERS)
            response = await client.put(
                f"/api/hub/offers/{offer['offer_id']}/status",
                params={"new_status": "active"},
                headers=SYSTEM_HEADERS,
            )

        assert response.status_code == 200
        assert response.json()["status"] == "active"

    async def test_update_active_to_expired(self, client, system_token_patch):
        offer = purchase_offer()
        with system_token_patch:
            await client.post("/api/hub/offers", json=offer, headers=SYSTEM_HEADERS)
            response = await client.put(
                f"/api/hub/offers/{offer['offer_id']}/status",
                params={"new_status": "expired"},
                headers=SYSTEM_HEADERS,
            )

        assert response.status_code == 200
        assert response.json()["status"] == "expired"

    async def test_update_nonexistent_offer_returns_404(self, client, system_token_patch):
        with system_token_patch:
            response = await client.put(
                "/api/hub/offers/does-not-exist/status",
                params={"new_status": "approved"},
                headers=SYSTEM_HEADERS,
            )

        assert response.status_code == 404

    async def test_update_allowed_with_marketing_role(self, client, marketing_token_patch, system_token_patch):
        """Marketing-role callers are now allowed to update offer status (Hub page flow)."""
        offer = marketer_offer()
        with system_token_patch:
            await client.post("/api/hub/offers", json=offer, headers=SYSTEM_HEADERS)

        with marketing_token_patch:
            response = await client.put(
                f"/api/hub/offers/{offer['offer_id']}/status",
                params={"new_status": "approved"},
                headers=MARKETING_HEADERS,
            )

        assert response.status_code == 200

    async def test_invalid_transition_returns_422(self, client, system_token_patch):
        """AC-010: draft → active is an invalid transition — must return 422."""
        offer = marketer_offer()
        with system_token_patch:
            await client.post("/api/hub/offers", json=offer, headers=SYSTEM_HEADERS)
            response = await client.put(
                f"/api/hub/offers/{offer['offer_id']}/status",
                params={"new_status": "active"},
                headers=SYSTEM_HEADERS,
            )

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert detail["error"] == "InvalidTransition"
        assert detail["old_status"] == "draft"
        assert detail["new_status"] == "active"


@pytest.mark.integration
class TestRedisUnavailable:
    async def test_redis_unavailable_save_returns_503(self, client, system_token_patch):
        """AC-005: When store raises RedisUnavailableError, save must return 503."""
        from src.backend.services.hub_store import RedisUnavailableError
        from src.backend.api.deps import get_hub_store
        from src.backend.main import app

        mock_store = AsyncMock()
        mock_store.save.side_effect = RedisUnavailableError("connection refused")

        offer = marketer_offer()
        app.dependency_overrides[get_hub_store] = lambda: mock_store
        try:
            with system_token_patch:
                response = await client.post(
                    "/api/hub/offers", json=offer, headers=SYSTEM_HEADERS
                )
        finally:
            app.dependency_overrides.pop(get_hub_store, None)

        assert response.status_code == 503

    async def test_redis_unavailable_get_returns_503(self, client, marketing_token_patch):
        """AC-006: When store raises RedisUnavailableError, get must return 503."""
        from src.backend.services.hub_store import RedisUnavailableError
        from src.backend.api.deps import get_hub_store
        from src.backend.main import app

        mock_store = AsyncMock()
        mock_store.get.side_effect = RedisUnavailableError("connection refused")

        app.dependency_overrides[get_hub_store] = lambda: mock_store
        try:
            with marketing_token_patch:
                response = await client.get(
                    "/api/hub/offers/some-offer-id", headers=MARKETING_HEADERS
                )
        finally:
            app.dependency_overrides.pop(get_hub_store, None)

        assert response.status_code == 503
