"""Integration tests for Designer API routes — COMP-008."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.backend.main import app
from src.backend.models.offer_brief import OfferBrief, OfferStatus, RiskSeverity

FIXTURES = json.loads(
    (Path(__file__).parents[3] / "fixtures/offer_brief_responses.json").read_text()
)

# JWT tokens for test use
MARKETING_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyLTEiLCJyb2xlIjoibWFya2V0aW5nIiwiZXhwIjo5OTk5OTk5OTk5fQ.FHJvWL4yJJxJNHI_placeholder"
ANALYST_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyLTIiLCJyb2xlIjoiYW5hbHlzdCIsImV4cCI6OTk5OTk5OTk5OX0.placeholder"


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
def mock_claude_service():
    """Mock Claude API service to avoid real API calls."""
    valid_offer = OfferBrief(**FIXTURES["valid_marketer_offer"])

    with patch("src.backend.api.designer.get_claude_service") as mock_factory:
        mock_service = MagicMock()
        mock_service.generate_from_objective = AsyncMock(return_value=valid_offer)
        mock_factory.return_value = mock_service
        yield mock_service


@pytest.fixture
def mock_fraud_service_safe():
    """Mock fraud service that always returns safe result."""
    from src.backend.models.offer_brief import FraudCheckResult, RiskFlags

    safe_result = FraudCheckResult(
        severity=RiskSeverity.low,
        flags=RiskFlags(
            over_discounting=False,
            cannibalization=False,
            frequency_abuse=False,
            offer_stacking=False,
            severity=RiskSeverity.low,
            warnings=[],
        ),
        warnings=[],
        blocked=False,
    )

    with patch("src.backend.api.designer.get_fraud_service") as mock_factory:
        mock_service = MagicMock()
        mock_service.validate = MagicMock(return_value=safe_result)
        mock_factory.return_value = mock_service
        yield mock_service


@pytest.mark.integration
class TestGenerateEndpoint:
    async def test_generate_offer_201_with_valid_objective(
        self, client, mock_claude_service, mock_fraud_service_safe
    ):
        with patch("src.backend.api.designer.get_audit_service"):
            with patch(
                "src.backend.core.security._decode_token",
                return_value={"sub": "user-1", "role": "marketing"},
            ):
                response = await client.post(
                    "/api/designer/generate",
                    json={
                        "objective": "Reactivate lapsed high-value members with winter sports gear offer"
                    },
                    headers={"Authorization": "Bearer test-token"},
                )

        assert response.status_code == 201
        data = response.json()
        assert "offer_id" in data
        assert data["trigger_type"] == "marketer_initiated"

    async def test_generate_returns_400_for_short_objective(self, client):
        with patch(
            "src.backend.core.security._decode_token",
            return_value={"sub": "user-1", "role": "marketing"},
        ):
            response = await client.post(
                "/api/designer/generate",
                json={"objective": "too short"},
                headers={"Authorization": "Bearer test-token"},
            )

        assert response.status_code == 422  # Pydantic validation error

    async def test_generate_returns_401_without_token(self, client):
        response = await client.post(
            "/api/designer/generate",
            json={"objective": "Reactivate lapsed high-value members"},
        )
        assert response.status_code == 401  # No bearer scheme = 401 (FastAPI 0.135+)

    async def test_generate_returns_403_for_wrong_role(self, client):
        with patch(
            "src.backend.core.security._decode_token",
            return_value={"sub": "user-2", "role": "analyst"},
        ):
            response = await client.post(
                "/api/designer/generate",
                json={
                    "objective": "Reactivate lapsed high-value members with winter sports gear offer"
                },
                headers={"Authorization": "Bearer analyst-token"},
            )

        assert response.status_code == 403

    async def test_generate_returns_422_when_fraud_critical(
        self, client, mock_claude_service
    ):
        from src.backend.models.offer_brief import FraudCheckResult, RiskFlags

        critical_result = FraudCheckResult(
            severity=RiskSeverity.critical,
            flags=RiskFlags(
                over_discounting=True,
                cannibalization=False,
                frequency_abuse=False,
                offer_stacking=False,
                severity=RiskSeverity.critical,
                warnings=["Discount of 40% exceeds threshold"],
            ),
            warnings=["Discount of 40% exceeds threshold"],
            blocked=True,
        )

        with patch("src.backend.api.designer.get_fraud_service") as mock_factory:
            mock_service = MagicMock()
            mock_service.validate = MagicMock(return_value=critical_result)
            mock_factory.return_value = mock_service

            with patch("src.backend.api.designer.get_audit_service"):
                with patch(
                    "src.backend.core.security._decode_token",
                    return_value={"sub": "user-1", "role": "marketing"},
                ):
                    response = await client.post(
                        "/api/designer/generate",
                        json={
                            "objective": "Massive 40% discount to clear all remaining winter inventory"
                        },
                        headers={"Authorization": "Bearer test-token"},
                    )

        assert response.status_code == 422
        data = response.json()
        assert data["detail"]["error"] == "FraudBlocked"


@pytest.mark.integration
class TestSuggestionsEndpoint:
    async def test_suggestions_returns_list(self, client):
        from src.backend.api.deps import get_inventory_service
        from src.backend.models.offer_brief import InventorySuggestion

        mock_service = MagicMock()
        mock_service.get_suggestions = MagicMock(
            return_value=[
                InventorySuggestion(
                    product_id="P001",
                    product_name="Winter Jacket",
                    category="outerwear",
                    store="Sport Chek",
                    units_in_stock=620,
                    urgency="high",
                    suggested_objective="Clear Winter Jacket overstock — 620 units in stock",
                )
            ]
        )

        # Use app.dependency_overrides so FastAPI uses the mock for this request
        app.dependency_overrides[get_inventory_service] = lambda: mock_service
        try:
            with patch(
                "src.backend.core.security._decode_token",
                return_value={"sub": "user-1", "role": "marketing"},
            ):
                response = await client.get(
                    "/api/designer/suggestions",
                    headers={"Authorization": "Bearer test-token"},
                )
        finally:
            app.dependency_overrides.pop(get_inventory_service, None)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
