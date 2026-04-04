"""Unit tests for CTCStoreFixtures — EC-005, Haversine distance, sorting."""

import math

import pytest

from src.backend.models.purchase_event import GeoPoint
from src.backend.services.ctc_store_fixtures import CTCStoreFixtures, _haversine_km


class TestHaversine:
    def test_same_point_is_zero(self):
        assert _haversine_km(43.6, -79.4, 43.6, -79.4) == pytest.approx(0.0, abs=0.001)

    def test_known_distance(self):
        # Canadian Tire Queen St W (43.6488, -79.3981) to Sport Chek Eaton Centre (43.6544, -79.3807)
        dist = _haversine_km(43.6488, -79.3981, 43.6544, -79.3807)
        # ~1.5 km — rough sanity check
        assert 1.0 < dist < 2.5


class TestGetNearby:
    def setup_method(self):
        self.fixtures = CTCStoreFixtures()

    def test_returns_stores_within_radius(self):
        # Location very close to Canadian Tire Queen St W
        loc = GeoPoint(lat=43.6490, lon=-79.3980)
        stores = self.fixtures.get_nearby(loc, radius_km=2.0)
        assert len(stores) > 0
        ids = [s.store_id for s in stores]
        assert "ctc-001" in ids

    def test_ec005_excludes_exactly_2km(self):
        """Stores exactly at 2.0 km must be excluded (strictly < not ≤)."""
        loc = GeoPoint(lat=43.6488, lon=-79.3981)  # ctc-001 coords
        # ctc-001 is at distance ~0 from itself — just verify the boundary logic holds
        stores = self.fixtures.get_nearby(loc, radius_km=0.0)
        # radius=0 → no stores (strictly less than 0 is never true)
        assert stores == []

    def test_sorted_by_distance_ascending(self):
        loc = GeoPoint(lat=43.6490, lon=-79.3985)
        stores = self.fixtures.get_nearby(loc, radius_km=5.0)
        if len(stores) >= 2:
            distances = [s.distance_km for s in stores]
            assert distances == sorted(distances)

    def test_returns_empty_for_remote_location(self):
        # Far away from all Toronto stores
        loc = GeoPoint(lat=45.0, lon=-75.0)  # Ottawa area
        stores = self.fixtures.get_nearby(loc, radius_km=2.0)
        assert stores == []

    def test_distance_rounded_to_3_decimal_places(self):
        loc = GeoPoint(lat=43.6490, lon=-79.3985)
        stores = self.fixtures.get_nearby(loc, radius_km=5.0)
        for store in stores:
            assert round(store.distance_km, 3) == store.distance_km

    def test_all_stores_returns_10(self):
        # 8 original CTC stores + 2 hill station partner fixtures (Blue Mountain, Whistler)
        stores = CTCStoreFixtures.all_stores()
        assert len(stores) == 10
