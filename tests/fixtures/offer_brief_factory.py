"""Factory functions for creating test OfferBrief instances."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from src.backend.models.offer_brief import (
    Channel,
    Construct,
    KPIs,
    OfferBrief,
    OfferStatus,
    RiskFlags,
    RiskSeverity,
    Segment,
    TriggerType,
)


def make_offer_brief(
    offer_id: Optional[str] = None,
    status: str = "draft",
    trigger_type: str = "marketer_initiated",
    created_at: Optional[datetime] = None,
) -> OfferBrief:
    """Create a minimal valid OfferBrief for unit testing."""
    return OfferBrief(
        offer_id=offer_id or str(uuid.uuid4()),
        objective="Reactivate lapsed high-value members with winter sports gear offer",
        segment=Segment(
            name="lapsed_high_value",
            definition="Members with >$500 lifetime spend inactive 90+ days",
            estimated_size=12500,
            criteria=["high_value", "lapsed_90_days"],
        ),
        construct=Construct(
            type="points_multiplier",
            value=3,
            description="3x points on all purchases",
        ),
        channels=[Channel(channel_type="push", priority=1)],
        kpis=KPIs(expected_redemption_rate=0.15, expected_uplift_pct=25),
        risk_flags=RiskFlags(
            over_discounting=False,
            cannibalization=False,
            frequency_abuse=False,
            offer_stacking=False,
            severity=RiskSeverity.low,
            warnings=[],
        ),
        status=OfferStatus(status),
        trigger_type=TriggerType(trigger_type),
        created_at=created_at or datetime(2026, 3, 27, 10, 0, 0, tzinfo=timezone.utc),
    )


def make_purchase_offer(offer_id: Optional[str] = None) -> OfferBrief:
    """Create a purchase-triggered active offer (requires valid_until)."""
    return OfferBrief(
        offer_id=offer_id or str(uuid.uuid4()),
        objective="Personalized offer for purchase context",
        segment=Segment(
            name="recent_purchaser",
            definition="Member who just made a purchase",
            estimated_size=1,
            criteria=["recent_purchase"],
        ),
        construct=Construct(
            type="discount",
            value=10,
            description="10% off next purchase",
        ),
        channels=[Channel(channel_type="push", priority=1)],
        kpis=KPIs(expected_redemption_rate=0.20, expected_uplift_pct=15),
        risk_flags=RiskFlags(
            over_discounting=False,
            cannibalization=False,
            frequency_abuse=False,
            offer_stacking=False,
            severity=RiskSeverity.low,
            warnings=[],
        ),
        status=OfferStatus.active,
        trigger_type=TriggerType.purchase_triggered,
        created_at=datetime(2026, 3, 27, 10, 0, 0, tzinfo=timezone.utc),
        valid_until=datetime(2026, 3, 27, 14, 0, 0, tzinfo=timezone.utc),
    )
