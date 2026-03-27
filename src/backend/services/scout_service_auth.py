"""Scout service JWT lifecycle manager.

F-005 FIX: This component owns the Scout service JWT — generating it at startup
and proactively refreshing it when 80% of the TTL has elapsed, so COMP-017
(PurchaseEventRouter) and COMP-018 (PurchaseEventHandler) always have a valid token.

The token has role='system' and is used for Scout → Designer service calls.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import jwt
from loguru import logger

from src.backend.core.config import settings


class ScoutServiceAuth:
    def __init__(self) -> None:
        self._token: Optional[str] = None
        self._expires_at: Optional[datetime] = None
        self._expiry_hours = settings.SERVICE_JWT_EXPIRY_HOURS

    def _generate(self) -> str:
        """Generate a new service JWT with role='system'."""
        now = datetime.utcnow()
        expires_at = now + timedelta(hours=self._expiry_hours)
        payload = {
            "sub": "scout-service",
            "role": "system",
            "iat": now,
            "exp": expires_at,
        }
        token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
        self._token = token
        self._expires_at = expires_at
        logger.info(
            "Scout service JWT generated",
            extra={"expires_at": expires_at.isoformat()},
        )
        return token

    def _needs_refresh(self) -> bool:
        """Return True if token is missing or within 20% of TTL remaining (80% elapsed)."""
        if self._token is None or self._expires_at is None:
            return True
        now = datetime.utcnow()
        total_ttl = timedelta(hours=self._expiry_hours)
        # Refresh when 80% of TTL has elapsed (i.e., 20% remaining)
        refresh_threshold = self._expires_at - (total_ttl * 0.2)
        return now >= refresh_threshold

    def get_valid_token(self) -> str:
        """Return current valid service token, refreshing proactively if needed."""
        if self._needs_refresh():
            return self._generate()
        return self._token  # type: ignore[return-value]

    def bearer_header(self) -> dict[str, str]:
        """Return Authorization header dict with current valid token."""
        return {"Authorization": f"Bearer {self.get_valid_token()}"}


# Module-level singleton — injected via Depends() in Scout routes
scout_auth = ScoutServiceAuth()
