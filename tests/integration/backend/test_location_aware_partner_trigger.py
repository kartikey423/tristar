"""Integration tests for location-aware partner trigger intelligence.

Tests:
- AC-LOC-01: Hill Station + Long Weekend → Outdoor/Camping category
- AC-LOC-02: Cottage/Lakes → Marine/Fishing category
- AC-LOC-03: Highway → Automotive category
- AC-LOC-04: Urban (default) → default fallback category
- AC-LOC-05: Store name keyword overrides GPS coordinates
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.backend.models.partner_event import PartnerPurchaseEvent
from src.backend.models.purchase_event import GeoPoint
from src.backend.services.canadian_holiday_service import CanadianHolidayService, TimeType
from src.backend.services.fraud_check_service import FraudCheckService
from src.backend.services.hub_api_client import HubApiClient
from src.backend.services.location_zone_service import LocationZone, LocationZoneService
from src.backend.services.partner_trigger_service import PartnerTriggerService
from src.backend.models.offer_brief import OfferStatus, RiskSeverity


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
def location_zone_service() -> LocationZoneService:
    return LocationZoneService()


@pytest.fixture
def holiday_service() -> CanadianHolidayService:
    return CanadianHolidayService()


@pytest.fixture
def partner_service(
    mock_hub_client, mock_fraud_service, location_zone_service, holiday_service
) -> PartnerTriggerService:
    return PartnerTriggerService(
        hub_client=mock_hub_client,
        fraud_service=mock_fraud_service,
        location_zone_service=location_zone_service,
        holiday_service=holiday_service,
    )


# ─── AC-LOC-01: Hill Station + Long Weekend → Outdoor/Camping ────────────────


@pytest.mark.asyncio
@pytest.mark.integration
async def test_hill_station_long_weekend_trigger(partner_service, mock_hub_client):
    """AC-LOC-01: Hill Station + Long Weekend → Outdoor/Camping category."""
    event = PartnerPurchaseEvent(
        event_id="test-blue-mountain-001",
        partner_id="tim_hortons",
        partner_name="Tim Hortons - Blue Mountain",
        purchase_amount=12.50,
        purchase_category="coffee",
        member_id="M-test-999",
        timestamp=datetime(2026, 4, 3, 10, 30, tzinfo=timezone.utc),  # Good Friday 2026
        location=GeoPoint(lat=44.5, lon=-80.3),  # Blue Mountain coordinates
        store_name="Tim Hortons - Blue Mountain",
    )

    # Trigger partner event
    result = await partner_service.classify_and_generate(event)

    # Assertions
    assert result is not None, "Offer should be generated"
    assert result.status == OfferStatus.active, "Offer should be active"
    assert result.trigger_type.value == "partner_triggered"
    assert result.valid_until is not None, "valid_until must be set for partner_triggered"

    # Check that outdoor/camping category is in segment criteria or objective
    segment_criteria_str = " ".join(result.segment.criteria).lower()
    objective_lower = result.objective.lower()
    assert (
        "outdoor" in segment_criteria_str
        or "camping" in segment_criteria_str
        or "outdoor" in objective_lower
        or "camping" in objective_lower
    ), f"Expected outdoor/camping category, got criteria={result.segment.criteria}, objective={result.objective}"

    # Verify saved to Hub
    mock_hub_client.save_offer.assert_called_once()


# ─── AC-LOC-02: Cottage/Lakes → Marine/Fishing ───────────────────────────────


@pytest.mark.asyncio
@pytest.mark.integration
async def test_cottage_lakes_trigger(partner_service):
    """AC-LOC-02: Cottage/Lakes location → Marine/Fishing category."""
    event = PartnerPurchaseEvent(
        event_id="test-muskoka-001",
        partner_id="tim_hortons",
        partner_name="Tim Hortons - Gravenhurst",
        purchase_amount=15.00,
        purchase_category="coffee",
        member_id="M-test-888",
        timestamp=datetime(2026, 7, 5, 9, 0, tzinfo=timezone.utc),  # Weekend
        location=GeoPoint(lat=45.1, lon=-79.4),  # Muskoka region
        store_name="Tim Hortons - Gravenhurst",
    )

    result = await partner_service.classify_and_generate(event)

    assert result is not None
    assert result.status == OfferStatus.active

    # Check for marine/fishing category
    segment_criteria_str = " ".join(result.segment.criteria).lower()
    objective_lower = result.objective.lower()
    assert (
        "marine" in segment_criteria_str
        or "fishing" in segment_criteria_str
        or "marine" in objective_lower
        or "fishing" in objective_lower
    ), f"Expected marine/fishing category for cottage/lakes zone"


# ─── AC-LOC-03: Highway → Automotive ──────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.integration
async def test_highway_trigger(partner_service):
    """AC-LOC-03: Highway corridor → Automotive category."""
    event = PartnerPurchaseEvent(
        event_id="test-highway-001",
        partner_id="tim_hortons",
        partner_name="Tim Hortons - Highway 400",
        purchase_amount=10.00,
        purchase_category="coffee",
        member_id="M-test-777",
        timestamp=datetime(2026, 5, 10, 14, 30, tzinfo=timezone.utc),  # Weekday
        location=GeoPoint(lat=44.0, lon=-79.5),  # Highway 400 corridor
        store_name="Tim Hortons - Highway 400",
    )

    result = await partner_service.classify_and_generate(event)

    assert result is not None
    assert result.status == OfferStatus.active

    # Check for automotive category
    segment_criteria_str = " ".join(result.segment.criteria).lower()
    objective_lower = result.objective.lower()
    assert (
        "automotive" in segment_criteria_str
        or "automotive" in objective_lower
    ), f"Expected automotive category for highway zone"


# ─── AC-LOC-04: Urban (default) ───────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.integration
async def test_urban_default_trigger(partner_service):
    """AC-LOC-04: Urban location → default category."""
    event = PartnerPurchaseEvent(
        event_id="test-urban-001",
        partner_id="tim_hortons",
        partner_name="Tim Hortons - Downtown Toronto",
        purchase_amount=8.50,
        purchase_category="coffee",
        member_id="M-test-666",
        timestamp=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),  # Weekday
        location=GeoPoint(lat=43.65, lon=-79.38),  # Toronto downtown
        store_name="Tim Hortons - King St",
    )

    result = await partner_service.classify_and_generate(event)

    assert result is not None
    assert result.status == OfferStatus.active


# ─── AC-LOC-05: Store name keyword overrides GPS ─────────────────────────────


@pytest.mark.asyncio
@pytest.mark.integration
async def test_store_name_overrides_coordinates(location_zone_service):
    """AC-LOC-05: Store name 'Blue Mountain' overrides urban coordinates."""
    # Urban coordinates but store name indicates Hill Station
    zone = location_zone_service.classify(
        location=GeoPoint(lat=43.65, lon=-79.38),  # Toronto coords
        store_name="Tim Hortons - Blue Mountain"
    )

    assert zone == LocationZone.hill_station, "Store name should override coordinates"


# ─── Time Type Detection Tests ────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.integration
async def test_long_weekend_detection(holiday_service):
    """Good Friday 2026 (April 3) should be detected as long_weekend."""
    time_type = holiday_service.get_time_type(datetime(2026, 4, 3, 10, 0, tzinfo=timezone.utc))
    assert time_type == TimeType.long_weekend


@pytest.mark.asyncio
@pytest.mark.integration
async def test_regular_weekday_detection(holiday_service):
    """Regular Tuesday should be detected as weekday."""
    time_type = holiday_service.get_time_type(datetime(2026, 6, 9, 10, 0, tzinfo=timezone.utc))  # Tuesday
    assert time_type == TimeType.weekday


@pytest.mark.asyncio
@pytest.mark.integration
async def test_regular_weekend_detection(holiday_service):
    """Regular Saturday (non-holiday) should be detected as weekend."""
    time_type = holiday_service.get_time_type(datetime(2026, 6, 13, 10, 0, tzinfo=timezone.utc))  # Saturday
    assert time_type == TimeType.weekend
