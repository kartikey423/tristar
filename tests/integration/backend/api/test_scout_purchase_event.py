"""Integration tests for Scout purchase event endpoint — COMP-017."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.backend.main import app
from src.backend.models.purchase_event import EnrichedContext, GeoPoint, PurchaseEventPayload


def make_valid_payload(**kwargs):
    defaults = {
        "event_id": "evt-integration-001",
        "member_id": "M001",
        "store_id": "TH-KING-001",
        "store_name": "Tim Hortons - King Street",
        "store_type": "partner",
        "partner_brand": "tim_hortons",
        "amount": 12.50,
        "is_refund": False,
        "location": {"lat": 43.65, "lon": -79.38},
        "category": "food_beverage",
        "timestamp": "2026-03-27T14:00:00Z",
    }
    defaults.update(kwargs)
    return defaults


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.mark.integration
class TestPurchaseEventEndpoint:
    async def test_valid_payload_returns_202(self, client):
        with patch("src.backend.api.scout.get_purchase_event_handler") as mock_factory:
            mock_handler = MagicMock()
            mock_handler.handle = AsyncMock(return_value=None)  # Feature disabled
            mock_factory.return_value = mock_handler

            response = await client.post(
                "/api/scout/purchase-event",
                json=make_valid_payload(),
            )

        assert response.status_code == 202

    async def test_refund_event_returns_400(self, client):
        response = await client.post(
            "/api/scout/purchase-event",
            json=make_valid_payload(is_refund=True),
        )
        assert response.status_code == 400
        data = response.json()
        assert "refund" in data["detail"].lower()

    async def test_missing_member_id_returns_422(self, client):
        payload = make_valid_payload()
        del payload["member_id"]
        response = await client.post(
            "/api/scout/purchase-event",
            json=payload,
        )
        assert response.status_code == 422

    async def test_purchase_trigger_disabled_returns_202_no_offer(self, client):
        """When PURCHASE_TRIGGER_ENABLED=False, event is accepted but no offer generated."""
        with patch("src.backend.api.scout.get_purchase_event_handler") as mock_factory:
            mock_handler = MagicMock()
            # Handler returns None = feature disabled
            mock_handler.handle = AsyncMock(return_value=None)
            mock_factory.return_value = mock_handler

            response = await client.post(
                "/api/scout/purchase-event",
                json=make_valid_payload(),
            )

        assert response.status_code == 202
        data = response.json()
        assert data["offer_generated"] is False

    async def test_zero_amount_returns_400(self, client):
        # amount > 0 enforced by Pydantic
        payload = make_valid_payload(amount=0)
        response = await client.post(
            "/api/scout/purchase-event",
            json=payload,
        )
        assert response.status_code == 422  # Pydantic validation
