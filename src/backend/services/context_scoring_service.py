"""Context scoring service for purchase-triggered offer activation.

Scores purchase context 0–100 across 7 factors:
  1. purchase_value    (max 20): purchase amount → buying intent signal
  2. proximity         (max 25): nearest CTC store within 2km
  3. frequency         (max 15): recent CTC engagement frequency
  4. category_affinity (max 20): purchase category aligns with CTC inventory
  5. partner_crosssell (max 15): partner brand (Tim Hortons, Westside, etc.)
  6. weather           (max 10): adverse weather → more likely to visit
  7. time_alignment    (max 5):  purchase during peak shopping hours

Threshold: score > 70.0 → should_trigger = True
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from src.backend.core.config import settings
from src.backend.models.purchase_event import EnrichedContext

# ─── Partner brand cross-sell weight ──────────────────────────────────────────
# CTC-owned stores always score full 15pts; partner brands score based on
# typical cross-sell affinity with CTC product categories.
_PARTNER_CROSSSELL_SCORES: dict[str, float] = {
    # CTC-owned
    "sport_chek": 15.0,
    "marks": 15.0,
    "canadian_tire": 15.0,
    "party_city": 12.0,
    "lequipeur": 13.0,
    # Partners
    "tim_hortons": 12.0,    # high: daily habit drives foot traffic
    "westside": 11.0,
    "homegym": 10.0,
    "default": 5.0,
}

# ─── Category affinity mapping ────────────────────────────────────────────────
# Purchase category → affinity score with CTC inventory
_CATEGORY_AFFINITY: dict[str, float] = {
    "sporting_goods": 20.0,
    "outdoor": 20.0,
    "hardware": 18.0,
    "food_beverage": 15.0,  # Tim Hortons, etc. → CTC lifestyle connection
    "fitness": 17.0,
    "automotive": 16.0,
    "home_garden": 15.0,
    "apparel": 14.0,
    "electronics": 12.0,
    "default": 8.0,
}

# ─── Time alignment windows (peak shopping) ───────────────────────────────────
_PEAK_HOURS = {10, 11, 12, 13, 14, 15, 16, 17, 18}  # 10am–6pm
_WEEKEND_BONUS = 2.0


@dataclass
class ContextScore:
    total: float
    breakdown: dict[str, float] = field(default_factory=dict)
    should_trigger: bool = False


class ContextScoringService:
    def __init__(self, threshold: Optional[float] = None) -> None:
        self._threshold = threshold if threshold is not None else settings.PURCHASE_TRIGGER_SCORE_THRESHOLD

    def _score_purchase_value(self, amount: float) -> float:
        """Higher purchase amount = stronger buying intent signal."""
        if amount >= 200:
            return 20.0
        if amount >= 100:
            return 15.0
        if amount >= 50:
            return 10.0
        if amount >= 25:
            return 7.0
        return 3.0

    def _score_proximity(self, nearby_stores: list) -> float:
        """Score based on nearest CTC store distance."""
        if not nearby_stores:
            return 0.0
        # nearby_stores sorted by distance ascending
        nearest = nearby_stores[0]
        distance_km = getattr(nearest, "distance_km", 99.0)

        if distance_km < 0.5:
            return 25.0
        if distance_km < 1.0:
            return 20.0
        if distance_km < 1.5:
            return 15.0
        if distance_km < 2.0:
            return 10.0
        return 0.0

    def _score_frequency(self, member: Optional[object]) -> float:
        """Score based on recent CTC engagement."""
        if member is None:
            return 5.0  # default partial score

        purchase_count = getattr(member, "purchase_count_90_days", 0)
        last_ctc_days = getattr(member, "last_ctc_purchase_days_ago", None)

        freq_score = 0.0
        if purchase_count >= 10:
            freq_score = 15.0
        elif purchase_count >= 5:
            freq_score = 10.0
        elif purchase_count >= 2:
            freq_score = 7.0
        else:
            freq_score = 3.0

        # Bonus for recent CTC purchase (last 7 days)
        if last_ctc_days is not None and last_ctc_days <= 7:
            freq_score = min(freq_score + 3.0, 15.0)

        return freq_score

    def _score_category_affinity(self, event: object) -> float:
        """Score based on purchase category alignment with CTC inventory."""
        category = getattr(event, "category", None) or ""
        category_lower = category.lower().replace(" ", "_").replace("-", "_")
        return _CATEGORY_AFFINITY.get(category_lower, _CATEGORY_AFFINITY["default"])

    def _score_partner_crosssell(self, event: object) -> float:
        """Score based on partner brand cross-sell potential."""
        partner_brand = getattr(event, "partner_brand", None) or ""
        store_type = getattr(event, "store_type", "") or ""

        if store_type == "ctc_owned":
            return 15.0

        brand_key = partner_brand.lower().replace(" ", "_").replace("-", "_")
        return _PARTNER_CROSSSELL_SCORES.get(brand_key, _PARTNER_CROSSSELL_SCORES["default"])

    def _score_weather(self, weather: Optional[object]) -> float:
        """Adverse weather (snow/cold) increases in-store visit likelihood."""
        if weather is None:
            return 5.0  # default partial score
        is_adverse = getattr(weather, "is_adverse", False)
        condition = getattr(weather, "condition", "").lower()
        temp_c = getattr(weather, "temperature_c", 15.0)

        if is_adverse or condition in {"snow", "freezing_rain", "blizzard"}:
            return 10.0
        if condition in {"rain", "cold"} or temp_c < 0:
            return 8.0
        return 5.0

    def _score_time_alignment(self, event: object) -> float:
        """Score based on purchase time alignment with peak shopping hours."""
        timestamp = getattr(event, "timestamp", None)
        if timestamp is None:
            return 3.0

        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp)
            except ValueError:
                return 3.0

        hour = timestamp.hour
        weekday = timestamp.weekday()  # 0=Monday, 6=Sunday

        score = 5.0 if hour in _PEAK_HOURS else 2.0
        if weekday >= 5:  # weekend
            score = min(score + _WEEKEND_BONUS, 5.0)

        return score

    def score(self, context: EnrichedContext) -> ContextScore:
        """Score an enriched purchase context and determine trigger eligibility."""
        breakdown: dict[str, float] = {}

        breakdown["purchase_value"] = self._score_purchase_value(context.event.amount)
        breakdown["proximity"] = self._score_proximity(context.nearby_stores)
        breakdown["frequency"] = self._score_frequency(context.member)
        breakdown["category_affinity"] = self._score_category_affinity(context.event)
        breakdown["partner_crosssell"] = self._score_partner_crosssell(context.event)
        breakdown["weather"] = self._score_weather(context.weather)
        breakdown["time_alignment"] = self._score_time_alignment(context.event)

        total = sum(breakdown.values())
        # Clamp to [0, 100]
        total = max(0.0, min(100.0, total))

        # Threshold is strict: must be GREATER than threshold (not equal)
        should_trigger = total > self._threshold

        return ContextScore(
            total=round(total, 2),
            breakdown={k: round(v, 2) for k, v in breakdown.items()},
            should_trigger=should_trigger,
        )
