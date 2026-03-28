"""Unit tests for RedisDeliveryConstraintService — F-003 fail-open, constraints."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
import redis as _redis_lib

from src.backend.services.delivery_constraint_service import RedisDeliveryConstraintService


def _make_service(redis_mock=None) -> RedisDeliveryConstraintService:
    """Create service with mocked Redis client."""
    svc = RedisDeliveryConstraintService.__new__(RedisDeliveryConstraintService)
    svc._redis = redis_mock or MagicMock()
    return svc


class TestFailOpen:
    """F-003: Redis errors must never propagate — all methods fail-open."""

    def test_can_deliver_fails_open_on_rate_limit_redis_error(self):
        redis_mock = MagicMock()
        redis_mock.exists.side_effect = _redis_lib.RedisError("connection refused")
        svc = _make_service(redis_mock)

        # Should NOT raise, should allow delivery (fail-open)
        now = datetime(2026, 3, 27, 14, 0, 0)
        allowed, reason = svc.can_deliver("M001", amount=50.0, now=now)
        assert allowed is True

    def test_can_deliver_fails_open_on_dedup_redis_error(self):
        redis_mock = MagicMock()
        # rate limit key: exists returns False (no rate limit hit)
        # dedup key: raises RedisError
        redis_mock.exists.side_effect = [False, _redis_lib.RedisError("timeout")]
        svc = _make_service(redis_mock)

        now = datetime(2026, 3, 27, 14, 0, 0)
        allowed, reason = svc.can_deliver("M001", amount=50.0, now=now)
        assert allowed is True

    def test_record_delivery_silently_passes_on_redis_error(self):
        redis_mock = MagicMock()
        redis_mock.pipeline.return_value.execute.side_effect = _redis_lib.RedisError("timeout")
        redis_mock.pipeline.return_value.__enter__ = MagicMock()
        redis_mock.pipeline.return_value.set = MagicMock()
        svc = _make_service(redis_mock)

        # Should NOT raise
        svc.record_delivery("M001")

    def test_retry_after_seconds_returns_zero_on_redis_error(self):
        redis_mock = MagicMock()
        redis_mock.pttl.side_effect = _redis_lib.RedisError("timeout")
        svc = _make_service(redis_mock)
        assert svc.retry_after_seconds("M001") == 0

    def test_queue_for_morning_silently_passes_on_redis_error(self):
        redis_mock = MagicMock()
        redis_mock.setex.side_effect = _redis_lib.RedisError("timeout")
        svc = _make_service(redis_mock)
        # Should NOT raise
        svc.queue_for_morning("M001", "offer-001")


class TestConstraints:

    def test_blocks_when_rate_limit_key_exists(self):
        redis_mock = MagicMock()
        redis_mock.exists.side_effect = [True]  # rate limit key present
        svc = _make_service(redis_mock)

        now = datetime(2026, 3, 27, 14, 0, 0)
        allowed, reason = svc.can_deliver("M001", amount=50.0, now=now)
        assert allowed is False
        assert "Rate limit" in reason

    def test_blocks_when_dedup_key_exists(self):
        redis_mock = MagicMock()
        # Rate limit key absent, dedup key present
        redis_mock.exists.side_effect = [False, True]
        svc = _make_service(redis_mock)

        now = datetime(2026, 3, 27, 14, 0, 0)
        allowed, reason = svc.can_deliver("M001", amount=50.0, now=now)
        assert allowed is False
        assert "Dedup" in reason

    def test_skips_dedup_for_high_value_purchase(self):
        redis_mock = MagicMock()
        redis_mock.exists.side_effect = [False]  # rate limit check only
        svc = _make_service(redis_mock)

        now = datetime(2026, 3, 27, 14, 0, 0)
        # High-value amount bypasses dedup
        allowed, _ = svc.can_deliver("M001", amount=200.0, now=now)
        assert allowed is True
        # exists called only once (rate limit, not dedup)
        assert redis_mock.exists.call_count == 1

    def test_blocks_during_quiet_hours(self):
        redis_mock = MagicMock()
        redis_mock.exists.return_value = False
        svc = _make_service(redis_mock)

        now = datetime(2026, 3, 27, 23, 0, 0)  # 11pm — quiet hours
        allowed, reason = svc.can_deliver("M001", amount=50.0, now=now)
        assert allowed is False
        assert "Quiet hours" in reason

    def test_blocks_on_opt_out(self):
        svc = _make_service()
        now = datetime(2026, 3, 27, 14, 0, 0)
        allowed, reason = svc.can_deliver("M001", amount=50.0, now=now, member_notifications_enabled=False)
        assert allowed is False
        assert "opted out" in reason.lower()

    def test_retry_after_seconds_returns_ceiling(self):
        redis_mock = MagicMock()
        redis_mock.pttl.return_value = 3001  # 3.001 seconds
        svc = _make_service(redis_mock)
        assert svc.retry_after_seconds("M001") == 4  # ceiling

    def test_retry_after_seconds_returns_zero_when_no_key(self):
        redis_mock = MagicMock()
        redis_mock.pttl.return_value = -2  # key doesn't exist
        svc = _make_service(redis_mock)
        assert svc.retry_after_seconds("M001") == 0
