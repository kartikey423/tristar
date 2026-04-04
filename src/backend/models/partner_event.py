"""Pydantic v2 models for partner purchase trigger events and redemption enforcement."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from src.backend.models.purchase_event import GeoPoint


class PartnerPurchaseEvent(BaseModel):
    """Incoming webhook payload from a CTC partner store (Tim Hortons, WestJet, etc.)."""

    event_id: str = Field(..., description="Unique event ID for deduplication (60s window)")
    partner_id: str = Field(..., description="Partner identifier e.g. 'tim_hortons'")
    partner_name: str = Field(..., min_length=1, max_length=100)
    purchase_amount: float = Field(..., ge=0)
    purchase_category: str = Field(..., min_length=1, max_length=100,
        description="Partner-side purchase category e.g. 'coffee', 'food', 'camping_gear'")
    member_id: str = Field(..., description="Triangle loyalty member ID")
    timestamp: datetime
    location: Optional[GeoPoint] = Field(None, description="GPS coordinates for location zone classification")
    store_name: Optional[str] = Field(None, min_length=1, max_length=200,
        description="Partner store name e.g. 'Tim Hortons - Blue Mountain' for zone detection")

    model_config = {
        "json_schema_extra": {
            "example": {
                "event_id": "tims-evt-2026-001",
                "partner_id": "tim_hortons",
                "partner_name": "Tim Hortons",
                "purchase_amount": 8.50,
                "purchase_category": "coffee",
                "member_id": "M-12345",
                "timestamp": "2026-04-04T14:30:00Z",
                "location": {"lat": 44.5, "lon": -80.3},
                "store_name": "Tim Hortons - Blue Mountain",
            }
        }
    }


class PartnerTriggerResponse(BaseModel):
    """Response returned immediately to partner webhook (HTTP 202)."""

    status: str = Field(..., description="'accepted' or 'duplicate'")
    offer_id: Optional[str] = Field(None, description="Set once background generation completes")
    message: str


class RedemptionRequest(BaseModel):
    """Request to redeem a Triangle Rewards offer with a specific payment split."""

    offer_id: str
    points_pct: float = Field(..., ge=0, le=100,
        description="Percentage of offer value to be paid in Triangle points (0–100)")
    cash_pct: float = Field(..., ge=0, le=100,
        description="Percentage of offer value to be paid via credit/debit (0–100)")

    @model_validator(mode="after")
    def validate_sum(self) -> "RedemptionRequest":
        if abs((self.points_pct + self.cash_pct) - 100.0) > 0.01:
            raise ValueError("points_pct + cash_pct must equal 100")
        return self


class RedemptionSplitError(Exception):
    """Raised when Triangle points redemption exceeds the offer's payment_split.points_max_pct."""

    def __init__(self, points_pct: float, max_pct: float) -> None:
        self.points_pct = points_pct
        self.max_pct = max_pct
        super().__init__(
            f"Points redemption ({points_pct:.1f}%) exceeds maximum allowed ({max_pct:.1f}%). "
            f"A minimum of {100 - max_pct:.1f}% must be paid via credit/debit card."
        )
