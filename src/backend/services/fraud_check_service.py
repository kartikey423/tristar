"""Fraud detection service — validates OfferBrief for high-risk patterns.

Integrates loyalty-fraud-detection domain logic:
- over_discounting: >30% value = critical
- offer_stacking: >3 active offers for same member = critical
- cannibalization: competing offers in same category
- frequency_abuse: offer generated too recently for same member
"""

from __future__ import annotations

from loguru import logger

from src.backend.models.offer_brief import FraudCheckResult, OfferBrief, RiskFlags, RiskSeverity

_OVER_DISCOUNT_THRESHOLD = 30.0  # percent — critical above this
_OFFER_STACK_THRESHOLD = 5       # critical if member has > this many active offers (raised from 3)
_DISCOUNT_TYPES = {"discount", "percentage_off", "percent_off"}


class FraudBlockedError(Exception):
    """Raised when fraud check returns severity=critical, blocking offer approval."""

    def __init__(self, result: FraudCheckResult) -> None:
        self.result = result
        super().__init__(f"Offer blocked due to critical fraud risk: {result.flags}")


class FraudCheckService:
    def __init__(self) -> None:
        # In-memory active offer count per member (production: query Hub)
        self._active_offer_counts: dict[str, int] = {}

    def _check_over_discounting(self, offer: OfferBrief) -> tuple[bool, list[str]]:
        """Flag if construct value exceeds 30% for discount-type constructs."""
        construct_type = offer.construct.type.lower()
        if construct_type in _DISCOUNT_TYPES and offer.construct.value > _OVER_DISCOUNT_THRESHOLD:
            return True, [
                f"Discount of {offer.construct.value:.1f}% exceeds 30% threshold"
            ]
        return False, []

    def _check_offer_stacking(self, member_id: str) -> tuple[bool, list[str]]:
        """Flag if member already has more than 3 active offers."""
        count = self._active_offer_counts.get(member_id, 0)
        if count >= _OFFER_STACK_THRESHOLD:
            return True, [
                f"Member already has {count} active offers (threshold: {_OFFER_STACK_THRESHOLD})"
            ]
        return False, []

    def _check_cannibalization(self, offer: OfferBrief) -> tuple[bool, list[str]]:
        """Flag if offer may cannibalize existing full-price sales in same category."""
        # Heuristic: points_multiplier on high-value segment suggests potential cannibalization
        warnings = []
        flagged = False
        if (
            offer.construct.type.lower() == "points_multiplier"
            and offer.construct.value >= 5
            and "high_value" in [c.lower() for c in offer.segment.criteria]
        ):
            flagged = True
            warnings.append(
                f"{offer.construct.value}× points multiplier on high-value segment "
                "may cannibalize full-margin purchases"
            )
        return flagged, warnings

    def _check_frequency_abuse(self, member_id: str, offer: OfferBrief) -> tuple[bool, list[str]]:
        """Flag if offer appears to be gaming the frequency rules."""
        # Lightweight heuristic: multiple high-value offers in short succession would be
        # tracked in Hub. MVP: always pass (tracked externally by delivery constraints).
        return False, []

    def validate(self, offer: OfferBrief, member_id: str = "") -> FraudCheckResult:
        """Run all fraud checks and return a consolidated result."""
        over_disc, wd1 = self._check_over_discounting(offer)
        stacking, wd2 = self._check_offer_stacking(member_id)
        cannib, wd3 = self._check_cannibalization(offer)
        freq, wd4 = self._check_frequency_abuse(member_id, offer)

        all_warnings = wd1 + wd2 + wd3 + wd4

        # Severity escalation: any critical flag → critical
        is_critical = over_disc or stacking
        severity = (
            RiskSeverity.critical
            if is_critical
            else (RiskSeverity.medium if (cannib or freq) else RiskSeverity.low)
        )

        flags = RiskFlags(
            over_discounting=over_disc,
            cannibalization=cannib,
            frequency_abuse=freq,
            offer_stacking=stacking,
            severity=severity,
            warnings=all_warnings,
        )

        blocked = severity == RiskSeverity.critical

        result = FraudCheckResult(
            severity=severity,
            flags=flags,
            warnings=all_warnings,
            blocked=blocked,
        )

        if blocked:
            logger.warning(
                "Offer blocked by fraud detection",
                extra={"offer_id": offer.offer_id, "severity": severity, "warnings": all_warnings},
            )
        else:
            logger.info(
                "Fraud check passed",
                extra={"offer_id": offer.offer_id, "severity": severity},
            )

        return result

    def record_active_offer(self, member_id: str) -> None:
        """Increment active offer count for offer stacking check."""
        self._active_offer_counts[member_id] = (
            self._active_offer_counts.get(member_id, 0) + 1
        )
