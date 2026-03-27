"""Unit tests for OfferBrief Pydantic model — COMP-002."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.backend.models.offer_brief import (
    OfferBrief,
    OfferStatus,
    RiskFlags,
    RiskSeverity,
    TriggerType,
)

FIXTURES = json.loads(
    (Path(__file__).parents[3] / "fixtures/offer_brief_responses.json").read_text()
)


@pytest.fixture
def valid_offer_data():
    return FIXTURES["valid_marketer_offer"]


@pytest.fixture
def purchase_triggered_data():
    return FIXTURES["purchase_triggered_offer"]


class TestOfferBriefValidation:
    def test_valid_marketer_offer_validates(self, valid_offer_data):
        offer = OfferBrief(**valid_offer_data)
        assert offer.offer_id == "550e8400-e29b-41d4-a716-446655440000"
        assert offer.trigger_type == TriggerType.marketer_initiated
        assert offer.status == OfferStatus.draft

    def test_missing_offer_id_fails(self, valid_offer_data):
        del valid_offer_data["offer_id"]
        with pytest.raises(ValidationError) as exc_info:
            OfferBrief(**valid_offer_data)
        assert "offer_id" in str(exc_info.value)

    def test_objective_too_short_fails(self, valid_offer_data):
        valid_offer_data["objective"] = "short"
        with pytest.raises(ValidationError):
            OfferBrief(**valid_offer_data)

    def test_objective_too_long_fails(self, valid_offer_data):
        valid_offer_data["objective"] = "x" * 501
        with pytest.raises(ValidationError):
            OfferBrief(**valid_offer_data)

    def test_invalid_status_rejected(self, valid_offer_data):
        valid_offer_data["status"] = "pending"  # Not a valid OfferStatus
        with pytest.raises(ValidationError):
            OfferBrief(**valid_offer_data)

    def test_trigger_type_enum_validates(self, valid_offer_data):
        valid_offer_data["trigger_type"] = "purchase_triggered"
        offer = OfferBrief(**valid_offer_data)
        assert offer.trigger_type == TriggerType.purchase_triggered

    def test_invalid_trigger_type_rejected(self, valid_offer_data):
        valid_offer_data["trigger_type"] = "unknown_type"
        with pytest.raises(ValidationError):
            OfferBrief(**valid_offer_data)

    def test_empty_channels_fails(self, valid_offer_data):
        valid_offer_data["channels"] = []
        with pytest.raises(ValidationError):
            OfferBrief(**valid_offer_data)

    def test_purchase_triggered_requires_valid_until(self, valid_offer_data):
        """purchase_triggered offers must have valid_until set."""
        valid_offer_data["trigger_type"] = "purchase_triggered"
        valid_offer_data["status"] = "active"
        # No valid_until set
        with pytest.raises(ValidationError) as exc_info:
            OfferBrief(**valid_offer_data)
        assert "valid_until" in str(exc_info.value)

    def test_purchase_triggered_with_valid_until_validates(self, purchase_triggered_data):
        offer = OfferBrief(**purchase_triggered_data)
        assert offer.trigger_type == TriggerType.purchase_triggered
        assert offer.valid_until is not None
        assert offer.status == OfferStatus.active

    def test_marketer_initiated_without_valid_until_validates(self, valid_offer_data):
        """marketer_initiated offers do NOT need valid_until."""
        assert "valid_until" not in valid_offer_data or valid_offer_data.get("valid_until") is None
        offer = OfferBrief(**valid_offer_data)
        assert offer.valid_until is None


class TestRiskFlags:
    def test_risk_severity_values(self):
        assert RiskSeverity.low == "low"
        assert RiskSeverity.medium == "medium"
        assert RiskSeverity.critical == "critical"

    def test_risk_flags_with_warnings(self):
        flags = RiskFlags(
            over_discounting=True,
            cannibalization=False,
            frequency_abuse=False,
            offer_stacking=False,
            severity=RiskSeverity.critical,
            warnings=["Discount of 40% exceeds threshold"],
        )
        assert flags.over_discounting is True
        assert len(flags.warnings) == 1
