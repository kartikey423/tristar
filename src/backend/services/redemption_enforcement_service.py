"""Redemption enforcement service — validates Triangle Rewards 75/25 payment split.

Enforces that Triangle Rewards points cannot exceed 75% of an offer's total value.
The remaining 25% must be paid via credit/debit card.

Called by Scout activation pipeline before notification dispatch.
"""

from __future__ import annotations

from src.backend.models.offer_brief import OfferBrief
from src.backend.models.partner_event import RedemptionRequest, RedemptionSplitError


class RedemptionEnforcementService:
    """Validates payment split constraints on Triangle Rewards redemptions."""

    def validate_payment_split(self, offer: OfferBrief, redemption: RedemptionRequest) -> None:
        """Enforce the offer's payment_split constraint.

        If the offer has no payment_split set, validation passes (backward compatible).
        If payment_split is set, raises RedemptionSplitError when points_pct exceeds max.

        Args:
            offer: The OfferBrief being redeemed.
            redemption: The requested payment split (points_pct + cash_pct = 100).

        Raises:
            RedemptionSplitError: If redemption.points_pct > offer.construct.payment_split.points_max_pct.
        """
        if offer.construct.payment_split is None:
            return  # No constraint — backward compatible with legacy offers

        max_pct = offer.construct.payment_split.points_max_pct
        if redemption.points_pct > max_pct:
            raise RedemptionSplitError(
                points_pct=redemption.points_pct,
                max_pct=max_pct,
            )
