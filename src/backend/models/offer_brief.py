"""Pydantic v2 models for OfferBrief — mirrors src/shared/types/offer-brief.ts exactly."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class TriggerType(str, Enum):
    marketer_initiated = "marketer_initiated"
    purchase_triggered = "purchase_triggered"


class OfferStatus(str, Enum):
    draft = "draft"
    approved = "approved"
    active = "active"
    expired = "expired"


class ChannelType(str, Enum):
    push = "push"
    email = "email"
    sms = "sms"
    in_app = "in_app"


class RiskSeverity(str, Enum):
    low = "low"
    medium = "medium"
    critical = "critical"


# ─── Nested Models ────────────────────────────────────────────────────────────


class Segment(BaseModel):
    name: str = Field(..., min_length=1)
    definition: str = Field(..., min_length=1)
    estimated_size: int = Field(..., ge=0)
    criteria: list[str] = Field(..., min_length=1)


class Construct(BaseModel):
    type: str = Field(..., min_length=1)
    value: float = Field(..., ge=0)
    description: str = Field(..., min_length=1)


class Channel(BaseModel):
    channel_type: ChannelType
    priority: int = Field(..., ge=1)
    message_template: Optional[str] = None


class KPIs(BaseModel):
    expected_redemption_rate: float = Field(..., ge=0, le=1)
    expected_uplift_pct: float = Field(..., ge=0)
    target_segment_size: Optional[int] = Field(default=None, ge=0)


class RiskFlags(BaseModel):
    over_discounting: bool
    cannibalization: bool
    frequency_abuse: bool
    offer_stacking: bool
    severity: RiskSeverity
    warnings: list[str] = Field(default_factory=list)


# ─── Core OfferBrief Model ────────────────────────────────────────────────────


class OfferBrief(BaseModel):
    offer_id: str = Field(..., description="UUID v4 string")
    objective: str = Field(..., min_length=10, max_length=500)
    segment: Segment
    construct: Construct
    channels: list[Channel] = Field(..., min_length=1)
    kpis: KPIs
    risk_flags: RiskFlags
    status: OfferStatus = OfferStatus.draft
    trigger_type: TriggerType = TriggerType.marketer_initiated
    created_at: datetime = Field(default_factory=datetime.utcnow)
    valid_until: Optional[datetime] = None

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def validate_valid_until_for_purchase_triggered(self) -> "OfferBrief":
        """Purchase-triggered offers must have valid_until set."""
        if self.trigger_type == TriggerType.purchase_triggered and self.valid_until is None:
            raise ValueError(
                "valid_until is required for purchase_triggered offers"
            )
        return self


# ─── Request / Response Models ────────────────────────────────────────────────


class GenerateOfferRequest(BaseModel):
    objective: str = Field(..., min_length=10, max_length=500)
    segment_hints: Optional[list[str]] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "objective": "Reactivate lapsed high-value members this winter",
                "segment_hints": ["high_value", "lapsed_90_days"],
            }
        }
    }


class ApproveOfferResponse(BaseModel):
    offer_id: str
    status: OfferStatus
    hub_saved: bool
    message: str


class FraudCheckResult(BaseModel):
    severity: RiskSeverity
    flags: RiskFlags
    warnings: list[str]
    blocked: bool


class InventorySuggestion(BaseModel):
    product_id: str
    product_name: str
    category: str
    store: str
    units_in_stock: int = Field(..., ge=0)
    urgency: str = Field(..., pattern="^(high|medium|low)$")
    suggested_objective: str
    stale: bool = False


class DealSuggestion(BaseModel):
    """Live deal scraped from Canadian Tire for offer creation intelligence."""

    deal_id: str
    product_name: str
    category: str
    discount_pct: float = Field(..., ge=0, le=100)
    original_price: float = Field(..., ge=0)
    deal_price: float = Field(..., ge=0)
    source_url: str
    source: str = Field(..., pattern="^(weekly_deals|flyer|clearance)$")
    suggested_objective: str
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
