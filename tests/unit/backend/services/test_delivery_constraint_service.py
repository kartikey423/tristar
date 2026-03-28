"""Unit tests for DeliveryConstraintService — COMP-020."""

from datetime import datetime, timedelta

import pytest
from freezegun import freeze_time

from src.backend.services.delivery_constraint_service import DeliveryConstraintService


class TestRateLimiting:
    def test_allows_first_delivery(self):
        service = DeliveryConstraintService()
        allowed, reason = service.can_deliver("M001", amount=50.0)
        assert allowed is True
        assert reason is None

    def test_blocks_within_6h_window(self):
        service = DeliveryConstraintService()
        now = datetime(2026, 3, 27, 10, 0, 0)
        service.record_delivery("M001", now=now)

        # Try 3 hours later — still within 6h window
        later = now + timedelta(hours=3)
        allowed, reason = service.can_deliver("M001", amount=50.0, now=later)
        assert allowed is False
        assert "Rate limit" in reason

    def test_allows_after_6h_window(self):
        service = DeliveryConstraintService()
        now = datetime(2026, 3, 27, 10, 0, 0)
        service.record_delivery("M001", now=now)

        # Try 7 hours later — outside 6h window; use high-value amount to bypass 24h dedup
        later = now + timedelta(hours=7)
        allowed, reason = service.can_deliver("M001", amount=150.0, now=later)
        assert allowed is True


class TestDedupWindow:
    def test_blocks_within_24h_for_normal_amount(self):
        service = DeliveryConstraintService()
        now = datetime(2026, 3, 27, 10, 0, 0)
        service.record_delivery("M002", now=now)

        # Try 8 hours later (outside 6h rate limit but inside 24h dedup)
        later = now + timedelta(hours=8)
        allowed, reason = service.can_deliver("M002", amount=50.0, now=later)
        assert allowed is False
        assert "Dedup" in reason

    def test_allows_high_value_purchase_within_24h(self):
        """Purchases > $100 bypass the 24h dedup window."""
        service = DeliveryConstraintService()
        now = datetime(2026, 3, 27, 10, 0, 0)
        service.record_delivery("M003", now=now)

        later = now + timedelta(hours=8)
        allowed, reason = service.can_deliver("M003", amount=150.0, now=later)
        assert allowed is True


class TestQuietHours:
    @freeze_time("2026-03-27 22:30:00")  # 10:30pm — quiet hours
    def test_blocks_during_quiet_hours(self):
        service = DeliveryConstraintService()
        allowed, reason = service.can_deliver("M004", amount=50.0)
        assert allowed is False
        assert "Quiet hours" in reason

    @freeze_time("2026-03-27 22:00:00")  # exactly 10pm
    def test_blocks_at_exact_quiet_hours_start(self):
        service = DeliveryConstraintService()
        allowed, reason = service.can_deliver("M005", amount=50.0)
        assert allowed is False

    @freeze_time("2026-03-27 07:59:00")  # 7:59am — still quiet hours (before 8am)
    def test_blocks_before_quiet_hours_end(self):
        service = DeliveryConstraintService()
        allowed, reason = service.can_deliver("M006", amount=50.0)
        assert allowed is False

    @freeze_time("2026-03-27 14:00:00")  # 2pm — outside quiet hours
    def test_allows_during_active_hours(self):
        service = DeliveryConstraintService()
        allowed, _ = service.can_deliver("M007", amount=50.0)
        assert allowed is True

    def test_queue_for_morning_stores_offer(self):
        service = DeliveryConstraintService()
        service.queue_for_morning("M008", "offer-xyz")
        assert "M008" in service._morning_queue
        assert service._morning_queue["M008"][0] == "offer-xyz"


class TestDeliveryRecording:
    def test_record_delivery_enables_subsequent_blocking(self):
        service = DeliveryConstraintService()
        now = datetime(2026, 3, 27, 14, 0, 0)
        service.record_delivery("M009", now=now)
        # Verify delivery is recorded
        deliveries = service._get_deliveries_since("M009", now - timedelta(hours=1))
        assert len(deliveries) == 1
