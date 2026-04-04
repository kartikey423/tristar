"""Integration tests: Designer auto-save to Hub flow — COMP-006.

Tests REQ-005 (auto-save on generate) and F-001 (approve via update, not save).
"""

import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.backend.main import app
from src.backend.models.offer_brief import OfferBrief, OfferStatus, RiskSeverity

FIXTURES = json.loads(
    (Path(__file__).parents[3] / "fixtures/offer_brief_responses.json").read_text()
)

MARKETING_HEADERS = {"Authorization": "Bearer marketing-token"}
SYSTEM_HEADERS = {"Authorization": "Bearer system-token"}

MARKETING_TOKEN_PATCH = patch(
    "src.backend.core.security._decode_token",
    return_value={"sub": "user-1", "role": "marketing"},
)
SYSTEM_TOKEN_PATCH = patch(
    "src.backend.core.security._decode_token",
    return_value={"sub": "scout-service", "role": "system"},
)


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
def mock_claude_safe():
    """Mock Claude returning a fixed valid offer."""
    valid_offer = OfferBrief(**deepcopy(FIXTURES["valid_marketer_offer"]))

    with patch("src.backend.api.designer.get_claude_service") as mock_factory:
        mock_service = MagicMock()
        mock_service.generate_from_objective = AsyncMock(return_value=valid_offer)
        mock_factory.return_value = mock_service
        yield mock_service, valid_offer


@pytest.fixture
def mock_fraud_safe():
    """Mock fraud service returning safe result — patches via class method to bypass lru_cache."""
    from src.backend.models.offer_brief import FraudCheckResult, RiskFlags
    from src.backend.services.fraud_check_service import FraudCheckService

    safe = FraudCheckResult(
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

    with patch.object(FraudCheckService, "validate", return_value=safe):
        yield


@pytest.mark.integration
class TestDesignerHubIntegration:
    async def test_generate_auto_saves_to_hub(
        self, client, mock_claude_safe, mock_fraud_safe
    ):
        """REQ-005 / AC-018: POST /generate must auto-save draft to Hub."""
        mock_service, valid_offer = mock_claude_safe

        with patch("src.backend.api.designer.get_audit_service"):
            with MARKETING_TOKEN_PATCH:
                response = await client.post(
                    "/api/designer/generate",
                    json={"objective": "Reactivate lapsed high-value members with winter sports"},
                    headers=MARKETING_HEADERS,
                )

        assert response.status_code == 201
        offer_id = response.json()["offer_id"]

        # Verify offer is now in Hub
        with SYSTEM_TOKEN_PATCH:
            hub_response = await client.get(
                f"/api/hub/offers/{offer_id}",
                headers=SYSTEM_HEADERS,
            )
        assert hub_response.status_code == 200
        assert hub_response.json()["status"] == "draft"

    async def test_generate_fraud_blocked_not_saved_to_hub(self, client, mock_claude_safe):
        """AC-019: When fraud is critical, offer must NOT be saved to Hub."""
        from src.backend.models.offer_brief import FraudCheckResult, RiskFlags
        from src.backend.services.fraud_check_service import FraudCheckService

        _mock_service, _valid_offer = mock_claude_safe
        critical = FraudCheckResult(
            severity=RiskSeverity.critical,
            flags=RiskFlags(
                over_discounting=True,
                cannibalization=False,
                frequency_abuse=False,
                offer_stacking=False,
                severity=RiskSeverity.critical,
                warnings=["Discount exceeds 30%"],
            ),
            warnings=["Discount exceeds 30%"],
            blocked=True,
        )

        # Patch method directly on class — works regardless of lru_cache on the factory
        with patch.object(FraudCheckService, "validate", return_value=critical):
            with patch("src.backend.api.designer.get_audit_service"):
                with MARKETING_TOKEN_PATCH:
                    response = await client.post(
                        "/api/designer/generate",
                        json={"objective": "Massive discount to clear all winter inventory now"},
                        headers=MARKETING_HEADERS,
                    )

        assert response.status_code == 422

        # Hub should be empty — fraud-blocked offer was not saved
        with SYSTEM_TOKEN_PATCH:
            list_response = await client.get("/api/hub/offers", headers=SYSTEM_HEADERS)
        assert list_response.json()["count"] == 0

    async def test_approve_transitions_not_rejects_duplicate(
        self, client, mock_claude_safe, mock_fraud_safe
    ):
        """AC-020 / F-001: POST /approve uses hub_store.update(), not save() — no 409 conflict.

        Flow: POST /generate (auto-saves as draft) → POST /approve (updates to approved)
        Should return 200, NOT 409.
        """
        mock_service, valid_offer = mock_claude_safe

        # Step 1: Generate (auto-saves as draft to Hub)
        with patch("src.backend.api.designer.get_audit_service"):
            with MARKETING_TOKEN_PATCH:
                gen_response = await client.post(
                    "/api/designer/generate",
                    json={"objective": "Reactivate lapsed high-value members with winter sports"},
                    headers=MARKETING_HEADERS,
                )
        assert gen_response.status_code == 201
        offer_data = gen_response.json()
        offer_id = offer_data["offer_id"]

        # Step 2: Approve (should call hub_store.update, not save)
        with patch("src.backend.api.designer.get_audit_service"):
            with MARKETING_TOKEN_PATCH:
                approve_response = await client.post(
                    f"/api/designer/approve/{offer_id}",
                    json=offer_data,
                    headers=MARKETING_HEADERS,
                )

        assert approve_response.status_code == 200, (
            f"Expected 200 but got {approve_response.status_code}: {approve_response.json()}"
        )
        assert approve_response.json()["status"] == "approved"
