"""Unit tests for FraudCheckService — COMP-006."""

import json
from pathlib import Path

import pytest

from src.backend.models.offer_brief import OfferBrief, RiskSeverity
from src.backend.services.fraud_check_service import FraudCheckService

FIXTURES = json.loads(
    (Path(__file__).parents[3] / "fixtures/offer_brief_responses.json").read_text()
)


def make_offer(construct_type: str, construct_value: float, **overrides) -> OfferBrief:
    data = {**FIXTURES["valid_marketer_offer"]}
    data["construct"] = {
        "type": construct_type,
        "value": construct_value,
        "description": f"Test construct: {construct_type} {construct_value}",
    }
    data.update(overrides)
    return OfferBrief(**data)


class TestOverDiscounting:
    def test_discount_above_30_pct_is_critical(self):
        service = FraudCheckService()
        offer = make_offer("discount", 35.0)
        result = service.validate(offer, member_id="M001")
        assert result.flags.over_discounting is True
        assert result.severity == RiskSeverity.critical
        assert result.blocked is True

    def test_discount_at_30_pct_is_not_flagged(self):
        """30% is the boundary — exactly 30% should NOT be flagged (threshold is ABOVE 30)."""
        service = FraudCheckService()
        offer = make_offer("discount", 30.0)
        result = service.validate(offer, member_id="M001")
        assert result.flags.over_discounting is False

    def test_discount_below_30_pct_is_low(self):
        service = FraudCheckService()
        offer = make_offer("discount", 20.0)
        result = service.validate(offer, member_id="M001")
        assert result.flags.over_discounting is False
        assert result.severity == RiskSeverity.low
        assert result.blocked is False

    def test_points_multiplier_not_flagged_as_over_discounting(self):
        """Points multiplier type should not trigger over_discounting check."""
        service = FraudCheckService()
        offer = make_offer("points_multiplier", 50.0)  # value=50 but not a discount
        result = service.validate(offer, member_id="M001")
        assert result.flags.over_discounting is False


class TestOfferStacking:
    def test_offer_stacking_above_threshold_is_critical(self):
        service = FraudCheckService()
        offer = make_offer("points_multiplier", 3.0)
        # Record 5 active offers for member (threshold raised to 5)
        for _ in range(5):
            service.record_active_offer("M_STACK")
        result = service.validate(offer, member_id="M_STACK")
        assert result.flags.offer_stacking is True
        assert result.severity == RiskSeverity.critical
        assert result.blocked is True

    def test_offer_stacking_below_threshold_passes(self):
        service = FraudCheckService()
        offer = make_offer("points_multiplier", 3.0)
        for _ in range(4):
            service.record_active_offer("M_LOW")  # 4 active — below threshold of 5
        result = service.validate(offer, member_id="M_LOW")
        assert result.flags.offer_stacking is False


class TestBlockedFlag:
    def test_blocked_is_true_only_for_critical(self):
        service = FraudCheckService()
        # Critical
        critical_offer = make_offer("discount", 40.0)
        critical_result = service.validate(critical_offer, member_id="M001")
        assert critical_result.blocked is True

        # Low severity
        safe_offer = make_offer("points_multiplier", 3.0)
        safe_result = service.validate(safe_offer, member_id="M001")
        assert safe_result.blocked is False

    def test_valid_offer_from_fixture_passes_fraud_check(self):
        service = FraudCheckService()
        offer = OfferBrief(**FIXTURES["valid_marketer_offer"])
        result = service.validate(offer, member_id="M001")
        assert result.blocked is False
        assert result.severity == RiskSeverity.low
