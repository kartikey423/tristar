"""Unit tests for the 75/25 Triangle Rewards payment split enforcement.

Covers:
- AC-02: 75% points + 25% cash → accepted
- AC-03: 80% points + 20% cash → rejected (HTTP 422)
- AC-04: No payment_split → backward compatible (no enforcement)
- Boundary: exactly 75% points → accepted
- Boundary: 75.001% points → rejected
- AC-01: OfferBrief model accepts payment_split field
"""

from __future__ import annotations

import pytest

from src.backend.models.offer_brief import (
    Channel,
    ChannelType,
    Construct,
    KPIs,
    OfferBrief,
    OfferStatus,
    PaymentSplit,
    RiskFlags,
    RiskSeverity,
    Segment,
    TriggerType,
)
from src.backend.models.partner_event import RedemptionRequest, RedemptionSplitError
from src.backend.services.redemption_enforcement_service import RedemptionEnforcementService


# ─── Fixtures ────────────────────────────────────────────────────────────────


def _make_offer(payment_split: PaymentSplit | None = None) -> OfferBrief:
    """Create a minimal valid OfferBrief with optional payment_split."""
    from datetime import datetime, timedelta, timezone

    return OfferBrief(
        offer_id="test-offer-redemption-001",
        objective="Test offer for redemption logic validation",
        segment=Segment(
            name="test_segment",
            definition="Test members",
            estimated_size=100,
            criteria=["test"],
        ),
        construct=Construct(
            type="percentage_off",
            value=20.0,
            description="20% off",
            payment_split=payment_split,
        ),
        channels=[Channel(channel_type=ChannelType.push, priority=1)],
        kpis=KPIs(expected_redemption_rate=0.1, expected_uplift_pct=10.0),
        risk_flags=RiskFlags(
            over_discounting=False,
            cannibalization=False,
            frequency_abuse=False,
            offer_stacking=False,
            severity=RiskSeverity.low,
            warnings=[],
        ),
        status=OfferStatus.approved,
        trigger_type=TriggerType.marketer_initiated,
    )


@pytest.fixture
def service() -> RedemptionEnforcementService:
    return RedemptionEnforcementService()


@pytest.fixture
def offer_with_split() -> OfferBrief:
    return _make_offer(payment_split=PaymentSplit(points_max_pct=75.0, cash_min_pct=25.0))


@pytest.fixture
def offer_without_split() -> OfferBrief:
    return _make_offer(payment_split=None)


# ─── AC-01: OfferBrief model accepts payment_split ────────────────────────────


def test_offer_brief_accepts_payment_split_field():
    """AC-01: OfferBrief model with payment_split validates without error."""
    offer = _make_offer(payment_split=PaymentSplit(points_max_pct=75.0, cash_min_pct=25.0))
    assert offer.construct.payment_split is not None
    assert offer.construct.payment_split.points_max_pct == 75.0
    assert offer.construct.payment_split.cash_min_pct == 25.0


def test_offer_brief_accepts_no_payment_split():
    """AC-04: OfferBrief without payment_split is valid (backward compatibility)."""
    offer = _make_offer(payment_split=None)
    assert offer.construct.payment_split is None


# ─── AC-02: Valid 75/25 split accepted ───────────────────────────────────────


def test_valid_75_25_split_accepted(service, offer_with_split):
    """AC-02: Exactly 75% points + 25% cash is accepted."""
    redemption = RedemptionRequest(offer_id="test-offer-redemption-001", points_pct=75.0, cash_pct=25.0)
    service.validate_payment_split(offer_with_split, redemption)  # Should not raise


def test_valid_50_50_split_accepted(service, offer_with_split):
    """50% points + 50% cash is below the 75% max — accepted."""
    redemption = RedemptionRequest(offer_id="test-offer-redemption-001", points_pct=50.0, cash_pct=50.0)
    service.validate_payment_split(offer_with_split, redemption)  # Should not raise


