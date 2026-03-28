"""CTC store fixtures — hardcoded store coordinates for nearby-store lookup.

Uses Haversine formula for distance calculation.
EC-005: stores exactly 2.0km away are excluded (strictly < 2.0km).
"""

from __future__ import annotations

import math
from typing import NamedTuple

from src.backend.models.purchase_event import GeoPoint, NearbyStore


class _StoreFixture(NamedTuple):
    store_id: str
    store_name: str
    lat: float
    lon: float
    category: str


_CTC_STORES: list[_StoreFixture] = [
    _StoreFixture("ctc-001", "Canadian Tire Queen St W", 43.6488, -79.3981, "general"),
    _StoreFixture("ctc-002", "Canadian Tire Yonge & Eglinton", 43.7060, -79.3985, "general"),
    _StoreFixture("ctc-003", "Sport Chek Eaton Centre", 43.6544, -79.3807, "sporting_goods"),
    _StoreFixture("ctc-004", "Sport Chek Yorkdale", 43.7243, -79.4508, "sporting_goods"),
    _StoreFixture("ctc-005", "Canadian Tire Mississauga", 43.5890, -79.6441, "general"),
    _StoreFixture("ctc-006", "Marks King St W", 43.6450, -79.4012, "apparel"),
    _StoreFixture("ctc-007", "Canadian Tire Scarborough", 43.7731, -79.2576, "general"),
    _StoreFixture("ctc-008", "Sport Chek Square One", 43.5935, -79.6393, "sporting_goods"),
]


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in kilometres between two WGS-84 points."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


class CTCStoreFixtures:
    """Returns nearby CTC stores within a given radius, sorted by distance."""

    def get_nearby(self, location: GeoPoint, radius_km: float = 2.0) -> list[NearbyStore]:
        """Return stores strictly within radius_km (EC-005: < not ≤).

        Results sorted by distance ascending.
        """
        results: list[tuple[float, NearbyStore]] = []
        for store in _CTC_STORES:
            dist = _haversine_km(location.lat, location.lon, store.lat, store.lon)
            if dist < radius_km:  # strictly less than — EC-005
                results.append((
                    dist,
                    NearbyStore(
                        store_id=store.store_id,
                        store_name=store.store_name,
                        distance_km=round(dist, 3),
                        category=store.category,
                    ),
                ))
        results.sort(key=lambda t: t[0])
        return [ns for _, ns in results]

    @staticmethod
    def all_stores() -> list[_StoreFixture]:
        """Return all fixture stores (for frontend preset dropdowns)."""
        return list(_CTC_STORES)
