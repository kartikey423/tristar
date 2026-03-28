"""Mock member profile store — 5 hardcoded demo personas for ContextDashboard.

Returns None for unknown member IDs (graceful degradation per REQ-004).
Profiles are designed to produce reliably different Claude scoring outcomes:
  demo-001 (outdoor/sporting) → high score for outdoor gear offers (AC-023 ≥ 75)
  demo-005 (automotive)       → low score for outdoor gear offers (AC-024 ≤ 45)
"""

from __future__ import annotations

from typing import Optional

from src.backend.models.purchase_event import MemberProfile

_PROFILES: dict[str, MemberProfile] = {
    "demo-001": MemberProfile(
        member_id="demo-001",
        segment="frequent_outdoor",
        total_spend_90_days=1240.0,
        purchase_count_90_days=12,
        preferred_categories=["outdoor", "sporting_goods", "fitness"],
        last_ctc_purchase_days_ago=3,
        loyalty_tier="gold",
    ),
    "demo-002": MemberProfile(
        member_id="demo-002",
        segment="urban_commuter",
        total_spend_90_days=540.0,
        purchase_count_90_days=6,
        preferred_categories=["food_beverage", "apparel"],
        last_ctc_purchase_days_ago=14,
        loyalty_tier="silver",
    ),
    "demo-003": MemberProfile(
        member_id="demo-003",
        segment="seasonal_home",
        total_spend_90_days=310.0,
        purchase_count_90_days=3,
        preferred_categories=["hardware", "home_garden"],
        last_ctc_purchase_days_ago=30,
        loyalty_tier="standard",
    ),
    "demo-004": MemberProfile(
        member_id="demo-004",
        segment="family_shopper",
        total_spend_90_days=2100.0,
        purchase_count_90_days=8,
        preferred_categories=["outdoor", "electronics", "apparel"],
        last_ctc_purchase_days_ago=7,
        loyalty_tier="platinum",
    ),
    "demo-005": MemberProfile(
        member_id="demo-005",
        segment="auto_parts_buyer",
        total_spend_90_days=180.0,
        purchase_count_90_days=2,
        preferred_categories=["automotive"],
        last_ctc_purchase_days_ago=45,
        loyalty_tier="standard",
    ),
}


class MockMemberProfileStore:
    """Returns hardcoded demo member profiles. Thread-safe (read-only data)."""

    def get(self, member_id: str) -> Optional[MemberProfile]:
        """Return profile for member_id, or None if not a demo member."""
        return _PROFILES.get(member_id)

    @staticmethod
    def all_member_ids() -> list[str]:
        """Return all demo member IDs in order."""
        return list(_PROFILES.keys())
