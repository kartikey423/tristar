"""Unit tests for PartnerTriggerService — Haiku classification and offer generation."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.backend.models.offer_brief import OfferStatus, RiskSeverity, TriggerType
from src.backend.models.partner_event import PartnerPurchaseEvent
from src.backend.services.fraud_check_service import FraudCheckService
from src.backend.services.hub_api_client import HubApiClient
from src.backend.services.canadian_holiday_service import CanadianHolidayService, TimeType
from src.backend.services.location_zone_service import LocationZone, LocationZoneService
from src.backend.services.partner_trigger_service import (
    PartnerTriggerService,
    _PARTNER_FALLBACK_CATEGORIES,
    _is_duplicate_partner_event,
    _partner_seen_events,
)


@pytest.fixture(autouse=True)
def clear_dedup_state():
    """Clear the dedup dict before each test to prevent cross-test pollution."""
    _partner_seen_events.clear()
    yield
    _partner_seen_events.clear()


@pytest.fixture
def mock_hub_client() -> MagicMock:
    client = MagicMock(spec=HubApiClient)
    client.save_offer = AsyncMock(return_value=None)
    return client


@pytest.fixture
def mock_fraud_service() -> MagicMock:
    from src.backend.models.offer_brief import FraudCheckResult, RiskFlags
    service = MagicMock(spec=FraudCheckService)
    service.validate.return_value = FraudCheckResult(
        severity=RiskSeverity.low,
        flags=RiskFlags(
            over_discounting=False, cannibalization=False,
            frequency_abuse=False, offer_stacking=False,
            severity=RiskSeverity.low, warnings=[],
        ),
        warnings=[],
        blocked=False,
    )
    return service


@pytest.fixture
def service(mock_hub_client, mock_fraud_service) -> PartnerTriggerService:
    svc = PartnerTriggerService(
        hub_client=mock_hub_client,
        fraud_service=mock_fraud_service,
        location_zone_service=LocationZoneService(),
        holiday_service=CanadianHolidayService(),
    )
    return svc


@pytest.fixture
def tim_hortons_event() -> PartnerPurchaseEvent:
    return PartnerPurchaseEvent(
        event_id="tims-test-001",
        partner_id="tim_hortons",
        partner_name="Tim Hortons",
        purchase_amount=8.50,
        purchase_category="coffee",
        member_id="M-12345",
        timestamp=datetime.now(timezone.utc),
    )


# ─── Deduplication ───────────────────────────────────────────────────────────


def test_is_duplicate_returns_false_first_time():
    """First time an event_id is seen → not a duplicate."""
    assert _is_duplicate_partner_event("new-event-001") is False


def test_is_duplicate_returns_true_second_time():
    """Second time the same event_id is seen → duplicate."""
    _is_duplicate_partner_event("dupe-event-001")
    assert _is_duplicate_partner_event("dupe-event-001") is True


def test_service_is_duplicate_delegates_correctly(service):
    """PartnerTriggerService.is_duplicate() wraps the module-level dedup check."""
    assert service.is_duplicate("fresh-event-abc") is False
    assert service.is_duplicate("fresh-event-abc") is True


# ─── Fallback category ────────────────────────────────────────────────────────


def test_fallback_category_tim_hortons(service):
    """Tim Hortons + Highway zone falls back to automotive_accessories."""
    assert service._fallback_category("tim_hortons", LocationZone.highway) == "automotive_accessories"


def test_fallback_category_westjet(service):
    """WestJet + Urban zone falls back to luggage."""
    assert service._fallback_category("westjet", LocationZone.urban) == "luggage"


def test_fallback_category_unknown_partner(service):
    """Unknown partner + Urban zone falls back to default category."""
    assert service._fallback_category("unknown_brand_xyz", LocationZone.urban) == "seasonal_promotions"


def test_fallback_always_returns_string(service):
    """Fallback never raises — always returns a non-empty string."""
    result = service._fallback_category("anything", LocationZone.urban)
    assert isinstance(result, str)
    assert len(result) > 0


# ─── Offer generation ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generated_offer_has_partner_triggered_type(service, tim_hortons_event):
    """Generated offer must have trigger_type=partner_triggered."""
    offer = await service._generate_offer(tim_hortons_event, "automotive_accessories")
    assert offer.trigger_type == TriggerType.partner_triggered


@pytest.mark.asyncio
async def test_generated_offer_has_valid_until_set(service, tim_hortons_event):
    """Generated offer must have valid_until set (required for partner_triggered)."""
    offer = await service._generate_offer(tim_hortons_event, "automotive_accessories")
    assert offer.valid_until is not None


@pytest.mark.asyncio
async def test_generated_offer_has_active_status(service, tim_hortons_event):
    """Generated offer must be status=active for immediate delivery."""
    offer = await service._generate_offer(tim_hortons_event, "automotive_accessories")
    assert offer.status == OfferStatus.active


@pytest.mark.asyncio
async def test_generated_offer_has_payment_split(service, tim_hortons_event):
    """Generated offer must have payment_split={75, 25}."""
    offer = await service._generate_offer(tim_hortons_event, "automotive_accessories")
    assert offer.construct.payment_split is not None
    assert offer.construct.payment_split.points_max_pct == 75.0
    assert offer.construct.payment_split.cash_min_pct == 25.0


@pytest.mark.asyncio
async def test_generated_offer_discount_below_fraud_threshold(service, tim_hortons_event):
    """Offer discount should be ≤ 30% to pass fraud detection."""
    offer = await service._generate_offer(tim_hortons_event, "automotive_accessories")
    assert offer.construct.value <= 30.0


# ─── Haiku failure fallback ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_haiku_failure_uses_fallback_category(service, tim_hortons_event):
    """When Haiku raises an exception, _classify_with_haiku returns fallback category."""
    with patch.object(service._claude.messages, 'create', side_effect=Exception("API timeout")):
        category = await service._classify_with_haiku(tim_hortons_event, LocationZone.highway, TimeType.weekday)
    assert category == "automotive_accessories"  # Tim Hortons + highway fallback


@pytest.mark.asyncio
async def test_haiku_empty_response_uses_fallback(service, tim_hortons_event):
    """When Haiku returns empty text, fallback is used."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="")]
    with patch("asyncio.to_thread", AsyncMock(return_value=mock_response)):
        category = await service._classify_with_haiku(tim_hortons_event, LocationZone.highway, TimeType.weekday)
    assert category == "automotive_accessories"  # Tim Hortons + highway fallback


