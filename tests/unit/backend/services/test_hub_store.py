"""Unit tests for InMemoryHubStore — COMP-001."""

import pytest
from datetime import datetime, timezone

from src.backend.models.offer_brief import OfferStatus, TriggerType
from src.backend.services.hub_store import InMemoryHubStore, OfferAlreadyExistsError
from tests.fixtures.offer_brief_factory import make_offer_brief, make_purchase_offer


@pytest.fixture
def store() -> InMemoryHubStore:
    s = InMemoryHubStore()
    return s


class TestSave:
    async def test_save_new_offer_succeeds(self, store):
        offer = make_offer_brief()
        await store.save(offer)
        result = await store.get(offer.offer_id)
        assert result is not None
        assert result.offer_id == offer.offer_id

    async def test_save_duplicate_raises_error(self, store):
        offer = make_offer_brief()
        await store.save(offer)
        with pytest.raises(OfferAlreadyExistsError):
            await store.save(offer)

    async def test_clear_empties_store(self, store):
        offer = make_offer_brief()
        await store.save(offer)
        store.clear()
        result = await store.get(offer.offer_id)
        assert result is None


class TestGet:
    async def test_get_existing_offer(self, store):
        offer = make_offer_brief()
        await store.save(offer)
        result = await store.get(offer.offer_id)
        assert result == offer

    async def test_get_missing_offer_returns_none(self, store):
        result = await store.get("nonexistent-id")
        assert result is None


class TestUpdate:
    async def test_update_replaces_offer(self, store):
        offer = make_offer_brief(status="draft")
        await store.save(offer)
        updated = offer.model_copy(update={"status": "approved"})
        await store.update(updated)
        result = await store.get(offer.offer_id)
        assert result.status == OfferStatus.approved

    async def test_update_nonexistent_offer_creates_it(self, store):
        """update() is an upsert — it creates the offer if not present."""
        offer = make_offer_brief()
        await store.update(offer)
        result = await store.get(offer.offer_id)
        assert result is not None


class TestList:
    async def test_list_all_returns_all_offers(self, store):
        await store.save(make_offer_brief())
        await store.save(make_offer_brief())
        result = await store.list()
        assert len(result) == 2

    async def test_list_filter_by_status(self, store):
        draft = make_offer_brief(status="draft")
        approved = make_offer_brief(status="approved")
        await store.save(draft)
        await store.save(approved)
        result = await store.list(status_filter=OfferStatus.draft)
        assert len(result) == 1
        assert result[0].status == OfferStatus.draft

    async def test_list_filter_by_trigger_type(self, store):
        marketer = make_offer_brief(trigger_type="marketer_initiated")
        purchase = make_purchase_offer()
        await store.save(marketer)
        await store.save(purchase)
        result = await store.list(trigger_type=TriggerType.purchase_triggered)
        assert len(result) == 1
        assert result[0].trigger_type == TriggerType.purchase_triggered

    async def test_list_filter_by_since_excludes_older(self, store):
        old_offer = make_offer_brief(created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        await store.save(old_offer)
        since = datetime(2026, 6, 1, tzinfo=timezone.utc)
        result = await store.list(since=since)
        assert len(result) == 0

    async def test_list_filter_by_since_includes_newer(self, store):
        new_offer = make_offer_brief(created_at=datetime(2026, 12, 1, tzinfo=timezone.utc))
        await store.save(new_offer)
        since = datetime(2026, 6, 1, tzinfo=timezone.utc)
        result = await store.list(since=since)
        assert len(result) == 1

    async def test_list_empty_store_returns_empty(self, store):
        result = await store.list()
        assert result == []


class TestExists:
    async def test_exists_returns_true_for_known_offer(self, store):
        offer = make_offer_brief()
        await store.save(offer)
        assert await store.exists(offer.offer_id) is True

    async def test_exists_returns_false_for_unknown_id(self, store):
        assert await store.exists("unknown-id") is False


class TestPing:
    async def test_ping_always_returns_true(self, store):
        assert await store.ping() is True
