"""Pydantic v2 models for POST /api/scout/match request and response.

No changes to OfferBrief schema (CON-006).
GPS coordinates (lat/lon) are never stored in ScoutActivationRecord (CON-002 / AC-017).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field

from src.backend.models.purchase_event import GeoPoint, MemberProfile, NearbyStore, WeatherConditions


class DayContext(str, Enum):
    weekday = "weekday"
    weekend = "weekend"
    long_weekend = "long_weekend"


class ScoutOutcome(str, Enum):
    activated = "activated"
    queued = "queued"
    rate_limited = "rate_limited"
    error = "error"


class ScoringMethod(str, Enum):
    claude = "claude"
    fallback = "fallback"
    cached = "cached"


# ─── API Request / Response ────────────────────────────────────────────────────


class MatchRequest(BaseModel):
    """Request body for POST /api/scout/match.

    purchase_location is Optional so that Pydantic does not return 422.
    Route-level validation returns HTTP 400 when absent (AC-007 / design review F-004).
    """

    member_id: str = Field(..., min_length=1, max_length=100)
    purchase_location: Optional[GeoPoint] = None  # required at route level → 400 if absent
    purchase_category: str = Field(default="general", min_length=1, max_length=50)
    rewards_earned: int = Field(default=0, ge=0)
    day_context: DayContext = DayContext.weekday
    weather_condition: Optional[str] = None  # omit → API call; present → skip API call


class MatchResponse(BaseModel):
    """Response for a successful match evaluation."""

    score: float = Field(..., ge=0.0, le=100.0)
    rationale: str
    notification_text: str
    offer_id: str
    outcome: ScoutOutcome
    scoring_method: ScoringMethod
    queued: Optional[bool] = None           # present when outcome=queued
    delivery_time: Optional[str] = None    # "HH:MM" next morning, when queued=True
    retry_after_seconds: Optional[int] = None  # present when outcome=rate_limited


class NoMatchResponse(BaseModel):
    """Response when no active offers are available or all candidates are filtered."""

    matches: list = Field(default_factory=list)
    message: str


# ─── Internal enriched context (never serialised to API) ──────────────────────


class EnrichedMatchContext(BaseModel):
    """Purchase context after concurrent enrichment.

    CON-002: No lat/lon fields. Only store_id, store_name, distance_km.
    """

    request: MatchRequest
    member: Optional[MemberProfile] = None
    nearby_stores: list[NearbyStore] = Field(default_factory=list)
    weather: Optional[WeatherConditions] = None
    enrichment_partial: bool = False        # True when any optional signal was absent
    absent_signals: list[str] = Field(default_factory=list)  # e.g. ["weather", "behavioral_profile"]


# ─── Audit record (persisted to scout_activation_log) ─────────────────────────


@dataclass
class ScoutActivationRecord:
    """Audit record for every match outcome. No GPS coordinates permitted (AC-017)."""

    member_id: str
    offer_id: str
    score: float
    rationale: str
    scoring_method: ScoringMethod
    outcome: ScoutOutcome
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