# ─── Fraud check blocking ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fraud_check_blocks_critical_offer(service, mock_fraud_service, tim_hortons_event, mock_hub_client):
    """When fraud check returns critical severity, offer is NOT saved to Hub."""
    from src.backend.models.offer_brief import FraudCheckResult, RiskFlags

    mock_fraud_service.validate.return_value = FraudCheckResult(
        severity=RiskSeverity.critical,
        flags=RiskFlags(
            over_discounting=True, cannibalization=False,
            frequency_abuse=False, offer_stacking=False,
            severity=RiskSeverity.critical, warnings=["Over-discounting detected"],
        ),
        warnings=["Over-discounting detected"],
        blocked=True,
    )

    with patch.object(service, '_classify_with_haiku', AsyncMock(return_value="automotive_accessories")):
        result = await service.classify_and_generate(tim_hortons_event)

    assert result is None
    mock_hub_client.save_offer.assert_not_called()


@pytest.mark.asyncio
async def test_low_fraud_risk_offer_saved_to_hub(service, mock_fraud_service, tim_hortons_event, mock_hub_client):
    """When fraud check returns low severity, offer IS saved to Hub."""
    with patch.object(service, '_classify_with_haiku', AsyncMock(return_value="automotive_accessories")):
        result = await service.classify_and_generate(tim_hortons_event)

    assert result is not None
    mock_hub_client.save_offer.assert_called_once()
