"""Pydantic v2 models for Scout purchase events and enriched context."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class GeoPoint(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)


class PurchaseEventPayload(BaseModel):
    """Inbound payload from the rewards system webhook."""

    event_id: str = Field(..., description="Unique event identifier for deduplication")
    member_id: str = Field(..., min_length=1)
    store_id: str = Field(..., min_length=1)
    store_name: str = Field(..., min_length=1)
    store_type: str = Field(..., description="ctc_owned | partner")
    partner_brand: Optional[str] = None  # e.g., 'tim_hortons', 'westside'
    amount: float = Field(..., gt=0, description="Purchase amount in CAD")
    currency: str = Field(default="CAD")
    is_refund: bool = False
    location: GeoPoint
    category: Optional[str] = None  # e.g., 'sporting_goods', 'food_beverage'
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class MemberProfile(BaseModel):
    member_id: str
    segment: str
    total_spend_90_days: float
    purchase_count_90_days: int
    preferred_categories: list[str] = Field(default_factory=list)
    last_ctc_purchase_days_ago: Optional[int] = None
    loyalty_tier: str = "standard"  # standard | silver | gold | platinum


class NearbyStore(BaseModel):
    store_id: str
    store_name: str
    distance_km: float
    category: str


class WeatherConditions(BaseModel):
    condition: str  # e.g., 'snow', 'rain', 'clear', 'cold'
    temperature_c: float
    is_adverse: bool = False


class EnrichedContext(BaseModel):
    """Purchase event payload enriched with member history, nearby stores, weather."""

    event: PurchaseEventPayload
    member: Optional[MemberProfile] = None
    nearby_stores: list[NearbyStore] = Field(default_factory=list)
    weather: Optional[WeatherConditions] = None
    enrichment_duration_ms: Optional[float] = None


class PurchaseContextRequest(BaseModel):
    """Request body for POST /api/designer/generate-purchase."""

    member_id: str
    event_id: str
    purchase_amount: float = Field(..., gt=0)
    store_name: str
    partner_brand: Optional[str] = None
    member_segment: str
    nearby_ctc_stores: list[str] = Field(default_factory=list)
    weather_condition: Optional[str] = None
    context_score: float = Field(..., ge=0, le=100)
    score_breakdown: dict[str, float] = Field(default_factory=dict)
