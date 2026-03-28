"""Unit tests for MockMemberProfileStore — REQ-008, AC-023, AC-024."""

import pytest

from src.backend.services.mock_member_profile_store import MockMemberProfileStore


class TestMockMemberProfileStore:
    def setup_method(self):
        self.store = MockMemberProfileStore()

    def test_returns_profile_for_demo_members(self):
        for member_id in ["demo-001", "demo-002", "demo-003", "demo-004", "demo-005"]:
            profile = self.store.get(member_id)
            assert profile is not None, f"Expected profile for {member_id}"
            assert profile.member_id == member_id

    def test_returns_none_for_unknown_member(self):
        """REQ-004: graceful degradation — unknown IDs return None."""
        assert self.store.get("unknown-999") is None
        assert self.store.get("") is None

    def test_all_member_ids_returns_five(self):
        ids = MockMemberProfileStore.all_member_ids()
        assert len(ids) == 5
        assert "demo-001" in ids
        assert "demo-005" in ids

    def test_demo_001_outdoor_profile_for_ac023(self):
        """AC-023: demo-001 has outdoor/sporting preferences — should score ≥75 for outdoor offers."""
        profile = self.store.get("demo-001")
        assert profile is not None
        assert "outdoor" in profile.preferred_categories
        assert profile.loyalty_tier == "gold"
        assert profile.purchase_count_90_days >= 10

    def test_demo_005_automotive_profile_for_ac024(self):
        """AC-024: demo-005 has automotive preference — should score ≤45 for outdoor offers."""
        profile = self.store.get("demo-005")
        assert profile is not None
        assert profile.preferred_categories == ["automotive"]
        assert profile.purchase_count_90_days <= 3

    def test_all_profiles_have_required_fields(self):
        for mid in MockMemberProfileStore.all_member_ids():
            p = self.store.get(mid)
            assert p is not None
            assert p.member_id
            assert p.segment
            assert isinstance(p.preferred_categories, list)
            assert p.loyalty_tier in {"standard", "silver", "gold", "platinum"}
