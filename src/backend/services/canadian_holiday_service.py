"""Canadian Holiday Calendar Service — Long Weekend and Time Type Detection.

Detects Canadian statutory holidays and classifies timestamps as:
- long_weekend: Friday–Monday window around a statutory holiday
- weekend: Saturday/Sunday (non-holiday)
- weekday: Monday–Friday (non-holiday)

Used for contextual partner trigger classification (e.g., Long Weekend → tailgating/camping offers).
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum


class TimeType(str, Enum):
    """Time classification for partner purchase events."""

    long_weekend = "long_weekend"
    weekend = "weekend"
    weekday = "weekday"


# ─── 2026 Canadian Statutory Holidays ─────────────────────────────────────────
# Fixed and floating holidays
_CANADIAN_HOLIDAYS_2026: set[date] = {
    # New Year's Day
    date(2026, 1, 1),
    # Family Day (3rd Monday of February — ON, AB, SK, BC, NB)
    date(2026, 2, 16),
    # Good Friday — April 3, 2026
    # Long weekend window: Apr 3 (Fri, holiday) → Apr 4 (Sat) → Apr 5 (Sun) → Apr 6 (Mon, holiday)
    # All four days classify as long_weekend via _is_long_weekend() adjacency logic.
    date(2026, 4, 3),
    # Easter Monday (Quebec statutory) — Apr 6 anchors the Apr 3–6 long weekend window
    date(2026, 4, 6),
    # Victoria Day (Monday before May 25)
    date(2026, 5, 18),
    # Canada Day
    date(2026, 7, 1),
    # Civic Holiday (1st Monday of August — most provinces)
    date(2026, 8, 3),
    # Labour Day (1st Monday of September)
    date(2026, 9, 7),
    # Thanksgiving (2nd Monday of October)
    date(2026, 10, 12),
    # Remembrance Day (not a stat holiday in all provinces, but widely observed)
    date(2026, 11, 11),
    # Christmas Day
    date(2026, 12, 25),
    # Boxing Day
    date(2026, 12, 26),
}


def _is_long_weekend(d: date) -> bool:
    """Check if date falls within a long weekend (Friday–Monday around a holiday).

    Long weekend rules:
    - If the date itself is a stat holiday → long_weekend
    - If Friday and next Monday is a stat holiday → long_weekend
    - If Monday and previous Friday was a stat holiday → long_weekend
    - If Saturday/Sunday and adjacent Friday or Monday is a stat holiday → long_weekend
    """
    # Check if the date itself is a holiday
    if d in _CANADIAN_HOLIDAYS_2026:
        return True

    # Get day of week (0=Monday, 6=Sunday)
    weekday = d.weekday()

    # Friday (4): Check if next Monday is a holiday
    if weekday == 4:  # Friday
        from datetime import timedelta
        next_monday = d + timedelta(days=3)
        if next_monday in _CANADIAN_HOLIDAYS_2026:
            return True

    # Saturday (5): Check if previous Friday or next Monday is a holiday
    if weekday == 5:  # Saturday
        from datetime import timedelta
        prev_friday = d - timedelta(days=1)
        next_monday = d + timedelta(days=2)
        if prev_friday in _CANADIAN_HOLIDAYS_2026 or next_monday in _CANADIAN_HOLIDAYS_2026:
            return True

    # Sunday (6): Check if next Monday is a holiday
    if weekday == 6:  # Sunday
        from datetime import timedelta
        next_monday = d + timedelta(days=1)
        if next_monday in _CANADIAN_HOLIDAYS_2026:
            return True

    # Monday (0): Check if previous Friday was a holiday
    if weekday == 0:  # Monday
        from datetime import timedelta
        prev_friday = d - timedelta(days=3)
        if prev_friday in _CANADIAN_HOLIDAYS_2026:
            return True

    return False


class CanadianHolidayService:
    """Detects Canadian statutory holidays and classifies time types."""

    def get_time_type(self, timestamp: datetime) -> TimeType:
        """Classify timestamp as long_weekend, weekend, or weekday.

        Args:
            timestamp: Purchase event timestamp.

        Returns:
            TimeType enum value.
        """
        d = timestamp.date()
        weekday = d.weekday()

        # Check if long weekend
        if _is_long_weekend(d):
            return TimeType.long_weekend

        # Check if regular weekend (Saturday/Sunday, non-holiday)
        if weekday in (5, 6):  # Saturday or Sunday
            return TimeType.weekend

        # Weekday (Monday–Friday, non-holiday)
        return TimeType.weekday
