"""Location Zone Classification Service — Hill Station, Cottage/Lakes, Highway, Urban.

Classifies partner store locations into zones for context-aware offer targeting.
Uses GPS coordinates and store name keywords for zone detection.

Zones:
- hill_station: Mountain/ski resort areas (Blue Mountain, Mont-Tremblant, Whistler)
- cottage_lakes: Lake/cottage country (Muskoka, Georgian Bay, Kawartha)
- highway: Major highway corridors (400, 401, 417)
- urban: City centers (default fallback)
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from src.backend.models.purchase_event import GeoPoint
from src.backend.services.ctc_store_fixtures import _haversine_km


class LocationZone(str, Enum):
    """Geographic zone types for partner store classification."""

    hill_station = "hill_station"
    cottage_lakes = "cottage_lakes"
    highway = "highway"
    urban = "urban"


# ─── Zone Detection Keywords ──────────────────────────────────────────────────
# Store name keyword → zone mapping (checked before coordinate-based classification)
_ZONE_KEYWORDS: dict[str, LocationZone] = {
    # Hill Station / Mountain
    "blue mountain": LocationZone.hill_station,
    "collingwood": LocationZone.hill_station,
    "mont tremblant": LocationZone.hill_station,
    "mont-tremblant": LocationZone.hill_station,
    "whistler": LocationZone.hill_station,
    "ski resort": LocationZone.hill_station,
    "mountain": LocationZone.hill_station,
    # Cottage / Lakes
    "muskoka": LocationZone.cottage_lakes,
    "gravenhurst": LocationZone.cottage_lakes,
    "bracebridge": LocationZone.cottage_lakes,
    "huntsville": LocationZone.cottage_lakes,
    "parry sound": LocationZone.cottage_lakes,
    "georgian bay": LocationZone.cottage_lakes,
    "kawartha": LocationZone.cottage_lakes,
    "cottage": LocationZone.cottage_lakes,
    "lake": LocationZone.cottage_lakes,
    # Highway (less common in store names, usually detected by coords)
    "highway": LocationZone.highway,
    "rest stop": LocationZone.highway,
    "service center": LocationZone.highway,
}

# ─── Zone Coordinate Boundaries ───────────────────────────────────────────────
# Bounding boxes: (lat_min, lat_max, lon_min, lon_max)
_HILL_STATION_ZONES: list[tuple[float, float, float, float]] = [
    # Blue Mountain / Collingwood area
    (44.3, 44.7, -80.5, -80.0),
    # Mont-Tremblant area
    (46.0, 46.3, -74.7, -74.3),
    # Whistler area (BC)
    (50.0, 50.2, -123.2, -122.8),
]

_COTTAGE_LAKES_ZONES: list[tuple[float, float, float, float]] = [
    # Muskoka region
    (45.0, 45.5, -80.2, -79.0),
    # Kawartha Lakes region
    (44.2, 44.7, -79.0, -78.5),
    # Parry Sound / Georgian Bay
    (45.3, 45.8, -80.5, -79.5),
]

# Highway corridors: (lat, lon) waypoints defining major routes
# For simplicity, check if location is within 5km of any waypoint
_HIGHWAY_CORRIDORS: list[tuple[float, float]] = [
    # Highway 400 North (Toronto → Barrie → Sudbury)
    (43.8, -79.5), (44.0, -79.5), (44.3, -79.6), (44.5, -79.7),
    # Highway 401 (Windsor → Toronto → Kingston → Montreal)
    (43.7, -79.4), (43.9, -79.2), (44.0, -78.8), (44.2, -78.2),
    # Highway 417 (Ottawa)
    (45.4, -75.7), (45.4, -75.9),
]


def _is_in_bounding_box(lat: float, lon: float, box: tuple[float, float, float, float]) -> bool:
    """Check if coordinates fall within a bounding box."""
    lat_min, lat_max, lon_min, lon_max = box
    return lat_min <= lat <= lat_max and lon_min <= lon <= lon_max


def _is_near_highway(lat: float, lon: float, threshold_km: float = 5.0) -> bool:
    """Check if location is within threshold_km of any highway corridor waypoint."""
    for hw_lat, hw_lon in _HIGHWAY_CORRIDORS:
        distance = _haversine_km(lat, lon, hw_lat, hw_lon)
        if distance < threshold_km:
            return True
    return False


class LocationZoneService:
    """Classifies partner store locations into geographic zones."""

    def classify(self, location: Optional[GeoPoint], store_name: Optional[str] = None) -> LocationZone:
        """Classify location into a geographic zone.

        Priority:
        1. Store name keywords (e.g., "Blue Mountain" → hill_station)
        2. Coordinate-based bounding boxes
        3. Highway proximity check
        4. Default to urban

        Args:
            location: GPS coordinates (lat, lon). If None, defaults to urban.
            store_name: Partner store name for keyword matching.

        Returns:
            LocationZone enum value.
        """
        # Priority 1: Check store name keywords
        if store_name:
            store_lower = store_name.lower()
            for keyword, zone in _ZONE_KEYWORDS.items():
                if keyword in store_lower:
                    return zone

        # Priority 2: Coordinate-based classification
        if location:
            lat, lon = location.lat, location.lon

            # Check Hill Station zones
            for box in _HILL_STATION_ZONES:
                if _is_in_bounding_box(lat, lon, box):
                    return LocationZone.hill_station

            # Check Cottage/Lakes zones
            for box in _COTTAGE_LAKES_ZONES:
                if _is_in_bounding_box(lat, lon, box):
                    return LocationZone.cottage_lakes

            # Check Highway corridors
            if _is_near_highway(lat, lon):
                return LocationZone.highway

        # Priority 3: Default to urban
        return LocationZone.urban
