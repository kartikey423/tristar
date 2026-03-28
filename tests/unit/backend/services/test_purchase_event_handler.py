"""Unit tests for PurchaseEventHandler — COMP-018."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from src.backend.models.purchase_event import GeoPoint, PurchaseEventPayload
from src.backend.services.purchase_event_handler import PurchaseEventHandler, _seen_events


def make_event(**kwargs) -> PurchaseEventPayload:
    defaults = {
        "event_id": "evt-unique-001",
        "member_id": "M001",
        "store_id": "TH-001",
        "store_name": "Tim Hortons",
        "store_type": "partner",
        "partner_brand": "tim_hortons",
        "amount": 12.50,
        "is_refund": False,
        "location": GeoPoint(lat=43.65, lon=-79.38),
        "category": "food_beverage",
        "timestamp": datetime(2026, 3, 27, 14, 0, 0),
    }
    defaults.update(kwargs)
    return PurchaseEventPayload(**defaults)


@pytest.fixture(autouse=True)
def clear_seen_events():
    _seen_events.clear()
    yield
    _seen_events.clear()


class TestFeatureFlag:
    async def test_disabled_feature_flag_returns_none(self):
        """When PURCHASE_TRIGGER_ENABLED=False, handler returns None immediately."""
        handler = PurchaseEventHandler()
        # Default config has PURCHASE_TRIGGER_ENABLED=False
        result = await handler.handle(make_event())
        assert result is None

    async def test_enabled_but_member_not_in_pilot_returns_none(self):
        handler = PurchaseEventHandler()
        handler._enabled = True
        handler._pilot_ids = {"M999"}  # M001 not in pilot

        result = await handler.handle(make_event(member_id="M001"))
        assert result is None

    async def test_enabled_with_empty_pilot_allows_all_members(self):
        handler = PurchaseEventHandler()
        handler._enabled = True
        handler._pilot_ids = set()  # Empty = all members allowed

        with (
            patch(
                "src.backend.services.purchase_event_handler._fetch_member_history",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "src.backend.services.purchase_event_handler._find_nearby_ctc_stores",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "src.backend.services.purchase_event_handler._get_weather",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            result = await handler.handle(make_event())

        assert result is not None


class TestRefundRejection:
    async def test_refund_event_returns_none(self):
        handler = PurchaseEventHandler()
        handler._enabled = True
        handler._pilot_ids = set()

        result = await handler.handle(make_event(is_refund=True))
        assert result is None


class TestDeduplication:
    async def test_duplicate_event_within_60s_returns_none(self):
        handler = PurchaseEventHandler()
        handler._enabled = True
        handler._pilot_ids = set()

        # First event
        _seen_events["evt-dup-001"] = datetime.utcnow()

        # Same event_id
        result = await handler.handle(make_event(event_id="evt-dup-001"))
        assert result is None


class TestConcurrentEnrichment:
    async def test_enrichment_uses_gather(self):
        """F-008: Enrichment should call asyncio.gather, not sequential awaits."""
        handler = PurchaseEventHandler()
        handler._enabled = True
        handler._pilot_ids = set()

        gather_called = []

        async def mock_gather(*coros, return_exceptions=False):
            gather_called.append(True)
            # Simulate gather behavior
            results = []
            for coro in coros:
                try:
                    results.append(await coro)
                except Exception as e:
                    if return_exceptions:
                        results.append(e)
                    else:
                        raise
            return results

        with patch("asyncio.gather", side_effect=mock_gather):
            result = await handler.handle(make_event())

        assert len(gather_called) == 1, "asyncio.gather was not called for concurrent enrichment"