def test_zero_points_accepted(service, offer_with_split):
    """0% points + 100% cash is valid — fully paid by cash."""
    redemption = RedemptionRequest(offer_id="test-offer-redemption-001", points_pct=0.0, cash_pct=100.0)
    service.validate_payment_split(offer_with_split, redemption)  # Should not raise


# ─── AC-03: Invalid 80/20 split rejected ─────────────────────────────────────


def test_invalid_80_20_split_rejected(service, offer_with_split):
    """AC-03: 80% points exceeds 75% max — raises RedemptionSplitError."""
    redemption = RedemptionRequest(offer_id="test-offer-redemption-001", points_pct=80.0, cash_pct=20.0)
    with pytest.raises(RedemptionSplitError) as exc_info:
        service.validate_payment_split(offer_with_split, redemption)
    assert exc_info.value.points_pct == 80.0
    assert exc_info.value.max_pct == 75.0


def test_100_points_rejected(service, offer_with_split):
    """100% points — fully blocked by 75% maximum."""
    redemption = RedemptionRequest(offer_id="test-offer-redemption-001", points_pct=100.0, cash_pct=0.0)
    with pytest.raises(RedemptionSplitError):
        service.validate_payment_split(offer_with_split, redemption)


# ─── Boundary conditions ─────────────────────────────────────────────────────


def test_boundary_exactly_75_accepted(service, offer_with_split):
    """Boundary: exactly 75% points is the maximum allowed — accepted."""
    redemption = RedemptionRequest(offer_id="test-offer-redemption-001", points_pct=75.0, cash_pct=25.0)
    service.validate_payment_split(offer_with_split, redemption)  # Should not raise


def test_boundary_75_001_rejected(service, offer_with_split):
    """Boundary: 75.001% points exceeds maximum — rejected."""
    redemption = RedemptionRequest(offer_id="test-offer-redemption-001", points_pct=75.001, cash_pct=24.999)
    with pytest.raises(RedemptionSplitError):
        service.validate_payment_split(offer_with_split, redemption)


# ─── AC-04: Backward compatibility — no payment_split ────────────────────────


def test_no_payment_split_backward_compatible(service, offer_without_split):
    """AC-04: When offer has no payment_split, any redemption is accepted (legacy offers)."""
    # Even 100% points is allowed for legacy offers with no payment_split
    redemption = RedemptionRequest(offer_id="test-offer-redemption-001", points_pct=100.0, cash_pct=0.0)
    service.validate_payment_split(offer_without_split, redemption)  # Should not raise


def test_no_payment_split_partial_split_accepted(service, offer_without_split):
    """Legacy offers with no payment_split accept any valid split."""
    redemption = RedemptionRequest(offer_id="test-offer-redemption-001", points_pct=90.0, cash_pct=10.0)
    service.validate_payment_split(offer_without_split, redemption)  # Should not raise


# ─── PaymentSplit model validation ───────────────────────────────────────────


def test_payment_split_must_sum_to_100():
    """PaymentSplit raises ValueError when fields don't sum to 100."""
    with pytest.raises(Exception):
        PaymentSplit(points_max_pct=70.0, cash_min_pct=20.0)  # 70+20=90 ≠ 100


def test_payment_split_valid_construction():
    """PaymentSplit validates when fields sum to 100."""
    ps = PaymentSplit(points_max_pct=75.0, cash_min_pct=25.0)
    assert ps.points_max_pct == 75.0
    assert ps.cash_min_pct == 25.0


# ─── RedemptionRequest model validation ──────────────────────────────────────


def test_redemption_request_must_sum_to_100():
    """RedemptionRequest raises ValueError when points_pct + cash_pct ≠ 100."""
    with pytest.raises(Exception):
        RedemptionRequest(offer_id="x", points_pct=80.0, cash_pct=10.0)


def test_redemption_request_valid():
    """RedemptionRequest validates when split sums to 100."""
    req = RedemptionRequest(offer_id="x", points_pct=75.0, cash_pct=25.0)
    assert req.points_pct == 75.0
